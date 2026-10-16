"""The recorded trace of an ask (DP-T14): the recorder, the join with the call log, the parsing.

The exchanges are built from the real prompt builders, so a change in the frozen prompt
format shows up here. Nothing touches the network; the model is a fake transport.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx2
import openai
import pytest

from plantgraph.demo.app import live_cascades
from plantgraph.demo.app.ask_trace import build_trace
from plantgraph.demo.app.trace_models import AskTrace
from plantgraph.demo.app.trace_recorder import Exchange, RecordingTransport, TraceWindow
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import CallErrorKind, CallPurpose, CallRecord, ChatResponse
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.final_answer import render_final_answer_request
from plantgraph.qa.models import AnswerType
from plantgraph.qa.strategies.cypher_rag import format_context
from qa_harness_toy import pin
from qa_plant_api_toy import item_id, toy_graph

QUESTION = "What is downstream of P1?"
FIND_REPLY = '{"call": {"tool": "find", "args": {"tag": "P1"}}}'
STEP_REPLY = '{"call": {"tool": "neighbours", "args": {"item": "id-p1"}}}'


def _reply_json(reply_id: str, text: str) -> dict[str, Any]:
    return {"id": reply_id, "choices": [{"message": {"role": "assistant", "content": text}}]}


def _exchange(reply_id: str | None, text: str, messages: list[dict[str, str]]) -> Exchange:
    body = None if reply_id is None else _reply_json(reply_id, text)
    return Exchange({"messages": messages}, body, None if body is None else 200, 0.1)


def _line(
    purpose: CallPurpose,
    reply_id: str | None,
    text: str = "",
    *,
    error_kind: CallErrorKind | None = None,
    from_cache: bool = False,
) -> CallRecord:
    response = None
    if reply_id is not None:
        response = ChatResponse(
            text=text,
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.002,
            latency_s=1.5,
            provider_response_id=reply_id,
            finish_reason="stop",
            from_cache=from_cache,
            created_at=datetime.now(UTC),
        )
    return CallRecord(
        run_id="live-ask",
        strategy="cypher_rag_plant" if purpose in ("cypher", "answer") else "graph_agent",
        purpose=purpose,
        cache_key="k",
        pin_hash="p",
        prompt_sha256="s",
        response=response,
        error_kind=error_kind,
    )


def _answer_messages(context: str) -> list[dict[str, str]]:
    request = render_final_answer_request(
        pin=pin(), context=context, question_text=QUESTION, answer_type=AnswerType.TAG_SET
    )
    return [m.model_dump() for m in request.messages]


def _cypher_run(rows: list[dict[str, Any]], *, cut: bool = False) -> tuple[list[Exchange], list]:
    query = "MATCH (n) RETURN n.tag AS tag"
    context = format_context(query, CypherResult(rows=rows, truncated=cut), row_cap=2)
    exchanges = [
        _exchange("c1", query, [{"role": "user", "content": "write a query"}]),
        _exchange("a1", '{"answer": ["P1"]}', _answer_messages(context)),
    ]
    lines = [_line("cypher", "c1", query), _line("answer", "a1", '{"answer": ["P1"]}')]
    return exchanges, lines


def _agent_conversation(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": "you are an agent"},
        {"role": "user", "content": QUESTION},
    ]
    for reply, observation in pairs:
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": observation})
    return messages


def _agent_run() -> tuple[list[Exchange], list]:
    """Two tool calls; the second one's result only appears in the final answer request."""
    first_result = "Result s1:\n1 item: P1 (id-p1)"
    second_result = "2 items: BV1, id-gv2"
    context = (
        "Tool results gathered for this question:\n\n"
        f'Call: find({{"tag": "P1"}})\n{first_result}\n\n'
        f'Call: neighbours({{"item": "id-p1"}})\n{second_result}'
    )
    exchanges = [
        _exchange("s1", FIND_REPLY, _agent_conversation()),
        _exchange("s2", STEP_REPLY, _agent_conversation((FIND_REPLY, first_result))),
        _exchange("a1", '{"answer": []}', _answer_messages(context)),
    ]
    lines = [
        _line("agent_step", "s1", FIND_REPLY),
        _line("agent_step", "s2", STEP_REPLY),
        _line("answer", "a1", '{"answer": []}'),
    ]
    return exchanges, lines


def _trace(exchanges: list[Exchange], lines: list[CallRecord]) -> AskTrace:
    return build_trace(exchanges, lines, toy_graph())


def test_the_cypher_query_and_its_rows_are_read_from_the_answer_prompt() -> None:
    exchanges, lines = _cypher_run([{"tag": "T1"}, {"tag": "P1"}])

    (step,) = _trace(exchanges, lines).cypher

    assert step.query == "MATCH (n) RETURN n.tag AS tag"
    assert step.rows == ({"tag": "P1"}, {"tag": "T1"})  # the canonical order the model saw
    assert step.context.startswith("Cypher query that was run:") and "2 row(s)" in step.context
    assert step.parsed and not step.truncated and step.tier == "cypher_rag_plant"


