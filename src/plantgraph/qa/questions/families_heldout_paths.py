"""Held-out families about routes between two equipment items (EXP-0006, ADR-0035).

All three walk only `send_to` edges (material flow: `A -send_to-> B` means A feeds B) and use
the same shortest path as `FLOW_PATH`: fewest hops, ties broken by the smallest tag sequence.

- `FIRST_MEETING_POINT`: where the flows leaving two items first come together.
- `VALVES_ON_PATH`: how many valves lie between two items, counted at item level (equipment and
  valves are the hops; untagged fittings such as tees are passed through).
- `ROUTE_AVOIDING`: can flow still get from A to B if one item on the way is removed?
  (lives in `families_heldout_route.py`, to keep this file short)

Choices where the design left room (each is a one-line rule, kept in the code too):
- A and B are always equipment items.
- `FIRST_MEETING_POINT` is symmetric in A and B, so only the pair with `tag(A) < tag(B)` is asked.
"""

from __future__ import annotations

import random

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, VALVE_CLASSES
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.availability import KBin, k_bin_of_k
from plantgraph.qa.questions.common import (
    ItemHop,
    build_question,
    is_path_item,
    next_path_items,
    nodes_of_classes,
    send_to_predecessors,
    send_to_successors,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.families_aggregate import COUNTED_CLASSES
from plantgraph.qa.questions.families_flow import (
    Reached,
    layer_sort_tags,
    one_target_per_bin,
    path_to,
    reach_from,
)
from plantgraph.qa.questions.templates_heldout import (
    first_meeting_point_text,
    valves_on_path_text,
)

_TEMPLATE_VERSION = "1"


def path_evidence(*paths: list[str]) -> Evidence:
    """The nodes and consecutive-pair edges of one or more node-id paths."""
    return Evidence(
        nodes=frozenset(n for path in paths for n in path),
        edges=frozenset(edge for path in paths for edge in zip(path, path[1:], strict=False)),
    )


def tag_of(plant: nx.DiGraph[str], node_id: str) -> str:
    """The tag of a node: its printed equipment or valve name."""
    return str(plant.nodes[node_id]["tag"])


class _ReachCache:
    """`reach_from` per node, computed on first use and kept for the pairwise walk.

    Only `FIRST_MEETING_POINT` needs this: it asks about many pairs of nodes. The other two
    families use each source once and call `reach_from` directly, so they never hold more than
    one source's reach.
    """

    def __init__(self, plant: nx.DiGraph[str], index: SheetIndex) -> None:
        self._plant = plant
        self._index = index
        self.successors = {node_id: send_to_successors(plant, node_id) for node_id in plant.nodes}
        self._reached: dict[str, dict[str, Reached]] = {}

    def of(self, node_id: str) -> dict[str, Reached]:
        """Every node reachable from `node_id` (itself included), with its shortest-path parent."""
        if node_id not in self._reached:
            self._reached[node_id] = reach_from(self._plant, self.successors, node_id, self._index)
        return self._reached[node_id]


# --- FIRST_MEETING_POINT ---------------------------------------------------------------------


def first_meeting_point_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """At most one candidate per `(A, k-bin)`: a partner B whose flow first joins that of A."""
    index = SheetIndex.from_sheets(sheets, manifest)
    cache = _ReachCache(plant, index)
    questions = []
    for source_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        by_bin = _meetings_by_bin(plant, cache, source_id)
        rng = random.Random(f"{seed}:FIRST_MEETING_POINT:{source_id}")
        for k_bin in KBin:
            if k_bin in by_bin:
                partner_id, meeting_id = rng.choice(by_bin[k_bin])
                questions.append(
                    _meeting_question(
                        plant, index, cache, corpus_id, seed, source_id, partner_id, meeting_id
                    )
                )
    return questions


def _meetings_by_bin(
    plant: nx.DiGraph[str], cache: _ReachCache, source_id: str
) -> dict[KBin, list[tuple[str, str]]]:
    """For source A: k-bin -> every valid `(partner B, meeting point m)`, B in sorted order."""
    reached = cache.of(source_id)
    by_bin: dict[KBin, list[tuple[str, str]]] = {}
    for partner_id in _equipment_sharing_a_descendant(plant, reached, source_id):
        meeting_id = _meeting_point(plant, cache, source_id, partner_id)
        if meeting_id is None:
            continue
        # the two paths meet only at `meeting_id` (see `_meeting_point`), so their k add up
        k = reached[meeting_id].k + cache.of(partner_id)[meeting_id].k
        by_bin.setdefault(k_bin_of_k(k), []).append((partner_id, meeting_id))
    return by_bin


def _equipment_sharing_a_descendant(
    plant: nx.DiGraph[str], reached: dict[str, Reached], source_id: str
) -> list[str]:
    """Equipment B, sorted by tag after A's, with some node downstream of both A and B.

    Walks `send_to` backwards from everything A reaches: any B found that way shares a
    descendant with A. Only B with a larger tag than A is kept (the pair is symmetric).
    """
    seen = set(reached)
    frontier = sorted(reached)
    while frontier:
        found = {p for n in frontier for p in send_to_predecessors(plant, n) if p not in seen}
        seen |= found
        frontier = sorted(found)
    own_tag = tag_of(plant, source_id)
    partners = [
        n
        for n in seen
        if n not in reached
        and plant.nodes[n]["node_class"] in EQUIPMENT_CLASSES
        and tag_of(plant, n) > own_tag
    ]
    return sorted(partners, key=lambda n: tag_of(plant, n))


def _meeting_point(
    plant: nx.DiGraph[str], cache: _ReachCache, first_id: str, second_id: str
) -> str | None:
    """The one item where the flows of A and B first come together, or `None` if there is none.

    Needs: neither reaches the other; their common descendants D are not empty; exactly one
    member `m` of D reaches every other member; and `m` is equipment or a valve. The two
    shortest paths to `m` then share only `m`: a shared earlier node would lie in D and
    be reached from `m`, so it would be a second candidate.
    """
    first, second = cache.of(first_id), cache.of(second_id)
    if first_id in second or second_id in first:
        return None
    common = set(first) & set(second)
    reaching_all = [m for m in sorted(common) if common <= set(cache.of(m))]
    if len(reaching_all) != 1:
        return None
    meeting_id = reaching_all[0]
    return meeting_id if plant.nodes[meeting_id]["node_class"] in COUNTED_CLASSES else None


def _meeting_question(
    plant: nx.DiGraph[str],
    index: SheetIndex,
    cache: _ReachCache,
    corpus_id: str,
    seed: int,
    source_id: str,
    partner_id: str,
    meeting_id: str,
) -> Question:
    path_a = path_to(cache.of(source_id), source_id, meeting_id)
    path_b = path_to(cache.of(partner_id), partner_id, meeting_id)
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.FIRST_MEETING_POINT,
        template_id="FIRST_MEETING_POINT",
        template_version=_TEMPLATE_VERSION,
        text=first_meeting_point_text(tag_of(plant, source_id), tag_of(plant, partner_id)),
        answer_type=AnswerType.TAG,
        reference=tag_of(plant, meeting_id),
        evidence=path_evidence(path_a, path_b),
        anchors=[tag_of(plant, source_id), tag_of(plant, partner_id)],
        plant=plant,
        index=index,
        seed=seed,
    )


