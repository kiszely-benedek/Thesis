"""NEIGHBOURS_DOWNSTREAM and FLOW_PATH: questions that follow `send_to` edges (design §9).

`send_to` is the pipe-segment relation: `A -send_to-> B` means material
flows from `A` directly into `B` (`graph/schema.py`). Both families below
walk only this relation — never `send_signal_to`, `control` or
`measured_by`, which are the *instrumentation* wiring `families_loop.py`
reads instead.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.availability import KBin, k_bin_of_k
from plantgraph.qa.questions.common import (
    ItemHop,
    build_question,
    is_path_item,
    next_path_items,
    send_to_successors,
    tagged_nodes_by_tag,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.templates import flow_path_text, neighbours_downstream_text

_TEMPLATE_VERSION = "1"


def neighbours_downstream_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per item with at least one item directly downstream of it.

    "Directly" looks through unnamed pipe fittings (a tee), so evidence holds the fittings too.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for node_id, tag in tagged_nodes_by_tag(plant):
        hops = next_path_items(plant, node_id) if is_path_item(plant, node_id) else []
        if not hops:
            continue
        evidence = _hops_evidence(node_id, hops)
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.NEIGHBOURS_DOWNSTREAM,
                template_id="NEIGHBOURS_DOWNSTREAM",
                template_version=_TEMPLATE_VERSION,
                text=neighbours_downstream_text(tag),
                answer_type=AnswerType.TAG_SET,
                reference=sorted(str(plant.nodes[hop.item_id]["tag"]) for hop in hops),
                evidence=evidence,
                anchors=[tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


def _hops_evidence(node_id: str, hops: list[ItemHop]) -> Evidence:
    """Every node and edge between `node_id` and the items it feeds, fittings included."""
    nodes = {node_id}
    edges: set[tuple[str, str]] = set()
    for hop in hops:
        chain = [node_id, *hop.via, hop.item_id]
        nodes.update(chain)
        edges.update(zip(chain, chain[1:], strict=False))
    return Evidence(nodes=frozenset(nodes), edges=frozenset(edges))


def flow_path_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """At most one `FLOW_PATH` candidate per `(source, k-bin)`, over every reachable target.

    There is no hop cap: how well a strategy answers across sheet and unit
    boundaries is the thing under test (ADR-0029). One forward walk per
    source finds every target's path and `k` cheaply; only the one target
    drawn per bin is turned into a `Question`, because building a question
    for every pair did not finish at 1,000 sheets.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    successors = {node_id: send_to_successors(plant, node_id) for node_id in plant.nodes}
    questions = []
    for source_id, source_tag in tagged_nodes_by_tag(plant):
        if not is_path_item(plant, source_id):
            continue
        reached = reach_from(plant, successors, source_id, index)
        del reached[source_id]  # a path from a node to itself is not a question
        items_reached = {n: r for n, r in reached.items() if is_path_item(plant, n)}
        rng = random.Random(f"{seed}:{source_id}")  # one stream per source: draws stay independent
        for target_id in one_target_per_bin(items_reached, rng):
            path = path_to(reached, source_id, target_id)
            questions.append(
                _flow_path_question(
                    plant,
                    index,
                    corpus_id=corpus_id,
                    seed=seed,
                    source_tag=source_tag,
                    target_tag=str(plant.nodes[target_id]["tag"]),
                    path=path,
                )
            )
    return questions


@dataclass(frozen=True)
class Reached:
    """How a walk got to one node: the node before it, and the sheet-crossing edges on the way."""

    parent: str | None
    k: int


def one_target_per_bin(reached: dict[str, Reached], rng: random.Random) -> list[str]:
    """One reachable target for each k-bin that has any, drawn with `rng`, in bin order."""
    by_bin: dict[KBin, list[str]] = {}
    for target_id in sorted(reached):
        by_bin.setdefault(k_bin_of_k(reached[target_id].k), []).append(target_id)
    return [rng.choice(by_bin[k_bin]) for k_bin in KBin if k_bin in by_bin]


