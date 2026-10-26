"""Held-out families about routes between two equipment items (EXP-0006, ADR-0035).

All three walk only `send_to` edges (material flow: `A -send_to-> B` means A feeds B) and use
the same shortest path as `FLOW_PATH`: fewest hops, ties broken by the smallest tag sequence.

- `FIRST_MEETING_POINT`: where the flows leaving two items first come together.
- `VALVES_ON_PATH`: how many valves lie between two items.
- `ROUTE_AVOIDING`: can flow still get from A to B if one item on the way is removed?

Choices where the design left room (each is a one-line rule, kept in the code too):
- A and B are always equipment items; the item removed in `ROUTE_AVOIDING` may be any item.
- `FIRST_MEETING_POINT` is symmetric in A and B, so only the pair with `tag(A) < tag(B)` is asked.
- The "yes" evidence of `ROUTE_AVOIDING` is the breadth-first path (first parent in sorted
  node-id order), since the design names no tie-break for the detour.
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
    build_question,
    is_path_item,
    nodes_of_classes,
    send_to_predecessors,
    send_to_successors,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.families_aggregate import COUNTED_CLASSES
from plantgraph.qa.questions.families_flow import (
    Reached,
    one_target_per_bin,
    path_to,
    reach_from,
)
from plantgraph.qa.questions.templates_heldout import (
    first_meeting_point_text,
    route_avoiding_text,
    valves_on_path_text,
)

_TEMPLATE_VERSION = "1"


def _path_evidence(*paths: list[str]) -> Evidence:
    """The nodes and consecutive-pair edges of one or more node-id paths."""
    return Evidence(
        nodes=frozenset(n for path in paths for n in path),
        edges=frozenset(edge for path in paths for edge in zip(path, path[1:], strict=False)),
    )


def _tag(plant: nx.DiGraph[str], node_id: str) -> str:
    return str(plant.nodes[node_id]["tag"])


class _ReachCache:
    """`reach_from` per node, computed on first use and kept (descendant sets are small)."""

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
    own_tag = _tag(plant, source_id)
    partners = [
        n
        for n in seen
        if n not in reached
        and plant.nodes[n]["node_class"] in EQUIPMENT_CLASSES
        and _tag(plant, n) > own_tag
    ]
    return sorted(partners, key=lambda n: _tag(plant, n))


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
        text=first_meeting_point_text(_tag(plant, source_id), _tag(plant, partner_id)),
        answer_type=AnswerType.TAG,
        reference=_tag(plant, meeting_id),
        evidence=_path_evidence(path_a, path_b),
        anchors=[_tag(plant, source_id), _tag(plant, partner_id)],
        plant=plant,
        index=index,
        seed=seed,
    )


# --- VALVES_ON_PATH --------------------------------------------------------------------------


def _valve_count_ranges(
    plant: nx.DiGraph[str], successors: dict[str, list[str]], source_id: str
) -> dict[str, tuple[int, int]]:
    """For each reachable node: fewest and most valves strictly between the source and it.

    Taken over *all* shortest paths: one breadth-first layer at a time, a node's range merges
    the ranges of its predecessors in the previous layer (plus that predecessor, if a valve).
    """
    ranges = {source_id: (0, 0)}
    frontier = [source_id]
    while frontier:
        found: dict[str, tuple[int, int]] = {}
        for node_id in frontier:
            low, high = ranges[node_id]
            add = 1 if plant.nodes[node_id]["node_class"] in VALVE_CLASSES else 0
            for successor_id in successors[node_id]:
                if successor_id in ranges:
                    continue
                # the first offer sets the range; later offers (other parents) widen it
                old_low, old_high = found.get(successor_id, (low + add, high + add))
                found[successor_id] = (min(old_low, low + add), max(old_high, high + add))
        ranges.update(found)
        frontier = sorted(found)
    return ranges


def valves_on_path_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """At most one candidate per `(source, k-bin)`; every shortest path must hold the same count."""
    index = SheetIndex.from_sheets(sheets, manifest)
    cache = _ReachCache(plant, index)
    equipment = set(nodes_of_classes(plant, EQUIPMENT_CLASSES))
    questions = []
    for source_id in sorted(equipment):
        ranges = _valve_count_ranges(plant, cache.successors, source_id)
        targets = {
            target_id: reached
            for target_id, reached in cache.of(source_id).items()
            if target_id in equipment
            and target_id != source_id
            and ranges[target_id][0] == ranges[target_id][1]
        }
        rng = random.Random(f"{seed}:VALVES_ON_PATH:{source_id}")
        for target_id in one_target_per_bin(targets, rng):
            path = path_to(cache.of(source_id), source_id, target_id)
            questions.append(
                build_question(
                    corpus_id=corpus_id,
                    family=QuestionFamily.VALVES_ON_PATH,
                    template_id="VALVES_ON_PATH",
                    template_version=_TEMPLATE_VERSION,
                    text=valves_on_path_text(_tag(plant, source_id), _tag(plant, target_id)),
                    answer_type=AnswerType.COUNT,
                    reference=ranges[target_id][0],
                    evidence=_path_evidence(path),
                    anchors=[_tag(plant, source_id), _tag(plant, target_id)],
                    plant=plant,
                    index=index,
                    seed=seed,
                )
            )
    return questions


# --- ROUTE_AVOIDING --------------------------------------------------------------------------


def _tree_without(
    successors: dict[str, list[str]], source_id: str, removed_id: str
) -> dict[str, str]:
    """Breadth-first tree from `source_id` with `removed_id` taken out: node -> first parent."""
    parent_of: dict[str, str] = {}
    frontier = [source_id]
    while frontier:
        found: dict[str, str] = {}
        for current in frontier:
            for successor in successors[current]:
                if successor not in (source_id, removed_id) and successor not in parent_of:
                    found.setdefault(successor, current)
        parent_of.update(found)
        frontier = sorted(found)
    return parent_of


def _route_in_tree(parent_of: dict[str, str], source_id: str, target_id: str) -> list[str]:
    """The path from the tree's root `source_id` down to `target_id`."""
    path = [target_id]
    while path[-1] != source_id:
        path.append(parent_of[path[-1]])
    return path[::-1]


