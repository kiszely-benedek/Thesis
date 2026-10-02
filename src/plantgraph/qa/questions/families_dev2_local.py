"""INSTRUMENTS_OF_ITEM, SAME_UNIT, LOOPS_NEAR_ITEM: dev-new families about one item's surroundings.

Design `question-aware-retrieval.md` §8.2. A **unit** is a named group of equipment; a
**control loop** is named by its controller's tag (see `families_loop.py`). As in
`families_dev2_reach.py`, an item is an equipment item and nothing reads an equipment attribute.
"""

from __future__ import annotations

import random

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, VALVE_CLASSES, Relation
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import (
    build_question,
    nodes_of_classes,
    relation_predecessors,
    relation_successors,
    send_to_predecessors,
    send_to_successors,
    unit_of,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.templates import (
    instruments_of_item_text,
    loops_near_item_text,
    same_unit_text,
)

_TEMPLATE_VERSION = "1"


# --- INSTRUMENTS_OF_ITEM ---------------------------------------------------------------------


def instruments_of_item_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per equipment item with at least one `measured_by` edge: its sensors."""
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for item_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        sensor_ids = relation_successors(plant, item_id, Relation.MEASURED_BY)
        if not sensor_ids:
            continue
        tag = str(plant.nodes[item_id]["tag"])
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.INSTRUMENTS_OF_ITEM,
                template_id="INSTRUMENTS_OF_ITEM",
                template_version=_TEMPLATE_VERSION,
                text=instruments_of_item_text(tag),
                answer_type=AnswerType.TAG_SET,
                reference=sorted(str(plant.nodes[s]["tag"]) for s in sensor_ids),
                evidence=Evidence(
                    nodes=frozenset({item_id, *sensor_ids}),
                    edges=frozenset((item_id, s) for s in sensor_ids),
                ),
                anchors=[tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


# --- SAME_UNIT -------------------------------------------------------------------------------


def same_unit_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """Per item: one partner from its own unit ("yes") and one from a flow-adjacent unit ("no").

    The "no" partner is drawn from a unit joined to this one by a `send_to` edge, so the answer
    is not given away by the units being far apart. Evidence is the two items alone (k = 0).
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    items_by_unit = _items_by_unit(plant)
    adjacent = _adjacent_units(plant)
    questions = []
    for item_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        unit_id = unit_of(plant, item_id)
        if unit_id is None:
            continue
        rng = random.Random(f"{seed}:SAME_UNIT:{item_id}")
        partners = _partners(item_id, unit_id, items_by_unit, adjacent, rng)
        for partner_id, reference in partners:
            questions.append(
                _same_unit_question(plant, index, item_id, partner_id, reference, corpus_id, seed)
            )
    return questions


def _items_by_unit(plant: nx.DiGraph[str]) -> dict[str, list[str]]:
    by_unit: dict[str, list[str]] = {}
    for item_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        unit_id = unit_of(plant, item_id)
        if unit_id is not None:
            by_unit.setdefault(unit_id, []).append(item_id)
    return by_unit


def _adjacent_units(plant: nx.DiGraph[str]) -> dict[str, list[str]]:
    """Unit -> the other units it shares a `send_to` edge with, in either direction, sorted."""
    pairs: dict[str, set[str]] = {}
    for source_id, target_id, data in plant.edges(data=True):
        if data["relation"] != Relation.SEND_TO.value:
            continue
        source_unit, target_unit = unit_of(plant, source_id), unit_of(plant, target_id)
        if source_unit is None or target_unit is None or source_unit == target_unit:
            continue
        pairs.setdefault(source_unit, set()).add(target_unit)
        pairs.setdefault(target_unit, set()).add(source_unit)
    return {unit: sorted(others) for unit, others in pairs.items()}


def _partners(
    item_id: str,
    unit_id: str,
    items_by_unit: dict[str, list[str]],
    adjacent: dict[str, list[str]],
    rng: random.Random,
) -> list[tuple[str, str]]:
    """`(partner id, reference)` for the "yes" partner and, when there is one, the "no" partner."""
    partners = []
    same_unit = [other for other in items_by_unit[unit_id] if other != item_id]
    if same_unit:
        partners.append((rng.choice(same_unit), "yes"))
    next_door = [
        other for unit in adjacent.get(unit_id, []) for other in items_by_unit.get(unit, [])
    ]
    if next_door:
        partners.append((rng.choice(next_door), "no"))
    return partners


def _same_unit_question(
    plant: nx.DiGraph[str],
    index: SheetIndex,
    item_id: str,
    partner_id: str,
    reference: str,
    corpus_id: str,
    seed: int,
) -> Question:
    first_tag, second_tag = str(plant.nodes[item_id]["tag"]), str(plant.nodes[partner_id]["tag"])
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.SAME_UNIT,
        template_id="SAME_UNIT",
        template_version=_TEMPLATE_VERSION,
        text=same_unit_text(first_tag, second_tag),
        answer_type=AnswerType.BOOLEAN,
        reference=reference,
        evidence=Evidence(nodes=frozenset({item_id, partner_id}), edges=frozenset()),
        anchors=[first_tag, second_tag],
        plant=plant,
        index=index,
        seed=seed,
    )


# --- LOOPS_NEAR_ITEM -------------------------------------------------------------------------


def loops_near_item_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per item next to at least one valve that a control loop actuates.

    Reference path: item `-send_to-` valve (either direction) `<-control-` actuator
    `<-send_signal_to-` controller; the answer is the controllers' tags.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for item_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        nodes, edges, loop_tags = _loops_around(plant, item_id)
        if not loop_tags:
            continue
        tag = str(plant.nodes[item_id]["tag"])
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.LOOPS_NEAR_ITEM,
                template_id="LOOPS_NEAR_ITEM",
                template_version=_TEMPLATE_VERSION,
                text=loops_near_item_text(tag),
                answer_type=AnswerType.TAG_SET,
                reference=sorted(loop_tags),
                evidence=Evidence(nodes=frozenset(nodes), edges=frozenset(edges)),
                anchors=[tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


def _loops_around(
    plant: nx.DiGraph[str], item_id: str
) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    """Evidence nodes, evidence edges and loop tags for the valves directly next to `item_id`."""
    nodes = {item_id}
    edges: set[tuple[str, str]] = set()
    loop_tags: set[str] = set()
    for valve_id, edge in _adjacent_valves(plant, item_id):
        for actuator_id, controller_id in _loop_chains(plant, valve_id):
            nodes |= {valve_id, actuator_id, controller_id}
            edges |= {edge, (actuator_id, valve_id), (controller_id, actuator_id)}
            loop_tags.add(str(plant.nodes[controller_id]["tag"]))
    return nodes, edges, loop_tags


def _loop_chains(plant: nx.DiGraph[str], valve_id: str) -> list[tuple[str, str]]:
    """`(actuator, controller)` for every control loop that moves `valve_id`."""
    return [
        (actuator_id, controller_id)
        for actuator_id in relation_predecessors(plant, valve_id, Relation.CONTROL)
        for controller_id in relation_predecessors(plant, actuator_id, Relation.SEND_SIGNAL_TO)
    ]


def _adjacent_valves(plant: nx.DiGraph[str], item_id: str) -> list[tuple[str, tuple[str, str]]]:
    """Valves one `send_to` edge from `item_id`, either direction, with that edge."""
    found = [(v, (item_id, v)) for v in send_to_successors(plant, item_id)]
    found += [(v, (v, item_id)) for v in send_to_predecessors(plant, item_id)]
    return [(v, edge) for v, edge in found if plant.nodes[v]["node_class"] in VALVE_CLASSES]
