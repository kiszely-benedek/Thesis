"""ADR-0044: the valve a control loop operates carries the loop's `{var}V-u-n` tag.

The actuator carries none, the DEXPI `ActuatingSystem` carries the valve's number, and nothing
but tag strings changed (the topology digests below were recorded from the code at `8d00a17`).
"""

from __future__ import annotations

import hashlib
import re

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.benchmark.connectors import _signal_loop_tag
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig, control_valve_tag
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.graph.validation import validate_plant_graph
from plantgraph.qa.context_render import legend_text
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.canonical_programs import run_canonical_program
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.plant_api.item_graph import build_item_graph
from plantgraph.qa.questions.families import all_candidates
from plantgraph.resolution.localize import localize
from plantgraph.resolution.resolver import resolve
from topology_snapshot import headline_digest, small_seed_digest

_ACTUATOR = NodeClass.ACTUATING_FUNCTION.value
_PIF = NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value

#: Tag-blind topology digests recorded from the generator at HEAD `8d00a17`, before ADR-0044.
_GOLDEN_SMALL = {
    0: "f29dd72aec478974c5cbab6bb71f2b647c493045a1f0398955fdb1a5f2dd1007",
    1: "188b4b11633851d66e15cac0dfe447889e926f712bc479ce2ceeaeb52740812c",
    2: "50b764962c518e5cd4894655235de76fb108cfda42f84b11d29a41ca89aa12f9",
    3: "e025879e007ddeee8868ec05b98cecc30842bf5f738263cba5cec4ff0b00d9f5",
    4: "24c95f50666ca2b72c136c38240ca116ca1627bd70855b3d58fb0d2a95db687c",
}
_GOLDEN_HEADLINE_5_UNITS_SEED_1 = "a437a3c8e46891d0a0c07f05769f5b15fe6f949f5425b1f9ccdea97315298f40"


def _plant(seed: int) -> nx.DiGraph[str]:
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


def _control_edges(plant: nx.DiGraph[str]) -> list[tuple[str, str]]:
    return [(u, v) for u, v, d in plant.edges(data=True) if d["relation"] == Relation.CONTROL.value]


# ---- T-G1: only tag strings changed ----------------------------------------------------------


@pytest.mark.parametrize("seed", sorted(_GOLDEN_SMALL))
def test_node_ids_edges_and_sheets_equal_the_ones_before_the_renaming(seed: int) -> None:
    assert small_seed_digest(seed) == _GOLDEN_SMALL[seed]


def test_the_headline_preset_topology_equals_the_one_before_the_renaming() -> None:
    assert headline_digest(5, 1) == _GOLDEN_HEADLINE_5_UNITS_SEED_1


# ---- T-G2: the new naming ---------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(5))
def test_every_operated_valve_carries_its_loops_valve_tag_and_the_actuator_none(seed: int) -> None:
    plant = _plant(seed)
    edges = _control_edges(plant)

    assert edges, "the seed produced no control loop; pick another"
    for actuator_id, valve_id in edges:
        actuator = plant.nodes[actuator_id]
        variable, unit_no, loop_no = actuator["loop_tag"].split("-")  # e.g. FIC-30-6
        expected = control_valve_tag(variable[0], int(unit_no), int(loop_no))
        assert plant.nodes[valve_id]["tag"] == expected
        assert "tag" not in actuator
    tags = [data["tag"] for _, data in plant.nodes(data=True) if "tag" in data]
    assert len(tags) == len(set(tags))
    assert validate_plant_graph(plant) == []


def test_the_dexpi_actuating_system_number_is_the_valves_tag() -> None:
    generated = generate_plant(GeneratorConfig(seed=2))
    systems = generated.model.conceptualModel.actuatingSystems or []
    assert systems

    for system in systems:
        valve = system.operatedValveReference.valve
        assert re.fullmatch(r"[FLPT]V-\d+-\d+", system.actuatingSystemNumber or "")
        assert system.actuatingSystemNumber == valve.pipingComponentNumber


def test_the_dexpi_actuator_has_no_number() -> None:
    generated = generate_plant(GeneratorConfig(seed=2))
    functions = generated.model.conceptualModel.processInstrumentationFunctions or []
    actuators = [af for pif in functions for af in pif.actuatingFunctions or []]

    assert actuators
    assert [af.actuatingFunctionNumber for af in actuators] == [None] * len(actuators)


def test_control_valve_tag_is_the_one_formula() -> None:
    assert control_valve_tag("F", 30, 6) == "FV-30-6"