# --- VALVES_ON_PATH --------------------------------------------------------------------------


def item_hops(plant: nx.DiGraph[str]) -> dict[str, dict[str, ItemHop]]:
    """Each path item -> the items it feeds directly, fittings folded away, keyed by item id."""
    return {
        node_id: {hop.item_id: hop for hop in next_path_items(plant, node_id)}
        for node_id in plant.nodes
        if is_path_item(plant, node_id)
    }


def item_valve_counts(
    plant: nx.DiGraph[str], source_id: str, hops: dict[str, dict[str, ItemHop]] | None = None
) -> dict[str, frozenset[int]]:
    """For each item reachable from the source: the valve counts of its item-level shortest routes.

    A hop is one item to the next (fittings are passed through, as `next_path_items` does), and
    "between" means the items strictly inside the route. One breadth-first layer at a time, an
    item collects the counts of its predecessors in the previous layer, plus that predecessor
    if it is a valve. More than one count in a set means the pair is ambiguous.

    Args:
        plant: the plant graph.
        source_id: the equipment item the routes start at.
        hops: `item_hops(plant)`, passed in when many sources are walked, to build it only once.
    """
    hops = item_hops(plant) if hops is None else hops
    counts = {source_id: frozenset({0})}
    frontier = [source_id]
    while frontier:
        found: dict[str, set[int]] = {}
        for node_id in frontier:
            add = 1 if plant.nodes[node_id]["node_class"] in VALVE_CLASSES else 0
            for next_id in hops[node_id]:
                if next_id not in counts:
                    found.setdefault(next_id, set()).update(c + add for c in counts[node_id])
        counts.update({node_id: frozenset(values) for node_id, values in found.items()})
        frontier = sorted(found)
    return counts


def _route_evidence(item_path: list[str], hops: dict[str, dict[str, ItemHop]]) -> Evidence:
    """The item-level route as evidence, with the fittings between consecutive items put back."""
    full_path = [item_path[0]]
    for from_id, to_id in zip(item_path, item_path[1:], strict=False):
        full_path.extend([*hops[from_id][to_id].via, to_id])
    return path_evidence(full_path)


def valves_on_path_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """At most one candidate per `(source, k-bin)`; every item-level shortest route must agree."""
    index = SheetIndex.from_sheets(sheets, manifest)
    hops = item_hops(plant)
    item_successors = {node_id: sorted(next_items) for node_id, next_items in hops.items()}
    tags = layer_sort_tags(plant)
    equipment = set(nodes_of_classes(plant, EQUIPMENT_CLASSES))
    questions = []
    for source_id in sorted(equipment):
        counts = item_valve_counts(plant, source_id, hops)  # dropped after this source
        reach = reach_from(plant, item_successors, source_id, index, tags=tags)
        targets = {
            target_id: reached
            for target_id, reached in reach.items()
            if target_id in equipment
            and target_id != source_id
            and len(counts[target_id]) == 1  # ambiguous pairs are never asked (ADR-0065, D1)
        }
        rng = random.Random(f"{seed}:VALVES_ON_PATH:{source_id}")
        for target_id in one_target_per_bin(targets, rng):
            item_path = path_to(reach, source_id, target_id)
            (count,) = counts[target_id]
            questions.append(
                build_question(
                    corpus_id=corpus_id,
                    family=QuestionFamily.VALVES_ON_PATH,
                    template_id="VALVES_ON_PATH",
                    template_version=_TEMPLATE_VERSION,
                    text=valves_on_path_text(tag_of(plant, source_id), tag_of(plant, target_id)),
                    answer_type=AnswerType.COUNT,
                    reference=count,
                    evidence=_route_evidence(item_path, hops),
                    anchors=[tag_of(plant, source_id), tag_of(plant, target_id)],
                    plant=plant,
                    index=index,
                    seed=seed,
                )
            )
    return questions
