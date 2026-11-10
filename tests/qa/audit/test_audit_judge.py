"""The blind judge prompt, its pin and its reply parser (F14)."""

from __future__ import annotations

import pytest

from audit_fakes import make_question, make_result, make_subgraph
from plantgraph.qa.audit.excerpt import render_excerpt
from plantgraph.qa.audit.judge import build_prompt, build_request, judge_pin, parse_reply
from plantgraph.qa.audit.models import JudgeInput, JudgeVerdict
from plantgraph.qa.audit.sources import make_judge_input
from plantgraph.qa.models import AnswerType, Outcome, QuestionResult

_EXCERPT = render_excerpt(make_subgraph("q"))


def _prompt_for(result: QuestionResult) -> str:
    question = make_question(1)
    return build_prompt(make_judge_input(question, result, _EXCERPT))


def test_judge_input_has_no_field_that_carries_the_scorers_verdict() -> None:
    assert set(JudgeInput.model_fields) == {
        "question_text",
        "answer_type",
        "raw_reply",
        "reference",
        "answerable",
        "plant_excerpt",
    }


def test_two_rows_differing_only_in_the_scorers_verdict_give_identical_prompts() -> None:
    question = make_question(1)
    right = make_result(question, correct=True)
    wrong = make_result(question, correct=False).model_copy(
        update={"f1": 0.25, "trace": {"scorer_note": "SCORER-SAYS-WRONG", "route_mode": "x"}}
    )

    assert _prompt_for(right) == _prompt_for(wrong)


def test_the_prompt_never_names_an_outcome_or_the_scoring_fields() -> None:
    question = make_question(1)
    parse_failure = make_result(
        question, correct=False, answer=None, outcome=Outcome.PARSE_FAILURE, raw_reply="Pump?"
    )
    prompts = [_prompt_for(make_result(question, correct=False)), _prompt_for(parse_failure)]

    for prompt in prompts:
        for outcome in Outcome:
            assert outcome.value not in prompt
        for field in ("scorer", "f1", '"correct": true', "correct=", "retrieval_usage"):
            assert field not in prompt


def test_the_prompt_labels_the_reference_as_possibly_wrong_and_holds_the_excerpt() -> None:
    prompt = _prompt_for(make_result(make_question(1)))

    assert "The benchmark's reference, which may be wrong:" in prompt
    assert "(untagged PipeTee #1)" in prompt
    assert "<<" not in prompt  # every placeholder was filled


def test_a_parse_failure_shows_its_raw_reply_and_nothing_about_how_it_was_read() -> None:
    question = make_question(1, answer_type=AnswerType.UNIT_SET)
    result = make_result(
        question, correct=False, answer=None, outcome=Outcome.PARSE_FAILURE, raw_reply="[1, 2]"
    )

    prompt = build_prompt(make_judge_input(question, result, _EXCERPT))

    assert "[1, 2]" in prompt
    assert "read from the reply" not in prompt and "no answer could" not in prompt
    assert "usable answer" not in prompt  # the judge decides from the reply text itself


def test_an_answered_row_and_a_parse_failure_with_the_same_reply_give_the_same_prompt() -> None:
    question = make_question(1)
    reply = '{"answer": "Pump", "not_present": false}'
    answered = make_result(question, correct=True)  # the run kept no reply, only the answer
    failed = make_result(
        question, correct=False, answer=None, outcome=Outcome.PARSE_FAILURE, raw_reply=reply
    )

    assert _prompt_for(answered) == _prompt_for(failed)
    assert reply in _prompt_for(answered)


def test_a_row_with_neither_reply_nor_answer_is_refused() -> None:
    question = make_question(1)
    result = make_result(question, correct=False, answer=None, outcome=Outcome.PARSE_FAILURE)

    with pytest.raises(ValueError, match="stored reply or a parsed answer"):
        make_judge_input(question, result, _EXCERPT)


def test_the_pin_is_the_paid04_sonnet_slug_at_low_reasoning() -> None:
    pin = judge_pin()

    assert pin.model_id == "anthropic/claude-sonnet-5.5"
    assert pin.extra == {"reasoning": {"effort": "low"}}
    assert pin.max_output_tokens == 2_048


def test_the_request_asks_for_json_and_is_labelled_a_judge_call() -> None:
    judge_input = make_judge_input(make_question(1), make_result(make_question(1)), _EXCERPT)

    request = build_request(judge_input)

    assert request.json_mode and request.purpose == "judge"


def test_parse_reply_reads_plain_and_fenced_json() -> None:
    body = '{"verdict": "ambiguous_question", "reference_ok": false, "reason": "two readings"}'

    assert parse_reply(body).verdict is JudgeVerdict.AMBIGUOUS_QUESTION
    assert parse_reply(f"```json\n{body}\n```").reason == "two readings"


def test_parse_reply_names_what_it_expected_when_the_reply_is_not_json() -> None:
    with pytest.raises(ValueError, match="verdict/reference_ok/reason"):
        parse_reply("I think it is right.")
    with pytest.raises(ValueError, match="verdict/reference_ok/reason"):
        parse_reply('{"verdict": "maybe", "reference_ok": true, "reason": ""}')
