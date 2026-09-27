"""LOOP_ACTUATED_VALVE and LOOP_MEASURED_EQUIPMENT: control-loop questions (design §9).

A **control loop** is drawn as a short instrument chain, not a single
symbol: a sensor (`ProcessSignalGeneratingFunction`) reports a measured
variable to a controller (`ProcessInstrumentationFunction`), which drives an
actuator (`ActuatingFunction`) that moves a valve. `loop_tag` is the
controller's own printed tag (`tests/graph_plant_builder.py`) — the label a
P&ID actually shows next to the loop — so a question names the loop by that,
not by any node's internal id.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question, single_predecessor, single_successor
from plantgraph.qa.questions.evidence import Evidence, connector_cut

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
    cut = connector_cut(manifest)
    questions = []
    for pif_id, loop_tag in _controllers_by_tag(plant):
        af_id = single_successor(
            plant, pif_id, Relation.SEND_SIGNAL_TO, context=f"controller of loop {loop_tag}"
        )
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
                sheets=sheets,
                cut=cut,
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
    cut = connector_cut(manifest)
    questions = []
    for pif_id, loop_tag in _controllers_by_tag(plant):
        psgf_id = single_predecessor(
            plant, pif_id, Relation.SEND_SIGNAL_TO, context=f"sensor of loop {loop_tag}"
        )
        equipment_id = single_predecessor(
            plant, psgf_id, Relation.MEASURED_BY, context=f"measured equipment of loop {loop_tag}"
        )
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
                sheets=sheets,
                cut=cut,
                seed=seed,
            )
        )
    return questions


def _controllers_by_tag(plant: nx.DiGraph[str]) -> list[tuple[str, str]]:
    """Every controller node (one per control loop), as `(node_id, loop_tag)`."""
    return sorted(
        (node_id, str(data["tag"]))
        for node_id, data in plant.nodes(data=True)
        if data.get("node_class") == NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value
    )
