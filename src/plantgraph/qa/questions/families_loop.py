"""LOOP_ACTUATED_VALVE and LOOP_MEASURED_EQUIPMENT: control-loop questions (design §9).

A **control loop** is drawn as a short instrument chain, not a single
symbol: a sensor (`ProcessSignalGeneratingFunction`) reports a measured
variable to a controller (`ProcessInstrumentationFunction`), which drives an
actuator (`ActuatingFunction`) that moves a valve. `loop_tag` is the
controller's own printed tag (`tests/graph_plant_builder.py`) — the label a
P&ID actually shows next to the loop — so a question names the loop by that,
not by any node's internal id.

A v2 plant also draws loops that are not a full chain: an indicator with no valve, a trip, a hand
switch, a cascade (a master controller feeding a slave controller), a sensor on a pipe instead of
on equipment. Each family below only takes the loops its question is about; the others are skipped.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, NodeClass, Relation, labels_for
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import (
    build_question,
    relation_predecessors,
    relation_successors,
    single_successor,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex

_TEMPLATE_VERSION = "1"


def loop_actuated_valve_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per control loop: which valve its actuator drives.

    Reference path: controller `-send_signal_to->` actuator `-control->` valve.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for pif_id, loop_tag in _controllers_by_tag(plant):
        af_ids = _successors_of_class(plant, pif_id, NodeClass.ACTUATING_FUNCTION)
        if len(af_ids) != 1:
            continue  # an indicator, a trip or a hand switch (no valve), or a split-range pair
        af_id = af_ids[0]
        valve_id = single_successor(
            plant, af_id, Relation.CONTROL, context=f"actuator of loop {loop_tag}"
        )
        evidence = Evidence(
            nodes=frozenset({pif_id, af_id, valve_id}),
            edges=frozenset({(pif_id, af_id), (af_id, valve_id)}),
        )
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.LOOP_ACTUATED_VALVE,
                template_id="LOOP_ACTUATED_VALVE",
                template_version=_TEMPLATE_VERSION,
                text=f"Which valve is actuated by control loop {loop_tag}?",
                answer_type=AnswerType.TAG,
                reference=str(plant.nodes[valve_id]["tag"]),
                evidence=evidence,
                anchors=[loop_tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


def loop_measured_equipment_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per control loop: which equipment item its sensor measures.

    Reference path: equipment `-measured_by->` sensor `-send_signal_to->` controller.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    questions = []
    for pif_id, loop_tag in _controllers_by_tag(plant):
        psgf_ids = _predecessors_of_class(
            plant, pif_id, NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION
        )
        if len(psgf_ids) != 1:
            continue  # a slave also has its master as predecessor; a hand switch has no sensor
        psgf_id = psgf_ids[0]
        equipment_ids = [
            n
            for n in relation_predecessors(plant, psgf_id, Relation.MEASURED_BY)
            if plant.nodes[n]["node_class"] in EQUIPMENT_CLASSES
        ]
        if len(equipment_ids) != 1:
            continue  # the sensor sits on a pipe or valve, not on an equipment item
        equipment_id = equipment_ids[0]
        evidence = Evidence(
            nodes=frozenset({equipment_id, psgf_id, pif_id}),
            edges=frozenset({(equipment_id, psgf_id), (psgf_id, pif_id)}),
        )
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.LOOP_MEASURED_EQUIPMENT,
                template_id="LOOP_MEASURED_EQUIPMENT",
                template_version=_TEMPLATE_VERSION,
                text=f"Which equipment item does control loop {loop_tag} measure?",
                answer_type=AnswerType.TAG,
                reference=str(plant.nodes[equipment_id]["tag"]),
                evidence=evidence,
                anchors=[loop_tag],
                plant=plant,
                index=index,
                seed=seed,
            )
        )
    return questions


def _controllers_by_tag(plant: nx.DiGraph[str]) -> list[tuple[str, str]]:
    """Every controller node as `(node_id, loop_tag)`.

    A controller is a `ProcessInstrumentationFunction` or a cascade `ProcessControlFunction`;
    the label chain (which lists both) tells them from every other node.
    """
    controller_label = NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value
    return sorted(
        (node_id, str(data["tag"]))
        for node_id, data in plant.nodes(data=True)
        if controller_label in labels_for(data["node_class"])
    )


def _successors_of_class(plant: nx.DiGraph[str], node_id: str, node_class: NodeClass) -> list[str]:
    signal_targets = relation_successors(plant, node_id, Relation.SEND_SIGNAL_TO)
    return [n for n in signal_targets if plant.nodes[n]["node_class"] == node_class.value]


def _predecessors_of_class(
    plant: nx.DiGraph[str], node_id: str, node_class: NodeClass
) -> list[str]:
    signal_sources = relation_predecessors(plant, node_id, Relation.SEND_SIGNAL_TO)
    return [n for n in signal_sources if plant.nodes[n]["node_class"] == node_class.value]
