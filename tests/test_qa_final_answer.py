"""The shared final-answer step: prompt render, JSON extraction, outcome mapping (§8).

Per `qa-system.md` §18 QA-T8's acceptance check: canned model replies — valid
JSON, fenced JSON, prose, truncated, wrong type, abstention — map to the
right `Outcome`, and the template hash is stable but changes with the
template. No network call is made anywhere in this file: `run_final_step`
takes a plain Python callable in place of the real LLM client (QA-T2, not
built yet).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.models import (
    ChatRequest,
    ChatResponse,
    ContextOverflow,
    ContextWall,
    ModelPin,
)
from plantgraph.qa import final_answer
from plantgraph.qa.final_answer import (
    FinalAnswerParseError,
    parse_final_answer,
    render_final_answer_request,
    run_final_step,
    template_sha256,
    template_text,
)
from plantgraph.qa.models import AnswerType, Outcome


def _pin(**overrides: object) -> ModelPin:
    defaults: dict[str, object] = {
        "backend": "openrouter",
        "model_id": "openai/gpt-5-mini",
        "route_provider": "openai",
        "temperature": 0.0,
        "seed": 42,
        "max_output_tokens": 512,
        "extra": {},
    }
    defaults.update(overrides)
    return ModelPin.model_validate(defaults)


def _response(text: str) -> ChatResponse:
    return ChatResponse(
        text=text,
        prompt_tokens=100,
        completion_tokens=10,
        cost_usd=0.001,
        latency_s=0.5,
        provider_response_id="gen-1",
        finish_reason="stop",
        from_cache=False,
        created_at=datetime(2026, 9, 26, 12, 0, 0),
    )


def _wall(*, max_ok_chars: int, min_rejected_chars: int | None) -> ContextWall:
    return ContextWall(
        pin_hash="pin-abc123",
        max_ok_chars=max_ok_chars,
        min_rejected_chars=min_rejected_chars,
        measured_at=datetime(2026, 9, 26, 12, 0, 0),
        probe_corpus_ids=["D10"],
    )


# --- template hash ---------------------------------------------------------------------------


def test_template_sha256_matches_the_shipped_file() -> None:
    template_path = Path(final_answer.__file__).parent / "prompts" / "final_answer.txt"
    assert template_sha256() == hashlib.sha256(template_path.read_bytes()).hexdigest()


def test_template_sha256_is_stable_across_calls() -> None:
    assert template_sha256() == template_sha256()


def test_template_sha256_changes_if_the_template_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original_hash = template_sha256()
    edited_template = tmp_path / "final_answer.txt"
    edited_template.write_text(template_text() + "\nOne more line.\n", encoding="utf-8")

    monkeypatch.setattr(final_answer, "_TEMPLATE_PATH", edited_template)

    assert template_sha256() != original_hash


# --- prompt rendering --------------------------------------------------------------------------


def test_render_keeps_system_instruction_context_question_and_format_in_order() -> None:
    request = render_final_answer_request(
        pin=_pin(),
        context='<node tag="P-101"/>',
        question_text="What type of item is P-101?",
        answer_type=AnswerType.TAG,
    )
    content = request.messages[0].content

    system_index = content.find("piping and instrumentation diagram")
    context_index = content.find('<node tag="P-101"/>')
    question_index = content.find("What type of item is P-101?")
    format_index = content.find("Answer with a single tag")

    assert -1 not in (system_index, context_index, question_index, format_index)
    assert system_index < context_index < question_index < format_index


def test_render_does_not_reinterpret_braces_inside_the_context() -> None:
    # CypherRAG's context is a dump of JSON rows; str.replace (not str.format)
    # must leave those braces exactly as given.
    cypher_rows = '{"tag": "P-101", "unit_id": "12"}'

    request = render_final_answer_request(
        pin=_pin(), context=cypher_rows, question_text="q", answer_type=AnswerType.TAG
    )

    assert cypher_rows in request.messages[0].content


def test_render_class_name_format_instruction_lists_node_classes() -> None:
    request = render_final_answer_request(
        pin=_pin(), context="c", question_text="q", answer_type=AnswerType.CLASS_NAME
    )

    assert "CentrifugalPump" in request.messages[0].content
    assert "GlobeValve" in request.messages[0].content


def test_render_sets_json_mode_and_answer_purpose() -> None:
    request = render_final_answer_request(
        pin=_pin(), context="c", question_text="q", answer_type=AnswerType.TAG
    )

    assert request.json_mode is True
    assert request.purpose == "answer"


# --- parsing: valid JSON, fenced JSON, prose, truncated, wrong type, abstention ---------------


def test_valid_json_parses_to_answered() -> None:
    reply = '{"answer": "P-101", "not_present": false}'

    final = parse_final_answer(reply, AnswerType.TAG)

    assert final.answer == "P-101"
    assert final.not_present is False


def test_fenced_json_is_extracted_from_around_the_code_fence() -> None:
    reply = 'Here you go:\n```json\n{"answer": ["A-1", "B-2"], "not_present": false}\n```\nDone.'

    final = parse_final_answer(reply, AnswerType.TAG_SET)

    assert final.answer == ["A-1", "B-2"]


def test_prose_with_no_json_object_is_a_parse_failure() -> None:
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer("The answer is P-101, a centrifugal pump.", AnswerType.TAG)


def test_truncated_json_is_a_parse_failure() -> None:
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer('{"answer": "P-101", "not_pre', AnswerType.TAG)


def test_wrong_type_for_the_answer_type_is_a_parse_failure() -> None:
    # TAG needs a string; the model sent a number instead.
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer('{"answer": 42, "not_present": false}', AnswerType.TAG)


def test_count_accepts_a_numeric_string() -> None:
    final = parse_final_answer('{"answer": "5", "not_present": false}', AnswerType.COUNT)
    assert final.answer == "5"


def test_count_rejects_a_non_numeric_string() -> None:
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer('{"answer": "five", "not_present": false}', AnswerType.COUNT)


def test_abstention_parses_with_a_null_answer() -> None:
    final = parse_final_answer('{"answer": null, "not_present": true}', AnswerType.TAG)

    assert final.not_present is True
    assert final.answer is None


def test_missing_not_present_field_is_a_parse_failure() -> None:
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer('{"answer": "P-101"}', AnswerType.TAG)


# --- run_final_step: outcome mapping end to end ----------------------------------------------


def test_run_final_step_answers_when_the_prompt_fits() -> None:
    calls: list[ChatRequest] = []

    def send(request: ChatRequest) -> ChatResponse:
        calls.append(request)
        return _response('{"answer": "P-101", "not_present": false}')

    result = run_final_step(
        pin=_pin(),
        context="small context",
        question_text="What type of item is P-101?",
        answer_type=AnswerType.TAG,
        wall=None,
        send=send,
    )

    assert result.outcome is Outcome.ANSWERED
    assert result.final_answer is not None
    assert result.final_answer.answer == "P-101"
    assert len(calls) == 1


def test_run_final_step_skips_the_call_when_the_prompt_is_over_the_wall() -> None:
    calls: list[ChatRequest] = []

    def send(request: ChatRequest) -> ChatResponse:
        calls.append(request)
        raise AssertionError("send must not be called: the pre-call check should have stopped it")

    result = run_final_step(
        pin=_pin(),
        context="anything",
        question_text="q",
        answer_type=AnswerType.TAG,
        wall=_wall(max_ok_chars=1, min_rejected_chars=2),
        send=send,
    )

    assert result.outcome is Outcome.DID_NOT_FIT
    assert result.response is None
    assert calls == []
    assert result.trace["fit_check"] == "pre_call_over_min_rejected"


def test_run_final_step_maps_an_on_call_overflow_to_did_not_fit() -> None:
    def send(request: ChatRequest) -> ChatResponse:
        raise ContextOverflow("maximum context length exceeded")

    result = run_final_step(
        pin=_pin(),
        context="anything",
        question_text="q",
        answer_type=AnswerType.TAG,
        wall=None,
        send=send,
    )

    assert result.outcome is Outcome.DID_NOT_FIT
    assert result.response is None
    assert result.trace["overflow_on_call"] is True


def test_run_final_step_reports_a_parse_failure_from_an_unparseable_reply() -> None:
    def send(request: ChatRequest) -> ChatResponse:
        return _response("Sorry, I cannot help with that.")

    result = run_final_step(
        pin=_pin(),
        context="anything",
        question_text="q",
        answer_type=AnswerType.TAG,
        wall=None,
        send=send,
    )

    assert result.outcome is Outcome.PARSE_FAILURE
    assert result.final_answer is None
    assert result.response is not None  # the call was made; only parsing failed


def test_run_final_step_lets_a_non_overflow_provider_error_propagate() -> None:
    class _BoomError(Exception):
        pass

    def send(request: ChatRequest) -> ChatResponse:
        raise _BoomError("provider is down")

    with pytest.raises(_BoomError):
        run_final_step(
            pin=_pin(),
            context="anything",
            question_text="q",
            answer_type=AnswerType.TAG,
            wall=None,
            send=send,
        )
