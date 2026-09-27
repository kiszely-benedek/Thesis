"""Programmatic scoring: exact match, set F1, path validity, abstention (ADR-0013, §9, §11).

Table-driven per `qa-system.md` §18 QA-T5's acceptance check: case and
whitespace, empty set, duplicates, the `UNIT` prefix, a path with connector
tags, an invalid path, correct and false abstention, and a parse failure.
"""

from __future__ import annotations

import pytest

from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome, Question, QuestionFamily
from plantgraph.qa.scoring import (
    ScoredAnswer,
    normalize_scalar,
    normalize_unit_id,
    score_abstention,
    score_answer,
    score_count,
    score_path,
    score_scalar,
    score_set,
    score_unit_id,
)


def _question(**overrides: object) -> Question:
    defaults: dict[str, object] = {
        "question_id": "q-0001",
        "corpus_id": "plant0",
        "family": QuestionFamily.LOOKUP_TYPE,
        "template_id": "lookup_type.v1",
        "template_version": "1",
        "text": "irrelevant to scoring",
        "answer_type": AnswerType.CLASS_NAME,
        "answerable": True,
        "reference": "Pump",
        "generator_seed": 0,
    }
    defaults.update(overrides)
    return Question.model_validate(defaults)


# --- case and whitespace normalization -------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("P-101", "P-101"),
        ("  p-101  ", "P-101"),
        ("p-101\n", "P-101"),
        ("p -  101", "P - 101"),  # internal runs collapse to one space, not to nothing
    ],
)
def test_normalize_scalar_folds_case_and_whitespace(value: str, expected: str) -> None:
    assert normalize_scalar(value) == expected


@pytest.mark.parametrize(
    ("reference", "answer"),
    [("Pump", "PUMP"), ("Pump", "  pump "), ("P-101", "p-101")],
)
def test_score_scalar_ignores_case_and_surrounding_whitespace(reference: str, answer: str) -> None:
    assert score_scalar(reference, answer) is True


def test_score_scalar_rejects_a_genuinely_different_value() -> None:
    assert score_scalar("Pump", "Valve") is False


# --- the UNIT prefix ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", "12"), ("unit 12", "12"), ("UNIT12", "12"), ("U12", "12"), ("U 12", "12")],
)
def test_normalize_unit_id_strips_a_leading_unit_label(value: str, expected: str) -> None:
    assert normalize_unit_id(value) == expected


def test_normalize_unit_id_leaves_a_unit_actually_named_u_alone() -> None:
    # the U/UNIT prefix is only a label when followed by a digit (a real unit
    # number); a unit literally called "U" or "Unicorn" must not be mangled.
    assert normalize_unit_id("U") == "U"
    assert normalize_unit_id("Unicorn") == "UNICORN"


def test_score_unit_id_matches_a_labelled_and_an_unlabelled_answer() -> None:
    assert score_unit_id("12", "unit 12") is True
    assert score_unit_id("12", "13") is False


# --- COUNT: integer equality, numeric strings accepted ------------------------------------


@pytest.mark.parametrize(("reference", "answer"), [(3, 3), (3, "3"), (0, "0"), (0, 0)])
def test_score_count_accepts_int_or_numeric_string(reference: int, answer: int | str) -> None:
    assert score_count(reference, answer) is True


def test_score_count_rejects_a_wrong_number() -> None:
    assert score_count(3, 4) is False


def test_score_count_rejects_a_non_numeric_string() -> None:
    assert score_count(3, "three") is False


# --- sets: empty, duplicates, exact-set as the strict variant -----------------------------


def test_score_set_two_empty_sets_are_a_perfect_match() -> None:
    result = score_set([], [])

    assert result.correct is True
    assert (result.precision, result.recall, result.f1) == (1.0, 1.0, 1.0)


def test_score_set_empty_reference_with_a_spurious_answer_is_wrong() -> None:
    result = score_set([], ["P-101"])

    assert result.correct is False
    assert result.precision == 0.0


def test_score_set_duplicates_collapse_before_comparison() -> None:
    result = score_set(["P-101", "P-101", "V-1"], ["v-1", "p-101"])

    assert result.correct is True
    assert (result.precision, result.recall, result.f1) == (1.0, 1.0, 1.0)


def test_score_set_partial_overlap_is_lenient_but_not_correct() -> None:
    result = score_set(["P-101", "V-1"], ["P-101"])

    assert result.correct is False
    assert result.precision == 1.0  # everything answered was right...
    assert result.recall == 0.5  # ...but half the reference set was missed
    assert 0.0 < result.f1 < 1.0


def test_score_set_unit_id_normalization_strips_the_unit_prefix() -> None:
    result = score_set(["12", "7"], ["UNIT 12", "unit7"], normalize="unit_id")

    assert result.correct is True


# --- paths: connector tags, an invalid path ------------------------------------------------


def test_score_path_accepts_a_connector_tag_inside_the_answer() -> None:
    # The model was told to omit connectors but includes one anyway; it
    # should be stripped, not treated as a wrong or a missing tag.
    result = score_path(
        reference_path=["P-101", "V-1", "T-1"],
        answer_path=["P-101", "SHEET-2-OPC-01", "V-1", "T-1"],
        connector_tags=["SHEET-2-OPC-01"],
        valid_edges=[("P-101", "V-1"), ("V-1", "T-1")],
    )

    assert result.correct is True
    assert result.f1 == 1.0