# ---- T-G3: signal connectors keep the controller's loop tag ----------------------------------


def test_a_signal_cut_between_actuator_and_valve_carries_the_controllers_loop_tag() -> None:
    plant = _plant(0)
    for actuator_id, valve_id in _control_edges(plant):
        controller_tags = {
            plant.nodes[n]["tag"]
            for n in plant.predecessors(actuator_id)
            if plant.nodes[n]["node_class"] == _PIF
        }
        assert _signal_loop_tag(plant, actuator_id, valve_id) in controller_tags


# ---- T-Q1..Q3: questions ----------------------------------------------------------------------


def _resolved_corpus(seed: int) -> tuple[nx.DiGraph[str], list[Question], NetworkxGraphView]:
    plant = _plant(seed)
    sheets, manifest = split(plant, SplitConfig(sheet_equipment_budget=2, seed=seed))
    localized, _ = localize(sheets)
    view = NetworkxGraphView("gen", localized, resolve(localized))
    by_family = all_candidates(plant, manifest, sheets, corpus_id="gen", seed=seed)
    return plant, [q for questions in by_family.values() for q in questions], view


def test_loop_actuated_valve_names_the_valve_by_the_loops_valve_tag() -> None:
    plant, questions, view = _resolved_corpus(3)
    loop_questions = [q for q in questions if q.family is QuestionFamily.LOOP_ACTUATED_VALVE]
    graph = build_item_graph(view)
    valve_tags = {plant.nodes[v]["tag"] for _, v in _control_edges(plant)}

    assert loop_questions
    for question in loop_questions:
        assert re.fullmatch(r"[FLPT]V-\d+-\d+", str(question.reference))
        assert question.reference in valve_tags
        assert question.text == f"Which valve is actuated by control loop {question.anchors[0]}?"
        assert run_canonical_program(graph, question) == question.reference


def test_no_question_names_an_untagged_node_and_lookup_type_never_answers_actuator() -> None:
    plant, questions, _ = _resolved_corpus(3)
    plant_tags = {data["tag"] for _, data in plant.nodes(data=True) if "tag" in data}

    for question in questions:
        if not question.answerable:
            continue  # an unanswerable question names an absent tag on purpose
        for named in _tags_named(question):
            assert named in plant_tags, f"{question.question_id}: {named!r} is not a plant tag"
        if question.family is QuestionFamily.LOOKUP_TYPE:
            assert question.reference != _ACTUATOR


def _tags_named(question: Question) -> list[str]:
    """Anchors that look like tags (a dash then a digit) plus the tags in a tag-typed reference."""
    named = [a for a in question.anchors if re.search(r"-\d", a) and not a.startswith("unit")]
    reference = question.reference
    if question.answer_type is AnswerType.TAG and isinstance(reference, str):
        named.append(reference)
    if question.answer_type in (AnswerType.TAG_SET, AnswerType.TAG_PATH):
        assert isinstance(reference, list)
        named.extend(reference)
    return named


def test_the_loop_valve_tag_is_the_controller_tag_with_ic_replaced_by_v() -> None:
    _, questions, _ = _resolved_corpus(4)
    loop_questions = [q for q in questions if q.family is QuestionFamily.LOOP_ACTUATED_VALVE]

    assert loop_questions
    for question in loop_questions:
        assert question.reference == question.anchors[0].replace("IC", "V")


# ---- T-P1: model-facing text ------------------------------------------------------------------

_HEAD_LEGEND_SHA256 = {
    "plant": "886067426812fd3f032c4fff8347dd5eb35cf263df489b3043ee334e6d6b9bc6",
    "occurrence": "e9645f097a03649bc742f43465987caf5b814c5d1c143dc0b32b9c80b4fa5d5e",
}
#: per representation: (the new wording, what it replaced)
_NEW_SENTENCE = {
    "plant": ("-control-> valve. Actuator nodes have no tag.", "-control-> valve."),
    "occurrence": ("Connector and actuator nodes have no tag.", "Connector nodes have no tag."),
}


@pytest.mark.parametrize("representation", ["plant", "occurrence"])
def test_a_legend_differs_from_the_one_before_by_the_one_actuator_sentence(
    representation: str,
) -> None:
    new, old = _NEW_SENTENCE[representation]
    text = legend_text(representation)  # type: ignore[arg-type]
    restored = text.replace(new, old) + "\n"

    assert new in text
    assert hashlib.sha256(restored.encode()).hexdigest() == _HEAD_LEGEND_SHA256[representation]
    assert "an actuator control the valve it moves" in text
