"""`AnswerType.BOOLEAN`: yes/no scoring, parsing a JSON bool, and the final-step format line."""

from __future__ import annotations

import pytest

from plantgraph.llm.models import ModelPin
from plantgraph.qa.final_answer import (
    FinalAnswerParseError,
    parse_final_answer,
    render_final_answer_request,
)
from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome, Question, QuestionFamily
from plantgraph.qa.scoring import normalize_boolean, score_answer, score_boolean


def _question(reference: str = "yes") -> Question:
    return Question(
        question_id="c:CONNECTED:A|B",
        corpus_id="c",
        family=QuestionFamily.CONNECTED,
        template_id="CONNECTED",
        template_version="1",
        text="Can process flow reach B from A?",
        answer_type=AnswerType.BOOLEAN,
        answerable=True,
        reference=reference,
        generator_seed=0,
    )


def _score(reference: str, answer: str | int) -> bool:
    final = FinalAnswer(answer=answer, not_present=False)
    return score_answer(_question(reference), Outcome.ANSWERED, final).correct


@pytest.mark.parametrize("word", ["yes", "Yes", " YES ", "true", "True", "1"])
def test_every_spelling_of_yes_reads_as_true(word: str) -> None:
    assert normalize_boolean(word) is True


@pytest.mark.parametrize("word", ["no", "No", "false", "FALSE", "0"])
def test_every_spelling_of_no_reads_as_false(word: str) -> None:
    assert normalize_boolean(word) is False


def test_a_reply_that_is_neither_yes_nor_no_is_wrong_not_an_error() -> None:
    assert normalize_boolean("maybe") is None
    assert not _score("yes", "maybe")
    assert not _score("no", "maybe")


def test_scoring_compares_yes_and_no_after_normalising() -> None:
    assert _score("yes", "Yes")
    assert _score("yes", "true")
    assert _score("no", "no")
    assert _score("no", "False")
    assert not _score("yes", "no")
    assert not _score("no", "yes")


def test_a_json_bool_read_back_as_an_int_still_scores() -> None:
    assert _score("yes", 1)
    assert _score("no", 0)
    assert not _score("yes", 0)


def test_a_reference_that_is_not_yes_or_no_is_a_generator_bug() -> None:
    with pytest.raises(ValueError, match="yes/no BOOLEAN reference"):
        score_boolean("maybe", "yes")


def test_a_false_abstention_on_a_boolean_question_is_wrong() -> None:
    final = FinalAnswer(answer=None, not_present=True)

    assert not score_answer(_question("yes"), Outcome.ANSWERED, final).correct


def test_a_json_true_is_parsed_as_yes_not_as_the_integer_one() -> None:
    parsed = parse_final_answer('{"answer": true, "not_present": false}', AnswerType.BOOLEAN)

    assert parsed.answer == "yes"
    assert (
        parse_final_answer('{"answer": false, "not_present": false}', AnswerType.BOOLEAN).answer
        == "no"
    )


def test_a_yes_no_string_is_accepted_and_anything_else_is_a_parse_failure() -> None:
    assert (
        parse_final_answer('{"answer": "Yes", "not_present": false}', AnswerType.BOOLEAN).answer
        == "Yes"
    )
    for raw in (
        '{"answer": "maybe", "not_present": false}',
        '{"answer": ["yes"], "not_present": false}',
    ):
        with pytest.raises(FinalAnswerParseError):
            parse_final_answer(raw, AnswerType.BOOLEAN)


def test_a_json_bool_is_only_respelled_for_boolean_questions() -> None:
    # for a COUNT question `true` stays what pydantic makes of it, and the shape check rejects it
    # elsewhere; the respelling must not leak into other answer types
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer('{"answer": true, "not_present": false}', AnswerType.TAG_SET)


def test_the_final_step_tells_the_model_to_answer_yes_or_no() -> None:
    pin = ModelPin.model_validate(
        {
            "backend": "openrouter",
            "model_id": "openai/gpt-5-mini",
            "route_provider": "openai",
            "temperature": 0.0,
            "seed": 42,
            "max_output_tokens": 512,
            "extra": {},
        }
    )

    request = render_final_answer_request(
        pin=pin,
        context="ctx",
        question_text="Can flow reach B from A?",
        answer_type=AnswerType.BOOLEAN,
    )

    assert 'Answer with "yes" or "no".' in request.messages[0].content
