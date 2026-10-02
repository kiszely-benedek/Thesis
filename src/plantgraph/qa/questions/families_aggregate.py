"""CROSS_UNIT and COUNT_IN_UNIT: questions about a whole unit rather than one item (design §9).

A **unit** is a named group of equipment operated together; every plant node
carries its `unit_id`. Both families read only `unit_id`, `node_class` and
the `send_to` edges between nodes.
"""

from __future__ import annotations

import re
from collections import Counter

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, VALVE_CLASSES, Relation
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question, unit_of
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.templates import count_in_unit_text, cross_unit_text

_TEMPLATE_VERSION = "1"

#: Only classes that sit on `send_to` edges are counted: instrumentation is
#: wired by signal edges, so "the unit-induced `send_to` subgraph" (the
#: evidence the design names) would not contain it.
COUNTED_CLASSES: frozenset[str] = EQUIPMENT_CLASSES | VALVE_CLASSES

# `HeatExchanger` -> `Heat`, `Exchanger`: the boundary is a lowercase-to-uppercase step.
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])")


def class_plural(node_class: str) -> str:
    """`"GlobeValve"` -> `"globe valves"`: the phrase a COUNT_IN_UNIT question uses."""
    return " ".join(_CAMEL_BOUNDARY.split(node_class)).lower() + "s"


def _send_to_edges(plant: nx.DiGraph[str]) -> list[tuple[str, str]]:
    """Every `send_to` edge, sorted so enumeration order never depends on networkx."""
    return sorted(
        (u, v)
        for u, v, data in plant.edges(data=True)
        if data["relation"] == Relation.SEND_TO.value
    )


def cross_unit_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per unit that sends flow directly to at least one other unit.

    A unit with no outgoing cross-unit edge has an empty answer; such a
    question tests nothing a strategy could get wrong, so it is skipped.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    leaving: dict[str, list[tuple[str, str]]] = {}
    for source_id, target_id in _send_to_edges(plant):
        source_unit, target_unit = unit_of(plant, source_id), unit_of(plant, target_id)
        if source_unit is not None and target_unit is not None and source_unit != target_unit:
            leaving.setdefault(source_unit, []).append((source_id, target_id))
    return [
        _cross_unit_question(plant, index, unit_id, edges, corpus_id=corpus_id, seed=seed)
        for unit_id, edges in sorted(leaving.items())
    ]


def _cross_unit_question(
    plant: nx.DiGraph[str],
    index: SheetIndex,
    unit_id: str,
    edges: list[tuple[str, str]],
    *,
    corpus_id: str,
    seed: int,
) -> Question:
    evidence = Evidence(
        nodes=frozenset(node_id for edge in edges for node_id in edge), edges=frozenset(edges)
    )
    receiving_units = {unit_of(plant, target_id) for _, target_id in edges}
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.CROSS_UNIT,
        template_id="CROSS_UNIT",
        template_version=_TEMPLATE_VERSION,
        text=cross_unit_text(unit_id),
        answer_type=AnswerType.UNIT_SET,
        reference=sorted(str(unit) for unit in receiving_units),
        evidence=evidence,
        anchors=[unit_id],
        plant=plant,
        index=index,
        seed=seed,
    )


def count_in_unit_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per `(unit, class)` pair that has at least one counted node."""
    index = SheetIndex.from_sheets(sheets, manifest)
    counted = _counted_nodes_by_unit(plant)
    questions = []
    for unit_id, node_ids in sorted(counted.items()):
        evidence = _unit_evidence(plant, unit_id, node_ids)
        class_counts = Counter(plant.nodes[node_id]["node_class"] for node_id in node_ids)
        for node_class, count in sorted(class_counts.items()):
            questions.append(
                build_question(
                    corpus_id=corpus_id,
                    family=QuestionFamily.COUNT_IN_UNIT,
                    template_id="COUNT_IN_UNIT",
                    template_version=_TEMPLATE_VERSION,
                    text=count_in_unit_text(class_plural(node_class), unit_id),
                    answer_type=AnswerType.COUNT,
                    reference=count,
                    evidence=evidence,
                    anchors=[unit_id, node_class],
                    plant=plant,
                    index=index,
                    seed=seed,
                )
            )
    return questions


def _counted_nodes_by_unit(plant: nx.DiGraph[str]) -> dict[str, list[str]]:
    by_unit: dict[str, list[str]] = {}
    for node_id in sorted(plant.nodes):
        unit_id = unit_of(plant, node_id)
        if unit_id is not None and plant.nodes[node_id]["node_class"] in COUNTED_CLASSES:
            by_unit.setdefault(unit_id, []).append(node_id)
    return by_unit


def _unit_evidence(plant: nx.DiGraph[str], unit_id: str, node_ids: list[str]) -> Evidence:
    """The unit-induced `send_to` subgraph: its counted nodes and the `send_to` edges among them."""
    members = set(node_ids)
    edges = frozenset((u, v) for u, v in _send_to_edges(plant) if u in members and v in members)
    return Evidence(nodes=frozenset(members), edges=edges)
