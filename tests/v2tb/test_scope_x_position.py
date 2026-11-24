"""POSITION_OF_VALVE by tag or descriptor (design `v2t-b` §10 R11), on the hand-built toy plant."""

from __future__ import annotations

import re

import pytest
from scope_x_toy import POSITIONS, toy_manifest, toy_plant, toy_sheets

from plantgraph.graph.schema import VALVE_CLASSES
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.scope_x import scope_x_candidates
from plantgraph.qa.questions.scope_x_models import FamilyOutcome, NamedBy
from plantgraph.qa.questions.templates_x import (
    class_words,
    position_of_described_valve_text,
    position_of_valve_text,
)
from plantgraph.qa.v2tb.descriptor import fold_class
from plantgraph.qa.v2tb.visible import POSITION_CODES

_FAMILY = QuestionFamily.POSITION_OF_VALVE
#: a purpose word names a valve's role, and the role decides its position (design `v2t-b` §10 P1)
_ROLE_WORDS = {
    "vent", "drain", "bleed", "flush", "bypass", "block", "root", "manifold", "suction",
    "discharge", "inlet", "outlet", "fill", "makeup",
}  # fmt: skip
_ANSWER_WORDS = {code.lower() for code in POSITION_CODES} | {"open", "closed"}


def _position() -> FamilyOutcome:
    plant = toy_plant()
    return scope_x_candidates(
        plant,
        toy_manifest(),
        toy_sheets(plant),
        POSITIONS,
        corpus_id="TOY",
        seed=1,
        families=(_FAMILY,),
    )[_FAMILY]


def _question_for(outcome: FamilyOutcome, anchor: str) -> Question:
    return next(q for q in outcome.kept if q.anchors == [anchor])


def test_an_untagged_valve_is_named_by_its_descriptor_and_anchored_on_next_to() -> None:
    question = _question_for(_position(), "TK-1")

    assert question.text == (
        'What is the normal operating position of the gate valve on line 6"-P-1203-A1A, '
        "on the upstream side of TK-1?"
    )
    assert question.reference == "NO"
    assert question.anchors == ["TK-1"]


def test_the_descriptor_question_carries_the_walk_between_valve_and_next_to_as_evidence() -> None:
    question = _question_for(_position(), "TK-1")

    assert set(question.evidence_tags) == {"TK-1"}  # the valve ga itself prints no tag


def test_named_by_says_tag_or_descriptor_and_the_report_counts_follow() -> None:
    outcome = _position()
    forms = {q.anchors[0]: outcome.flags[q.question_id].named_by for q in outcome.kept}

    assert forms == {
        "TK-1": NamedBy.DESCRIPTOR,
        "HV-2": NamedBy.TAG,
        "HV-5A": NamedBy.TAG,
        "HV-5B": NamedBy.TAG,
    }
    assert outcome.flags[_question_for(outcome, "TK-1").question_id].holds_untagged


def test_question_ids_stay_distinct_when_two_valves_share_a_next_to() -> None:
    outcome = _position()
    ids = [q.question_id for q in outcome.kept]

    assert len(ids) == len(set(ids))
    assert "TOY:POSITION_OF_VALVE:HV-2" in ids


def test_the_tag_text_is_the_registered_one() -> None:
    assert position_of_valve_text("HV-2") == "What is the normal operating position of valve HV-2?"


@pytest.mark.parametrize("class_name", sorted(VALVE_CLASSES))
def test_class_words_are_lower_case_words_that_fold_back_to_the_class(class_name: str) -> None:
    words = class_words(class_name)

    assert words == words.lower()
    assert fold_class(words) == fold_class(class_name)


def test_class_words_split_a_camel_case_class() -> None:
    assert class_words("GateValve") == "gate valve"
    assert class_words("SpringLoadedGlobeSafetyValve") == "spring loaded globe safety valve"


def test_the_fixed_words_hold_no_position_code_and_no_role_word() -> None:
    texts = [position_of_valve_text("X-1")] + [
        position_of_described_valve_text(cls, "L-1", side, "X-1")
        for cls in sorted(VALVE_CLASSES)
        for side in ("upstream", "downstream")
    ]
    for text in texts:
        words = set(re.findall(r"[a-z]+", text.lower()))
        assert not words & _ANSWER_WORDS, text
        assert not words & _ROLE_WORDS, text