def test_a_cut_off_result_is_flagged_and_no_rows_gives_an_empty_tuple() -> None:
    cut = _trace(*_cypher_run([{"tag": "T1"}, {"tag": "P1"}], cut=True)).cypher[0]
    empty = _trace(*_cypher_run([])).cypher[0]

    assert cut.truncated is True and len(cut.rows) == 2
    assert empty.rows == () and empty.parsed is True


def test_a_context_that_is_not_json_lines_is_kept_whole_and_flagged() -> None:
    exchanges, lines = _cypher_run([{"tag": "T1"}])
    broken = exchanges[1].request_json["messages"][0]["content"].replace('{"tag": "T1"}', "oops")
    exchanges[1] = _exchange("a1", "{}", [{"role": "user", "content": broken}])

    (step,) = _trace(exchanges, lines).cypher

    assert step.parsed is False and step.rows == () and "oops" in step.context


def test_a_failed_query_without_an_answer_call_keeps_the_query_and_flags_it() -> None:
    exchanges, lines = _cypher_run([{"tag": "T1"}])

    (step,) = _trace(exchanges[:1], lines[:1]).cypher

    assert step.query.startswith("MATCH") and step.context == "" and step.parsed is False


def test_each_observation_is_paired_with_its_own_tool_call() -> None:
    first, second = _trace(*_agent_run()).agent

    assert (first.index, first.tool, first.args) == (1, "find", {"tag": "P1"})
    assert first.observation == "Result s1:\n1 item: P1 (id-p1)"
    assert (second.index, second.tool, second.args) == (2, "neighbours", {"item": "id-p1"})


def test_the_last_observation_is_taken_from_the_final_answer_request() -> None:
    _, last = _trace(*_agent_run()).agent

    assert last.observation == "2 items: BV1, id-gv2" and last.parsed is True


def test_items_are_the_tags_and_item_ids_named_in_args_and_observation() -> None:
    first, last = _trace(*_agent_run()).agent

    assert first.items == ("P1", "id-p1")
    assert last.items == ("BV1", "id-p1", item_id("GV2"))  # tags first, then item ids


def test_an_unreadable_reply_is_kept_raw_with_its_error_message_and_flagged() -> None:
    bad = "this is not json"
    exchanges = [
        _exchange("s1", bad, _agent_conversation()),
        _exchange("a1", "{}", _agent_conversation((bad, "error: expected a JSON object"))),
    ]
    lines = [_line("agent_step", "s1", bad), _line("answer", "a1", "{}")]

    (step,) = _trace(exchanges, lines).agent

    assert step.parsed is False and step.reply == bad and step.tool == ""
    assert step.observation == "error: expected a JSON object"


def test_a_reply_whose_observation_cannot_be_found_is_flagged_not_dropped() -> None:
    exchanges, lines = _agent_run()

    (step,) = _trace(exchanges[:1], lines[:1]).agent  # no later request exists

    assert step.tool == "find" and step.observation == "" and step.parsed is False


def test_a_done_reply_is_not_a_step() -> None:
    exchanges = [_exchange("s1", '{"done": true}', _agent_conversation())]

    assert _trace(exchanges, [_line("agent_step", "s1", '{"done": true}')]).agent == ()


def test_calls_come_from_the_call_log_and_the_join_uses_the_reply_id() -> None:
    exchanges, lines = _agent_run()
    exchanges.reverse()  # the order of the exchanges must not matter, only the ids

    trace = _trace(exchanges, lines)

    assert [step.tool for step in trace.agent] == ["find", "neighbours"]
    assert [call.purpose for call in trace.calls] == ["agent_step", "agent_step", "answer"]
    assert trace.calls[0].cost_usd == 0.002 and trace.calls[0].latency_s == 1.5


def test_an_exchange_without_a_log_line_is_counted_and_stays_out_of_the_steps() -> None:
    exchanges, lines = _agent_run()
    retried = _exchange(None, "", _agent_conversation())  # a failed attempt, later retried

    trace = _trace([retried, *exchanges], lines)

    assert trace.unlogged_attempts == 1 and len(trace.agent) == 2


def test_a_late_reply_of_an_abandoned_call_is_ignored() -> None:
    exchanges, lines = _agent_run()
    late = _exchange("late", FIND_REPLY, _agent_conversation())
    late_line = _line("agent_step", "late", FIND_REPLY, error_kind="late_after_timeout")
    timeout_line = _line("agent_step", None, error_kind="timeout")

    trace = _trace([late, *exchanges], [timeout_line, late_line, *lines])

    assert len(trace.agent) == 2 and trace.unlogged_attempts == 0
    assert [c.error_kind for c in trace.calls[:2]] == ["timeout", "late_after_timeout"]


def test_the_cache_flag_of_a_call_is_carried_into_the_trace() -> None:
    exchanges, lines = _agent_run()
    lines[0] = _line("agent_step", "s1", FIND_REPLY, from_cache=True)

    assert [c.from_cache for c in _trace(exchanges, lines).calls] == [True, False, False]


