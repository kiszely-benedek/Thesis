"""Scope X gold (T15): references, refusals, positions, the A2 adapter, on a hand-built plant."""

from __future__ import annotations

import json

import pytest
from scope_x_toy import POSITIONS, toy_manifest, toy_plant, toy_sheets

from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.scope_x import (
    SCOPE_X_DEV_FAMILIES,
    SCOPE_X_FAMILIES,
    FamilyOutcome,
    RefusalReason,
    for_a2,
    scope_x_candidates,
)
from plantgraph.qa.questions.templates import upstream_isolation_text
from plantgraph.qa.questions.templates_heldout import downstream_isolation_text
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.scoring_b import reference_nodes

F = QuestionFamily


def _build(
    families: tuple[QuestionFamily, ...] = SCOPE_X_FAMILIES,
) -> dict[QuestionFamily, FamilyOutcome]:
    plant = toy_plant()
    return scope_x_candidates(
        plant,
        toy_manifest(),
        toy_sheets(plant),
        POSITIONS,
        corpus_id="TOY",
        seed=1,
        families=families,
    )


def _by_anchor(outcome: FamilyOutcome) -> dict[str, Question]:
    return {q.anchors[0]: q for q in outcome.kept}


def test_open_valves_drops_a_normally_closed_valve_that_the_isolation_family_keeps() -> None:
    outcomes = _build()
    open_up = _by_anchor(outcomes[F.OPEN_VALVES_TO_ISOLATE])
    isolation_up = _by_anchor(outcomes[F.UPSTREAM_ISOLATION_X])

    assert open_up["TK-5"].reference == ["HV-5A"]
    assert isolation_up["TK-5"].reference == ["HV-5A", "HV-5B"]
    assert open_up["TK-5"].answer_type is AnswerType.VALVE_SET


def test_the_discriminating_flag_marks_only_the_questions_the_positions_change() -> None:
    open_up = _build()[F.OPEN_VALVES_TO_ISOLATE]
    differs = {
        q.anchors[0]: open_up.flags[q.question_id].differs_from_topological for q in open_up.kept
    }

    assert differs == {"TK-1": False, "TK-5": True}


def test_an_open_valves_candidate_with_empty_gold_is_refused_and_counted() -> None:
    open_up = _build()[F.OPEN_VALVES_TO_ISOLATE]
    empty = [r for r in open_up.refusals if r.reason is RefusalReason.EMPTY_GOLD]

    assert [r.anchor for r in empty] == ["TK-2"]  # its only valve, HV-2, is normally closed
    assert open_up.candidates == 4  # TK-1, TK-2, TK-3, TK-5


def test_the_isolation_family_keeps_what_open_valves_refuses_for_an_empty_gold() -> None:
    isolation = _build()[F.UPSTREAM_ISOLATION_X]

    assert _by_anchor(isolation)["TK-2"].reference == ["HV-2"]


def test_two_same_class_valves_in_series_have_no_unique_descriptor_and_refuse_the_candidate() -> (
    None
):
    isolation = _build()[F.UPSTREAM_ISOLATION_X]
    refusal = next(r for r in isolation.refusals if r.anchor == "TK-3")

    assert refusal.reason is RefusalReason.NO_UNIQUE_DESCRIPTOR
    assert refusal.valve_ids == ("gd",)  # the valve nearest TK-3 is the one that cannot be named
    assert "TK-3" not in _by_anchor(isolation)


def test_the_downstream_walk_refuses_by_the_same_rule() -> None:
    downstream = _build()[F.DOWNSTREAM_ISOLATION_X]
    refusal = next(r for r in downstream.refusals if r.anchor == "SRC-3")

    assert refusal.valve_ids == ("gc",)


def test_an_untagged_valve_is_written_as_a_sorted_descriptor_string_that_resolves_to_it() -> None:
    isolation = _build()[F.UPSTREAM_ISOLATION_X]
    reference = _by_anchor(isolation)["TK-1"].reference

    assert isinstance(reference, list) and len(reference) == 1
    assert json.loads(reference[0]) == {
        "class": "GateValve",
        "line_number": '6"-P-1203-A1A',
        "next_to": "TK-1",
        "side": "upstream",
    }
    assert reference_nodes(PlantIndex(toy_plant()), reference) == {"ga"}  # the R8 self-test