def test_score_path_rejects_an_edge_that_is_not_in_the_ground_truth() -> None:
    result = score_path(
        reference_path=["P-101", "V-1", "T-1"],
        answer_path=["P-101", "T-1"],  # skips V-1: (P-101, T-1) is not a real edge
        connector_tags=[],
        valid_edges=[("P-101", "V-1"), ("V-1", "T-1")],
    )

    assert result.correct is False


def test_score_path_rejects_wrong_endpoints_even_with_only_real_edges() -> None:
    result = score_path(
        reference_path=["P-101", "V-1", "T-1"],
        answer_path=["V-1", "T-1"],  # real edge, but does not start at P-101
        connector_tags=[],
        valid_edges=[("P-101", "V-1"), ("V-1", "T-1")],
    )

    assert result.correct is False


def test_score_path_f1_is_lenient_even_when_the_path_is_invalid() -> None:
    result = score_path(
        reference_path=["P-101", "V-1", "T-1"],
        answer_path=["P-101", "T-1"],  # invalid, but 2 of 3 reference tags present
        connector_tags=[],
        valid_edges=[("P-101", "V-1"), ("V-1", "T-1")],
    )

    assert result.correct is False
    assert 0.0 < result.f1 < 1.0


# --- abstention: correct and false ----------------------------------------------------------


def test_score_abstention_correct_on_an_unanswerable_question() -> None:
    assert score_abstention(answerable=False, not_present=True) is True


def test_score_abstention_wrong_when_an_unanswerable_question_is_answered_anyway() -> None:
    assert score_abstention(answerable=False, not_present=False) is False


def test_score_abstention_false_abstention_on_an_answerable_question() -> None:
    # the model claims the information is missing when it is not present in
    # the graph at all: always wrong, regardless of the `answer` field.
    assert score_abstention(answerable=True, not_present=True) is False


def test_score_abstention_correct_when_an_answerable_question_is_answered() -> None:
    assert score_abstention(answerable=True, not_present=False) is True


# --- score_answer: outcome dispatch, including parse failure --------------------------------


def test_score_answer_parse_failure_is_wrong_with_no_lenient_score() -> None:
    question = _question()

    result = score_answer(question, Outcome.PARSE_FAILURE, final_answer=None)

    assert result == ScoredAnswer(correct=False, f1=None)


@pytest.mark.parametrize(
    "outcome", [Outcome.DID_NOT_FIT, Outcome.RETRIEVAL_ERROR, Outcome.PROVIDER_ERROR]
)
def test_score_answer_every_non_answered_outcome_is_wrong(outcome: Outcome) -> None:
    result = score_answer(_question(), outcome, final_answer=None)

    assert result.correct is False
    assert result.f1 is None


def test_score_answer_answered_without_a_final_answer_is_a_contract_error() -> None:
    with pytest.raises(ValueError, match="final_answer is None"):
        score_answer(_question(), Outcome.ANSWERED, final_answer=None)


def test_score_answer_class_name_exact_match() -> None:
    question = _question(answer_type=AnswerType.CLASS_NAME, reference="Pump")

    result = score_answer(question, Outcome.ANSWERED, FinalAnswer(answer="pump", not_present=False))

    assert result == ScoredAnswer(correct=True, f1=None)


def test_score_answer_tag_set_uses_the_strict_exact_set() -> None:
    question = _question(answer_type=AnswerType.TAG_SET, reference=["P-101", "V-1"])
    partial = FinalAnswer(answer=["P-101"], not_present=False)

    result = score_answer(question, Outcome.ANSWERED, partial)

    assert result.correct is False
    assert result.f1 is not None and 0.0 < result.f1 < 1.0


def test_score_answer_tag_path_end_to_end() -> None:
    question = _question(answer_type=AnswerType.TAG_PATH, reference=["P-101", "V-1", "T-1"])
    answer = FinalAnswer(answer=["P-101", "V-1", "T-1"], not_present=False)

    result = score_answer(
        question,
        Outcome.ANSWERED,
        answer,
        valid_edges=[("P-101", "V-1"), ("V-1", "T-1")],
    )

    assert result == ScoredAnswer(correct=True, f1=1.0)


def test_score_answer_false_abstention_on_an_answerable_question() -> None:
    question = _question(answer_type=AnswerType.CLASS_NAME, reference="Pump")
    abstained = FinalAnswer(answer=None, not_present=True)

    result = score_answer(question, Outcome.ANSWERED, abstained)

    assert result == ScoredAnswer(correct=False, f1=None)


def test_score_answer_correct_abstention_on_an_unanswerable_question() -> None:
    question = _question(
        family=QuestionFamily.UNANSWERABLE_TAG,
        answer_type=AnswerType.TAG,
        answerable=False,
        reference=None,
    )
    abstained = FinalAnswer(answer=None, not_present=True)

    result = score_answer(question, Outcome.ANSWERED, abstained)

    assert result == ScoredAnswer(correct=True, f1=None)


def test_score_answer_free_text_is_not_scored_here() -> None:
    # EXP-0001's rubric-judged answers go through judge.py, not scoring.py.
    question = _question(answer_type=AnswerType.FREE_TEXT, reference="a free-text reference")
    answer = FinalAnswer(answer="a free-text answer", not_present=False)

    with pytest.raises(ValueError, match="FREE_TEXT"):
        score_answer(question, Outcome.ANSWERED, answer)