def _flow_path_question(
    plant: nx.DiGraph[str],
    index: SheetIndex,
    *,
    corpus_id: str,
    seed: int,
    source_tag: str,
    target_tag: str,
    path: list[str],
) -> Question:
    evidence = Evidence(nodes=frozenset(path), edges=frozenset(zip(path, path[1:], strict=False)))
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.FLOW_PATH,
        template_id="FLOW_PATH",
        template_version=_TEMPLATE_VERSION,
        text=flow_path_text(source_tag, target_tag),
        answer_type=AnswerType.TAG_PATH,
        reference=[str(plant.nodes[n]["tag"]) for n in path if is_path_item(plant, n)],
        evidence=evidence,
        anchors=[source_tag, target_tag],
        plant=plant,
        index=index,
        seed=seed,
    )


def path_to(reached: dict[str, Reached], source_id: str, target_id: str) -> list[str]:
    """Rebuild the walk's path to `target_id` by following parents back to the source."""
    path = [target_id]
    while path[-1] != source_id:
        parent = reached[path[-1]].parent
        if parent is None:
            raise ValueError(
                f"expected a parent chain ending at {source_id!r}, broke at {path[-1]!r}"
            )
        path.append(parent)
    return path[::-1]


def reach_from(
    plant: nx.DiGraph[str],
    successors: dict[str, list[str]],
    source_id: str,
    index: SheetIndex,
) -> dict[str, Reached]:
    """Every node reachable from `source_id` over `send_to`, by a shortest path.

    Among equal-length shortest paths to a node, keeps the one whose *tag*
    sequence is lexicographically smallest (design §9, FLOW_PATH). The walk
    goes one BFS layer at a time: every node first met in one layer is the
    same number of hops away, so the best parent seen in that layer wins
    outright. Only parents are stored; full paths are rebuilt for the few
    targets that become questions.

    Comparing two parents' tag sequences would cost a path rebuild per tie, and a v2 plant has
    many ties (parallel branches between two tees). Instead each layer is ranked once, so a
    comparison is one integer test: see `_rank_layer`.
    """
    reached = {source_id: Reached(parent=None, k=0)}
    rank = {source_id: 0}
    frontier = [source_id]
    while frontier:
        found: dict[str, Reached] = {}
        for node_id in frontier:
            _offer_successors(successors, node_id, reached, found, index, rank)
        reached.update(found)
        rank = _rank_layer(plant, found, rank)
        frontier = sorted(found)
    return reached


def _offer_successors(
    successors: dict[str, list[str]],
    node_id: str,
    reached: dict[str, Reached],
    found: dict[str, Reached],
    index: SheetIndex,
    rank: dict[str, int],
) -> None:
    """Offer `node_id` as parent of each of its new successors; keep the smaller-ranked parent."""
    for successor_id in successors[node_id]:
        if successor_id in reached:
            continue
        current = found.get(successor_id)
        if current is not None and not _outranks(rank, node_id, current):
            continue
        k = reached[node_id].k + index.crosses(node_id, successor_id)
        found[successor_id] = Reached(parent=node_id, k=k)


def _outranks(rank: dict[str, int], new_parent: str, current: Reached) -> bool:
    """Whether `new_parent`'s path has strictly smaller tags than the one via `current`."""
    if current.parent is None:
        raise ValueError("expected a stored non-source parent when comparing tie candidates")
    return rank[new_parent] < rank[current.parent]


def _rank_layer(
    plant: nx.DiGraph[str], layer: dict[str, Reached], parent_rank: dict[str, int]
) -> dict[str, int]:
    """Rank one BFS layer by the tag sequence of its paths (0 = smallest; equal sequences tie).

    Every path in a layer has the same length, so two sequences compare first by their parents'
    sequences (already ranked, one layer up) and then by the node's own tag. An untagged fitting
    counts as its node id: that only breaks ties between routes through unnamed fittings.
    """

    def sequence_key(node_id: str) -> tuple[int, str]:
        parent = layer[node_id].parent
        if parent is None:
            raise ValueError(f"expected a parent for {node_id!r} in a layer past the source")
        return parent_rank[parent], str(plant.nodes[node_id].get("tag", node_id))

    if len(layer) == 1:  # most layers of a long chain: nothing to compare
        return dict.fromkeys(layer, 0)
    keys = {node_id: sequence_key(node_id) for node_id in layer}
    ranks: dict[str, int] = {}
    previous: tuple[int, str] | None = None
    rank = -1
    for node_id in sorted(layer, key=keys.__getitem__):
        if keys[node_id] != previous:
            rank += 1
            previous = keys[node_id]
        ranks[node_id] = rank
    return ranks