def test_a_reference_is_sorted_and_the_flags_say_whether_the_gold_holds_an_untagged_valve() -> None:
    isolation = _build()[F.UPSTREAM_ISOLATION_X]
    flags = {q.anchors[0]: isolation.flags[q.question_id].holds_untagged for q in isolation.kept}

    assert flags == {"TK-1": True, "TK-2": False, "TK-5": False}
    for question in isolation.kept:
        assert question.reference == sorted(question.reference or [])


def test_every_candidate_is_kept_or_refused() -> None:
    for outcome in _build().values():
        assert outcome.candidates == len(outcome.kept) + len(outcome.refusals), outcome.family


def test_position_of_valve_asks_for_each_tagged_positioned_valve() -> None:
    position = _build()[F.POSITION_OF_VALVE]
    asked = {q.anchors[0]: q.reference for q in position.kept}

    assert asked == {"HV-2": "NC", "HV-5A": "NO", "HV-5B": "NC"}  # ga, gc, gd print no tag
    assert {q.answer_type for q in position.kept} == {AnswerType.POSITION}
    assert position.refusals == []
    assert position.kept[0].text == "What is the normal operating position of valve HV-2?"


def test_the_isolation_x_families_use_the_registered_texts() -> None:
    outcomes = _build()
    up = _by_anchor(outcomes[F.UPSTREAM_ISOLATION_X])["TK-5"]
    down = _by_anchor(outcomes[F.DOWNSTREAM_ISOLATION_X])["SRC-5"]

    assert up.text == upstream_isolation_text("TK-5")
    assert down.text == downstream_isolation_text("SRC-5")


def test_the_open_valves_texts_are_the_two_ruled_wordings() -> None:
    outcomes = _build()
    up = _by_anchor(outcomes[F.OPEN_VALVES_TO_ISOLATE])["TK-5"]
    down = _by_anchor(outcomes[F.OPEN_VALVES_TO_ISOLATE_DOWNSTREAM])["SRC-5"]

    assert up.text == (
        "To isolate TK-5 from all upstream equipment, which normally open valves must be closed?"
    )
    assert down.text == (
        "To cut SRC-5 off from all downstream equipment, which normally open valves must be closed?"
    )


def test_question_ids_are_distinct_across_the_families_of_one_plant() -> None:
    ids = [q.question_id for outcome in _build().values() for q in outcome.kept]

    assert len(ids) == len(set(ids))


def test_the_dev_families_can_be_built_without_the_sealed_ones() -> None:
    outcomes = _build(SCOPE_X_DEV_FAMILIES)

    assert tuple(outcomes) == SCOPE_X_DEV_FAMILIES


def test_a_family_outside_scope_x_is_refused() -> None:
    with pytest.raises(ValueError, match="expected scope X families"):
        _build((F.FLOW_PATH,))


def test_a_position_for_a_node_the_plant_lacks_is_refused() -> None:
    plant = toy_plant()
    with pytest.raises(ValueError, match="positioned valve"):
        scope_x_candidates(
            plant, toy_manifest(), toy_sheets(plant), {"ghost": "NO"}, corpus_id="T", seed=1
        )


def test_the_a2_adapter_retypes_the_question_and_keeps_the_reference() -> None:
    question = _by_anchor(_build()[F.UPSTREAM_ISOLATION_X])["TK-5"]
    adapted = for_a2(question)

    assert adapted.answer_type is AnswerType.TAG_SET
    assert adapted.reference == question.reference
    assert adapted.model_copy(update={"answer_type": AnswerType.VALVE_SET}) == question


def test_the_a2_adapter_is_not_given_a_position_question() -> None:
    position = _build()[F.POSITION_OF_VALVE].kept[0]

    with pytest.raises(ValueError, match="VALVE_SET question"):
        for_a2(position)
