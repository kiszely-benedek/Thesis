"""CONNECTED, DOWNSTREAM_IN_UNIT and UPSTREAM_SOURCES: the dev-new families that follow flow.

Design `question-aware-retrieval.md` §8.2. All three walk only `send_to` edges (material
flow: `A -send_to-> B` means A feeds B), and none reads an equipment attribute (ADR-0021).
An **item** below is an equipment item (pump, tank, vessel ...), the same pool
`UPSTREAM_ISOLATION` and `NO_PATH` draw their anchors from.
"""

from __future__ import annotations

import random

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import (
    build_question,
    nodes_of_classes,
    send_to_predecessors,
    send_to_successors,
    unit_of,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.families_aggregate import COUNTED_CLASSES
from plantgraph.qa.questions.families_flow import (
    Reached,
    one_target_per_bin,
    path_to,
    reach_from,
)
from plantgraph.qa.questions.templates import (
    connected_text,
    downstream_in_unit_text,
    upstream_sources_text,
)

_TEMPLATE_VERSION = "1"


# --- CONNECTED -------------------------------------------------------------------------------


def connected_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """Per source item: one "yes" target per k-bin that has one, and one "no" target.

    "yes" evidence is the shortest path (as `FLOW_PATH`); "no" evidence is the whole walk from
    the source (a breadth-first tree), because proving "not reachable" means seeing everything
    the source does reach. The sampler alternates yes and no inside a bin.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    successors = {node_id: send_to_successors(plant, node_id) for node_id in plant.nodes}
    items = nodes_of_classes(plant, EQUIPMENT_CLASSES)
    questions: list[Question] = []
    for source_id in items:
        reached = reach_from(plant, successors, source_id, index)
        rng = random.Random(f"{seed}:CONNECTED:{source_id}")
        yes = _yes_questions(reached, source_id, items, rng)
        no = _no_questions(reached, source_id, items, rng)
        questions += [
            _connected_question(plant, index, corpus_id, seed, *spec) for spec in yes + no
        ]
    return questions


#: What `_connected_question` needs: source id, target id, "yes"/"no", and the evidence.
_ConnectedSpec = tuple[str, str, str, Evidence]


def _yes_questions(
    reached: dict[str, Reached],
    source_id: str,
    items: list[str],
    rng: random.Random,
) -> list[_ConnectedSpec]:
    item_set = set(items)
    targets = {t: r for t, r in reached.items() if t in item_set and t != source_id}
    specs = []
    for target_id in one_target_per_bin(targets, rng):
        path = path_to(reached, source_id, target_id)
        evidence = Evidence(
            nodes=frozenset(path), edges=frozenset(zip(path, path[1:], strict=False))
        )
        specs.append((source_id, target_id, "yes", evidence))
    return specs


def _no_questions(
    reached: dict[str, Reached],
    source_id: str,
    items: list[str],
    rng: random.Random,
) -> list[_ConnectedSpec]:
    unreachable = [item for item in items if item not in reached]
    if not unreachable:
        return []
    tree_edges = frozenset((r.parent, n) for n, r in reached.items() if r.parent is not None)
    evidence = Evidence(nodes=frozenset(reached), edges=tree_edges)
    return [(source_id, rng.choice(unreachable), "no", evidence)]


def _connected_question(
    plant: nx.DiGraph[str],
    index: SheetIndex,
    corpus_id: str,
    seed: int,
    source_id: str,
    target_id: str,
    reference: str,
    evidence: Evidence,
) -> Question:
    source_tag, target_tag = str(plant.nodes[source_id]["tag"]), str(plant.nodes[target_id]["tag"])
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.CONNECTED,
        template_id="CONNECTED",
        template_version=_TEMPLATE_VERSION,
        text=connected_text(source_tag, target_tag),
        answer_type=AnswerType.BOOLEAN,
        reference=reference,
        evidence=evidence,
        anchors=[source_tag, target_tag],
        plant=plant,
        index=index,
        seed=seed,
    )


# --- DOWNSTREAM_IN_UNIT ----------------------------------------------------------------------


def downstream_in_unit_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per item that feeds something else of its own unit, directly or not."""
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for item_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        unit_id = unit_of(plant, item_id)
        if unit_id is None:
            continue
        reached, edges = _walk_inside_unit(plant, item_id, unit_id)
        receiving = [n for n in reached if plant.nodes[n]["node_class"] in COUNTED_CLASSES]
        if not receiving:
            continue
        tag = str(plant.nodes[item_id]["tag"])
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.DOWNSTREAM_IN_UNIT,
                template_id="DOWNSTREAM_IN_UNIT",
                template_version=_TEMPLATE_VERSION,
                text=downstream_in_unit_text(unit_id, tag),
                answer_type=AnswerType.TAG_SET,
                reference=sorted(str(plant.nodes[n]["tag"]) for n in receiving),
                evidence=Evidence(nodes=frozenset({item_id, *reached}), edges=edges),
                anchors=[tag, unit_id],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


def _walk_inside_unit(
    plant: nx.DiGraph[str], start_id: str, unit_id: str
) -> tuple[set[str], frozenset[tuple[str, str]]]:
    """Items reached from `start_id` over `send_to`, entering only items of `unit_id`.

    Returns the reached items (the start excluded) and every edge walked into the unit.
    """
    reached: set[str] = set()
    edges: set[tuple[str, str]] = set()
    frontier = [start_id]
    while frontier:
        next_frontier: list[str] = []
        for current in frontier:
            for successor in send_to_successors(plant, current):
                if unit_of(plant, successor) != unit_id:
                    continue  # leaving the unit: this edge is not walked
                edges.add((current, successor))
                if successor not in reached and successor != start_id:
                    reached.add(successor)
                    next_frontier.append(successor)
        frontier = next_frontier
    return reached, frozenset(edges)


# --- UPSTREAM_SOURCES ------------------------------------------------------------------------


def upstream_sources_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per item that has at least one source (nothing flows into it) upstream."""
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for item_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        feeds = _upstream_tree(plant, item_id)
        sources = [n for n in feeds if not send_to_predecessors(plant, n)]
        if not sources:
            continue
        tag = str(plant.nodes[item_id]["tag"])
        evidence = Evidence(
            nodes=frozenset({item_id, *feeds}),
            edges=frozenset((ancestor, fed) for ancestor, fed in feeds.items()),
        )
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.UPSTREAM_SOURCES,
                template_id="UPSTREAM_SOURCES",
                template_version=_TEMPLATE_VERSION,
                text=upstream_sources_text(tag),
                answer_type=AnswerType.TAG_SET,
                reference=sorted(str(plant.nodes[n]["tag"]) for n in sources),
                evidence=evidence,
                anchors=[tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


def _upstream_tree(plant: nx.DiGraph[str], start_id: str) -> dict[str, str]:
    """Breadth-first tree over `send_to` backwards: each ancestor -> the node it feeds in the tree.

    The start is not a key. A node first met in a layer keeps the first parent in id order, so
    the tree (and so the evidence and `k`) does not depend on iteration order.
    """
    feeds: dict[str, str] = {}
    frontier = [start_id]
    while frontier:
        found: dict[str, str] = {}
        for current in frontier:
            for predecessor in send_to_predecessors(plant, current):
                if predecessor != start_id and predecessor not in feeds:
                    found.setdefault(predecessor, current)
        feeds.update(found)
        frontier = sorted(found)
    return feeds