def test_an_empty_ask_gives_an_empty_trace() -> None:
    assert _trace([], []) == AskTrace()


# ---- the recorder ------------------------------------------------------------------------


def _chat(transport: httpx2.BaseTransport) -> openai.OpenAI:
    client = openai.DefaultHttpxClient(transport=transport)
    return openai.OpenAI(base_url="http://fake.invalid/v1", api_key="k", http_client=client)


def _ask_model(client: openai.OpenAI, text: str) -> None:
    client.chat.completions.create(model="m", messages=[{"role": "user", "content": text}])


def test_the_recorder_keeps_both_bodies_and_passes_the_reply_on_unchanged() -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="hello"))
    recorder = RecordingTransport(httpx2.MockTransport(fake.handler))

    _ask_model(_chat(recorder), "hi")

    (exchange,) = recorder.exchanges()
    assert exchange.request_json["messages"] == [{"role": "user", "content": "hi"}]
    assert exchange.response_json is not None
    assert exchange.response_json["choices"][0]["message"]["content"] == "hello"
    assert exchange.status == 200 and len(fake.requests) == 1


def test_the_window_holds_only_the_exchanges_after_its_mark(tmp_path: Any) -> None:
    fake = FakeTransport()
    recorder = RecordingTransport(httpx2.MockTransport(fake.handler))
    client = _chat(recorder)
    _ask_model(client, "before")

    window = TraceWindow.open(recorder, tmp_path / "calls.jsonl")
    _ask_model(client, "during")

    (exchange,) = window.exchanges()
    assert exchange.request_json["messages"][0]["content"] == "during"
    assert window.log_lines() == []  # no call log yet


def test_the_window_reads_only_the_log_lines_after_its_offset_and_skips_a_half_line(
    tmp_path: Any,
) -> None:
    log = tmp_path / "calls.jsonl"
    log.write_text(_line("answer", "old", "x").model_dump_json() + "\n", encoding="utf-8")
    window = TraceWindow.open(
        RecordingTransport(httpx2.MockTransport(FakeTransport().handler)), log
    )
    new = _line("answer", "new", "y").model_dump_json()
    with log.open("a", encoding="utf-8") as handle:
        handle.write(new + "\n" + new[:20])  # a second line still being written

    (line,) = window.log_lines()

    assert line.response is not None and line.response.provider_response_id == "new"


def test_a_failing_attempt_is_recorded_and_the_error_still_reaches_the_caller() -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("too slow", request=request)

    recorder = RecordingTransport(httpx2.MockTransport(refuse))

    with pytest.raises(openai.APITimeoutError):
        _chat(recorder).with_options(max_retries=0).chat.completions.create(
            model="m", messages=[{"role": "user", "content": "hi"}]
        )

    (exchange,) = recorder.exchanges()
    assert exchange.response_json is None and exchange.status is None


# ---- R7: the recording client keeps the SDK's timeouts and limits ---------------------------


def test_the_demo_client_has_the_sdk_default_timeout_and_connection_limits() -> None:
    recorder = RecordingTransport(httpx2.MockTransport(FakeTransport().handler))
    ours = live_cascades._sdk_client(recorder)
    sdk_default = openai.DefaultHttpxClient()

    assert ours.timeout == sdk_default.timeout == httpx2.Timeout(600, connect=5.0)
    assert ours.timeout == openai.DEFAULT_TIMEOUT


def test_the_timeout_reaches_the_transport_with_each_request() -> None:
    seen: list[Any] = []

    def look(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.extensions["timeout"])
        return FakeTransport().handler(request)

    recorder = RecordingTransport(httpx2.MockTransport(look))
    _ask_model(_chat(recorder), "hi")

    assert seen == [{"connect": 5.0, "read": 600, "write": 600, "pool": 600}]


def test_a_slow_reply_still_times_out_through_the_recorder() -> None:
    """A transport that takes longer than the read timeout gets the SDK's timeout error."""

    def slow(request: httpx2.Request) -> httpx2.Response:
        limit = request.extensions["timeout"]["read"]
        raise httpx2.ReadTimeout(f"no reply within {limit} s", request=request)

    recorder = RecordingTransport(httpx2.MockTransport(slow))
    client = openai.OpenAI(
        base_url="http://fake.invalid/v1",
        api_key="k",
        max_retries=0,
        http_client=openai.DefaultHttpxClient(transport=recorder),
    )

    with pytest.raises(openai.APITimeoutError):
        _ask_model(client, "hi")

    assert recorder.exchanges()[0].response_json is None


def test_a_reply_that_is_not_json_is_recorded_with_an_empty_body() -> None:
    recorder = RecordingTransport(
        httpx2.MockTransport(lambda request: httpx2.Response(200, content=b"not json"))
    )

    recorder.handle_request(httpx2.Request("POST", "http://fake.invalid/v1", content=b"{}"))

    (exchange,) = recorder.exchanges()
    assert exchange.response_json is None and exchange.status == 200
