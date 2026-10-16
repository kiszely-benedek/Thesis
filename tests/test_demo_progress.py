"""Live progress and lost time of an ask (DP-T21): the recorder, the event builder, the job status.

The builders are tested on synthetic attempts (no sleeping); one test runs a real job whose fake
model blocks until released, to see an attempt before its reply.
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx2
import openai
import pytest

from plantgraph.demo.app.api_models import AskRequest, JobStatus
from plantgraph.demo.app.progress import (
    AGENT_PROMPT_START,
    ANSWER_PROMPT_START,
    CYPHER_PROMPT_START,
    build_progress,
    lost_time,
    phase_from_prompt,
)
from plantgraph.demo.app.state import AppState, build_app_state
from plantgraph.demo.app.trace_recorder import Exchange, RecordingTransport, TraceWindow
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import CallPurpose, CallRecord, ChatResponse
from plantgraph.qa.agent.prompts import render_system_prompt
from plantgraph.qa.final_answer import render_final_answer_request
from plantgraph.qa.models import AnswerType
from plantgraph.qa.strategies.cypher_rag import render_cypher_request
from qa_harness_toy import CORPUS_ID, pin
from test_demo_app import Env, env, scripted_transport, toy  # noqa: F401

CYPHER_REQUEST = {"messages": [{"role": "user", "content": CYPHER_PROMPT_START + " ..."}]}
FIND_REPLY = '{"call": {"tool": "find", "args": {"tag": "E-30-3"}}}'


def _reply(text: str, reply_id: str = "r1") -> dict[str, Any]:
    return {"id": reply_id, "choices": [{"message": {"role": "assistant", "content": text}}]}


def _done(request: dict[str, Any], text: str, reply_id: str, start: float, took: float) -> Exchange:
    return Exchange(request, _reply(text, reply_id), 200, took, start)


def _failed(request: dict[str, Any], start: float, took: float, *, status: int | None) -> Exchange:
    error = f"HTTP {status}" if status else "ReadTimeout"
    return Exchange(request, None, status, took, start, error)


def _running(request: dict[str, Any], start: float) -> Exchange:
    return Exchange(request, None, None, 0.0, start)


def _line(purpose: CallPurpose, reply_id: str) -> CallRecord:
    response = ChatResponse(
        text="x",
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=0.0,
        latency_s=1.0,
        provider_response_id=reply_id,
        finish_reason="stop",
        from_cache=False,
        created_at=datetime.now(UTC),
    )
    return CallRecord(
        run_id="live-ask",
        purpose=purpose,
        cache_key="k",
        pin_hash="p",
        prompt_sha256="s",
        response=response,
    )


def _agent_request(*observations: tuple[str, str]) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": AGENT_PROMPT_START + " ..."},
        {"role": "user", "content": "Question: ..."},
    ]
    for reply, observation in observations:
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": observation})
    return {"messages": messages}


# ---- the recorder ---------------------------------------------------------------------------


def _client(transport: httpx2.BaseTransport) -> openai.OpenAI:
    http_client = openai.DefaultHttpxClient(transport=transport)
    return openai.OpenAI(
        base_url="http://fake.invalid/v1", api_key="k", max_retries=0, http_client=http_client
    )


def test_an_attempt_is_visible_while_it_waits_for_its_reply_and_completed_after() -> None:
    release = threading.Event()
    fake = FakeTransport(default_reply=ScriptedReply(text="hello"))

    def blocking(request: httpx2.Request) -> httpx2.Response:
        release.wait(timeout=10)
        return fake.handler(request)

    recorder = RecordingTransport(httpx2.MockTransport(blocking))
    caller = threading.Thread(
        target=lambda: _client(recorder).chat.completions.create(
            model="m", messages=[{"role": "user", "content": "hi"}]
        )
    )
    caller.start()
    deadline = time.perf_counter() + 5
    while not recorder.exchanges() and time.perf_counter() < deadline:
        time.sleep(0.01)

    (waiting,) = recorder.exchanges()
    assert waiting.running and waiting.request_json["messages"][0]["content"] == "hi"
    release.set()
    caller.join(timeout=10)

    (finished,) = recorder.exchanges()
    assert not finished.running and finished.status == 200 and finished.error is None
    assert finished.started_s == waiting.started_s and finished.elapsed_s > 0


def test_failed_attempts_keep_the_status_or_the_exception_class_and_start_order() -> None:
    answers = iter([httpx2.Response(502, json={"error": "bad gateway"}), "timeout", "ok"])

    def flaky(request: httpx2.Request) -> httpx2.Response:
        answer = next(answers)
        if answer == "timeout":
            raise httpx2.ReadTimeout("slow", request=request)
        if isinstance(answer, httpx2.Response):
            return answer
        return FakeTransport().handler(request)

    recorder = RecordingTransport(httpx2.MockTransport(flaky))
    client = _client(recorder)
    for _ in range(3):
        try:
            client.chat.completions.create(model="m", messages=[{"role": "user", "content": "q"}])
        except openai.OpenAIError:
            pass

    bad_gateway, timeout, fine = recorder.exchanges()
    assert (bad_gateway.status, bad_gateway.error) == (502, "HTTP 502")
    assert (timeout.status, timeout.error) == (None, "ReadTimeout")
    assert fine.error is None and not any(e.running for e in (bad_gateway, timeout, fine))
    assert bad_gateway.started_s <= timeout.started_s <= fine.started_s


# ---- phase ----------------------------------------------------------------------------------


def test_the_prompt_markers_match_the_frozen_prompts() -> None:
    cypher = render_cypher_request(pin=pin(), schema_text="S", question_text="Q")
    answer = render_final_answer_request(
        pin=pin(), context="C", question_text="Q", answer_type=AnswerType.TAG_SET
    )
    agent = render_system_prompt(_agent_params(), primer=False, seeded=False)

    assert cypher.messages[0].content.startswith(CYPHER_PROMPT_START)
    assert answer.messages[0].content.startswith(ANSWER_PROMPT_START)
    assert agent.startswith(AGENT_PROMPT_START)


def _agent_params() -> Any:
    from plantgraph.qa.agent.models import AgentParams

    return AgentParams()


def test_phase_comes_from_the_log_line_first_then_the_markers_then_unknown() -> None:
    odd = {"messages": [{"role": "user", "content": "something nobody wrote"}]}
    # the log line says "answer" although the prompt looks like a query prompt: the line wins
    logged = _done(CYPHER_REQUEST, "x", "r1", 0.0, 1.0)
    marked = _failed(CYPHER_REQUEST, 1.0, 1.0, status=502)
    unmarked = _running(odd, 2.0)

    events = build_progress([logged, marked, unmarked], [_line("answer", "r1")], 3.0, 0.0).events

    assert [e.phase for e in events] == ["answer", "cypher", "unknown"]
    assert phase_from_prompt({}) == "unknown"


def test_the_order_of_attempts_never_decides_the_phase() -> None:
    odd = {"messages": [{"role": "user", "content": "something nobody wrote"}]}
    first = _done(CYPHER_REQUEST, "SELECT", "r1", 0.0, 1.0)

    (_, second) = build_progress([first, _running(odd, 1.0)], [], 2.0, 0.0).events

    assert second.phase == "unknown"  # not "answer, because it follows the query"


# ---- events ---------------------------------------------------------------------------------


def test_failed_attempts_are_numbered_and_carry_status_and_error() -> None:
    attempts = [
        _failed(CYPHER_REQUEST, 0.0, 1.0, status=502),
        _failed(CYPHER_REQUEST, 2.0, 5.0, status=None),
        _running(CYPHER_REQUEST, 8.0),
    ]

    first, second, third = build_progress(attempts, [], 10.5, 0.0).events

    assert (first.state, first.attempt, first.http_status, first.error) == ("failed", 1, 502, None)
    assert (second.state, second.attempt, second.http_status, second.error) == (
        "failed",
        2,
        None,
        "ReadTimeout",
    )
    assert (third.state, third.attempt, third.elapsed_s) == ("running", 3, 2.5)


def test_a_new_request_starts_again_at_attempt_one() -> None:
    query = _done(CYPHER_REQUEST, "MATCH (n) RETURN n", "c1", 0.0, 1.0)
    answer_request = {"messages": [{"role": "user", "content": ANSWER_PROMPT_START + " ..."}]}

    events = build_progress([query, _running(answer_request, 1.0)], [], 2.0, 0.0).events

    assert [e.attempt for e in events] == [1, 1]
    assert events[0].summary == "MATCH (n) RETURN n" and events[1].state == "running"


def test_start_times_are_relative_to_the_start_of_the_ask() -> None:
    (event,) = build_progress([_running(CYPHER_REQUEST, 105.0)], [], 107.0, 100.0).events

    assert (event.started_s, event.elapsed_s) == (5.0, 2.0)


def test_a_finished_agent_step_shows_its_tool_call_and_the_first_line_of_the_observation() -> None:
    second_reply = '{"call": {"tool": "neighbours", "args": {"item": "id-1"}}}'
    attempts = [
        _done(_agent_request(), FIND_REPLY, "s1", 0.0, 1.0),
        _done(_agent_request((FIND_REPLY, "Result s1:\nitem id-1")), second_reply, "s2", 1.0, 1.0),
        _running(
            _agent_request((FIND_REPLY, "Result s1:\nitem id-1"), (second_reply, "2 items")), 2.0
        ),
    ]

    first, second, third = build_progress(attempts, [], 3.0, 0.0).events

    assert first.summary == 'find(tag="E-30-3")' and first.detail == "Result s1:"
    assert second.summary == 'neighbours(item="id-1")' and second.detail == "2 items"
    assert (first.action, second.action, third.action) == (1, 2, 3)
    assert third.state == "running" and third.summary is None


# ---- lost time ------------------------------------------------------------------------------


def test_lost_time_is_the_failed_durations_plus_the_waits_before_the_retries() -> None:
    # three failures of 1.0, 2.0 and 3.0 s; waits of 1 s and 2 s (the client's backoff) between
    # them and 4 s before the fourth attempt, which succeeds and is not lost time
    attempts = [
        _failed(CYPHER_REQUEST, 0.0, 1.0, status=502),
        _failed(CYPHER_REQUEST, 2.0, 2.0, status=502),
        _failed(CYPHER_REQUEST, 6.0, 3.0, status=None),
        _done(CYPHER_REQUEST, "q", "c1", 13.0, 25.2),
    ]

    lost = lost_time(attempts)

    assert lost.failed_attempts == 3
    assert lost.lost_s == pytest.approx((1.0 + 2.0 + 3.0) + (1.0 + 2.0 + 4.0))


def test_an_ask_without_errors_has_no_lost_time() -> None:
    lost = lost_time([_done(CYPHER_REQUEST, "q", "c1", 0.0, 5.0)])

    assert (lost.failed_attempts, lost.lost_s) == (0, 0.0)


def test_a_failure_followed_by_a_different_request_has_no_wait_added() -> None:
    other = {"messages": [{"role": "user", "content": "another prompt"}]}

    lost = lost_time([_failed(CYPHER_REQUEST, 0.0, 2.0, status=500), _running(other, 9.0)])

    assert lost.lost_s == pytest.approx(2.0)


# ---- the job status -------------------------------------------------------------------------


@pytest.fixture
def opened() -> Iterator[list[AppState]]:
    states: list[AppState] = []
    yield states
    for state in states:
        state.close()


def _wait_for(condition: Any, what: str) -> None:
    deadline = time.perf_counter() + 20
    while time.perf_counter() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError(f"expected {what} within 20 s")


def test_the_job_status_carries_the_running_attempt_and_keeps_the_progress_at_the_end(
    env: Env, opened: list[AppState]
) -> None:
    release = threading.Event()
    inner = scripted_transport()

    def blocking(request: httpx2.Request) -> httpx2.Response:
        release.wait(timeout=20)
        return inner.handler(request)

    state = build_app_state(
        env.config,
        transport=httpx2.MockTransport(blocking),
        held_corpora_probe=lambda: (CORPUS_ID,),
    )
    state.load_all()
    opened.append(state)
    request = AskRequest(
        corpus_id=CORPUS_ID, text=env.answerable.text, example_id=env.answerable.question_id
    )

    job_id = state.start_ask(request)
    _wait_for(lambda: _progress_of(state.job_status(job_id)), "an attempt in the job status")
    waiting = state.job_status(job_id)
    release.set()
    _wait_for(lambda: state.job_status(job_id).state != "running", "the job to end")
    final = state.job_status(job_id)

    assert waiting.state == "running" and waiting.progress is not None
    assert [e.state for e in waiting.progress.events] == ["running"]
    assert final.progress is not None
    assert [(e.phase, e.state) for e in final.progress.events] == [("answer", "done")]
    assert final.result is not None and final.result.trace.failed_attempts == 0


def _progress_of(status: JobStatus) -> bool:
    return status.progress is not None and len(status.progress.events) > 0


def test_the_progress_of_an_old_job_is_not_changed_by_a_later_ask(
    env: Env, opened: list[AppState]
) -> None:
    state = build_app_state(
        env.config,
        transport=httpx2.MockTransport(scripted_transport().handler),
        held_corpora_probe=lambda: (CORPUS_ID,),
    )
    state.load_all()
    opened.append(state)
    request = AskRequest(
        corpus_id=CORPUS_ID, text=env.answerable.text, example_id=env.answerable.question_id
    )

    first = state.start_ask(request)
    _wait_for(lambda: state.job_status(first).state != "running", "the first job")
    _wait_for(lambda: _start_second(state, request), "the second job to be accepted")

    progress = state.job_status(first).progress
    assert progress is not None and len(progress.events) == 1


def _start_second(state: AppState, request: AskRequest) -> bool:
    try:
        second = state.start_ask(request)
    except Exception:  # the previous job may still hold the Busy lock for a moment
        return False
    _wait_for(lambda: state.job_status(second).state != "running", "the second job")
    return True


def test_a_window_marks_its_start_on_the_recorders_clock(tmp_path: Any) -> None:
    recorder = RecordingTransport(httpx2.MockTransport(FakeTransport().handler))

    window = TraceWindow.open(recorder, tmp_path / "calls.jsonl")

    assert 0.0 <= window.mark_s <= recorder.now_s()