def route_avoiding_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """Per source A and shortest-path k-bin: one target B, one removed item V on the way.

    The answer ("yes" or "no") is asked for alternately, starting from a seeded side, so that
    neither dominates; when a target offers only one of the two, that one is used.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    cache = _ReachCache(plant, index)
    equipment = set(nodes_of_classes(plant, EQUIPMENT_CLASSES))
    questions = []
    for source_id in sorted(equipment):
        rng = random.Random(f"{seed}:ROUTE_AVOIDING:{source_id}")
        wants_yes = rng.random() < 0.5
        # a target needs an item strictly inside its path to avoid (a tee does not count)
        targets = {
            t: r
            for t, r in cache.of(source_id).items()
            if t in equipment
            and t != source_id
            and _items_inside(plant, path_to(cache.of(source_id), source_id, t))
        }
        for target_id in one_target_per_bin(targets, rng):
            path = path_to(cache.of(source_id), source_id, target_id)
            removed = _removed_item(plant, cache.successors, path, wants_yes, rng)
            wants_yes = not wants_yes
            questions.append(_route_question(plant, index, corpus_id, seed, path, *removed))
    return questions


def _items_inside(plant: nx.DiGraph[str], path: list[str]) -> list[str]:
    """The equipment items and valves strictly between a path's two ends, in path order."""
    return [node_id for node_id in path[1:-1] if is_path_item(plant, node_id)]


def _removed_item(
    plant: nx.DiGraph[str],
    successors: dict[str, list[str]],
    path: list[str],
    wants_yes: bool,
    rng: random.Random,
) -> tuple[str, dict[str, str]]:
    """Pick the item V strictly inside `path` whose removal gives the wanted answer.

    Returns `(V, tree of the plant without V)`. If no V gives the wanted answer, one with the
    other answer is used.
    """
    source_id, target_id = path[0], path[-1]
    trees = {v: _tree_without(successors, source_id, v) for v in _items_inside(plant, path)}
    if not trees:
        raise ValueError(f"expected a path with an item inside, found {path}")
    wanted = [v for v, tree in trees.items() if (target_id in tree) == wants_yes]
    removed_id = rng.choice(wanted or sorted(trees))
    return removed_id, trees[removed_id]


def _route_question(
    plant: nx.DiGraph[str],
    index: SheetIndex,
    corpus_id: str,
    seed: int,
    path: list[str],
    removed_id: str,
    parent_of: dict[str, str],
) -> Question:
    source_id, target_id = path[0], path[-1]
    if target_id in parent_of:
        evidence = _path_evidence(_route_in_tree(parent_of, source_id, target_id))
    else:  # proving "no" means seeing everything A still reaches
        tree_edges = frozenset((parent, child) for child, parent in parent_of.items())
        evidence = Evidence(nodes=frozenset({source_id, *parent_of}), edges=tree_edges)
    tags = [_tag(plant, source_id), _tag(plant, target_id), _tag(plant, removed_id)]
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.ROUTE_AVOIDING,
        template_id="ROUTE_AVOIDING",
        template_version=_TEMPLATE_VERSION,
        text=route_avoiding_text(*tags),
        answer_type=AnswerType.BOOLEAN,
        reference="yes" if target_id in parent_of else "no",
        evidence=evidence,
        anchors=tags,
        plant=plant,
        index=index,
        seed=seed,
    )
