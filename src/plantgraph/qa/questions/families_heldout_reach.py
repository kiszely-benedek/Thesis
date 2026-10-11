"""Held-out families that read a whole downstream or unit-level slice of the plant (EXP-0006).

- `DOWNSTREAM_ISOLATION`: the mirror of `UPSTREAM_ISOLATION`, walking `send_to` forwards.
- `FEEDING_UNITS`: the mirror of `CROSS_UNIT`, looking at who sends flow *into* a unit.
- `UNITS_REACHED`: how many other units the flow leaving an item passes through.

A **unit** is a named group of equipment operated together (`unit_id`). Like every family,
these read only `tag`, `node_class`, `unit_id` and the `send_to` edges of the ground-truth plant.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, OPERATED_VALVE_CLASSES, Relation
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import (
    build_question,
    nodes_of_classes,
    send_to_successors,
    unit_of,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.templates_heldout import (
    downstream_isolation_text,
    feeding_units_text,
    units_reached_text,
)

_TEMPLATE_VERSION = "1"


def _tags(plant: nx.DiGraph[str], node_ids: set[str] | frozenset[str]) -> list[str]:
    return sorted(str(plant.nodes[node_id]["tag"]) for node_id in node_ids)


# --- DOWNSTREAM_ISOLATION --------------------------------------------------------------------


def _downstream_walk(
    plant: nx.DiGraph[str], start_id: str
) -> tuple[frozenset[str], frozenset[tuple[str, str]]] | None:
    """Walk `send_to` forwards: `(valves to close, edges walked)`, or `None` if a route has none.

    On each route the valve to close is the first operated valve (globe or ball). A check
    valve is passed through. `None` means some route ends at a node with nothing downstream
    before meeting an operated valve. The `seen` set stops the walk at cycles.
    """
    valves: set[str] = set()
    edges: set[tuple[str, str]] = set()
    seen = {start_id}
    frontier = [start_id]
    while frontier:
        next_frontier: list[str] = []
        for current in frontier:
            downstream = send_to_successors(plant, current)
            if not downstream:
                return None  # a route with nothing on it to close
            edges.update((current, successor) for successor in downstream)
            next_frontier += _classify_downstream(plant, downstream, valves, seen)
        frontier = next_frontier
    return frozenset(valves), frozenset(edges)


def _classify_downstream(
    plant: nx.DiGraph[str], downstream: list[str], valves: set[str], seen: set[str]
) -> list[str]:
    """Collect operated valves into `valves`; return the unseen other nodes to keep walking from."""
    keep_walking = []
    for node_id in downstream:
        if plant.nodes[node_id]["node_class"] in OPERATED_VALVE_CLASSES:
            valves.add(node_id)
        elif node_id not in seen:
            keep_walking.append(node_id)
        seen.add(node_id)
    return keep_walking


def downstream_isolation_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per equipment item whose every downstream route meets an operated valve."""
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for node_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        walk = _downstream_walk(plant, node_id)
        if walk is None:
            continue
        valves, edges = walk
        tag = str(plant.nodes[node_id]["tag"])
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.DOWNSTREAM_ISOLATION,
                template_id="DOWNSTREAM_ISOLATION",
                template_version=_TEMPLATE_VERSION,
                text=downstream_isolation_text(tag),
                answer_type=AnswerType.TAG_SET,
                reference=_tags(plant, valves),
                evidence=Evidence(
                    nodes=frozenset({node_id, *(n for edge in edges for n in edge)}), edges=edges
                ),
                anchors=[tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


# --- FEEDING_UNITS ---------------------------------------------------------------------------


def _edges_entering_units(plant: nx.DiGraph[str]) -> dict[str, list[tuple[str, str]]]:
    """For each unit, the `send_to` edges that come into it from a different unit."""
    entering: dict[str, list[tuple[str, str]]] = {}
    send_to_edges = sorted(
        (u, v) for u, v, d in plant.edges(data=True) if d["relation"] == Relation.SEND_TO.value
    )
    for source_id, target_id in send_to_edges:
        source_unit, target_unit = unit_of(plant, source_id), unit_of(plant, target_id)
        if source_unit is not None and target_unit is not None and source_unit != target_unit:
            entering.setdefault(target_unit, []).append((source_id, target_id))
    return entering


def feeding_units_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per unit that receives flow from another unit (an empty answer is skipped)."""
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for unit_id, edges in sorted(_edges_entering_units(plant).items()):
        feeding = {unit_of(plant, source_id) for source_id, _ in edges}
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.FEEDING_UNITS,
                template_id="FEEDING_UNITS",
                template_version=_TEMPLATE_VERSION,
                text=feeding_units_text(unit_id),
                answer_type=AnswerType.UNIT_SET,
                reference=sorted(str(unit) for unit in feeding),
                evidence=Evidence(
                    nodes=frozenset(n for edge in edges for n in edge), edges=frozenset(edges)
                ),
                anchors=[unit_id],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


# --- UNITS_REACHED ---------------------------------------------------------------------------


def _descendant_tree(plant: nx.DiGraph[str], start_id: str) -> dict[str, str]:
    """Breadth-first tree over `send_to`: each descendant -> the node it was first reached from.

    The start is not a key. Frontiers and successors are visited in sorted node-id order, so
    the tree (and with it the evidence and `k`) never depends on iteration order.
    """
    parent_of: dict[str, str] = {}
    frontier = [start_id]
    while frontier:
        found: dict[str, str] = {}
        for current in frontier:
            for successor in send_to_successors(plant, current):
                if successor != start_id and successor not in parent_of:
                    found.setdefault(successor, current)
        parent_of.update(found)
        frontier = sorted(found)
    return parent_of


def units_reached_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per equipment item with at least one descendant; the answer may be 0."""
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for node_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        parent_of = _descendant_tree(plant, node_id)
        if not parent_of:
            continue
        own_unit = unit_of(plant, node_id)
        other_units = {unit_of(plant, n) for n in parent_of} - {own_unit, None}
        tag = str(plant.nodes[node_id]["tag"])
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.UNITS_REACHED,
                template_id="UNITS_REACHED",
                template_version=_TEMPLATE_VERSION,
                text=units_reached_text(tag),
                answer_type=AnswerType.COUNT,
                reference=len(other_units),
                evidence=Evidence(
                    nodes=frozenset({node_id, *parent_of}),
                    edges=frozenset((parent, child) for child, parent in parent_of.items()),
                ),
                anchors=[tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions
