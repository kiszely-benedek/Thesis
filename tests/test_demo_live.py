"""The demo answers live only: no stored answer can come back (DP-T12), tested over the toy plant.

The model is a scripted fake transport; its request list is the proof of what was sent. The toy
fixtures of `test_demo_app` are reused.
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

import dataclasses
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx2
import pytest

from plantgraph.demo.app import live_cascades
from plantgraph.demo.app.answering import came_from_cache
from plantgraph.demo.app.api_models import AskRequest, DemoAnswer, JobStatus
from plantgraph.demo.app.live_cascades import (
    Asker,
    AskHandle,
    CascadeSource,
    LiveCascadeFactory,
)
from plantgraph.demo.app.state import AppState, build_app_state
from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.cascade.live_build import OpenedCascade
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.models import Question
from plantgraph.qa.strategies.base import AskedQuestion
from qa_harness_toy import CORPUS_ID
from test_demo_app import Env, env, scripted_transport, toy  # noqa: F401


@pytest.fixture(autouse=True)
def _close_states() -> Iterator[None]:
    yield
    for state in _OPENED_STATES:  # delete each open cascade's temporary cache file
        state.close()
    _OPENED_STATES.clear()


_OPENED_STATES: list[AppState] = []


def _state(env: Env, transport: FakeTransport | None, cap: float | None = None) -> AppState:
    state = build_app_state(
        env.config,
        session_cap_usd=cap,
        transport=httpx2.MockTransport(transport.handler) if transport else None,
        held_corpora_probe=lambda: (CORPUS_ID,),  # no real Neo4j in tests
    )
    state.load_all()
    _OPENED_STATES.append(state)
    return state


def _ask_and_wait(state: AppState, question: Question) -> JobStatus:
    request = AskRequest(corpus_id=CORPUS_ID, text=question.text, example_id=question.question_id)
    job_id = state.start_ask(request)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status = state.job_status(job_id)
        if status.state != "running":
            return status
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} was still running after 20 s")


def _answer(status: JobStatus) -> DemoAnswer:
    assert status.result is not None, f"expected a finished answer, found state {status.state}"
    return status.result


class _CachedLooking:
    """An asker that rewrites its answers to look like stored ones."""

    def __init__(self, real: Asker) -> None:
        self._real = real

    def ask(self, asked: AskedQuestion) -> LiveAnswer | NeedsPaidCall:
        result = self._real.ask(asked)
        if isinstance(result, LiveAnswer):
            return result.model_copy(update={"from_cache": True})
        return result


class _SpySource:
    """Wraps a corpus's cascade source; counts the asks and may make answers look cached."""

    def __init__(self, real: CascadeSource, *, force_cached: bool = False) -> None:
        self._real = real
        self._force_cached = force_cached
        self.begun = 0
        self.tiers = real.tiers
        self.tier1_store = real.tier1_store
        self.store = real.store

    def begin_ask(self) -> AskHandle:
        self.begun += 1
        handle = self._real.begin_ask()
        if not self._force_cached:
            return handle
        return dataclasses.replace(handle, cascade=_CachedLooking(handle.cascade))

    def close(self) -> None:
        self._real.close()


def _spy_on(state: AppState, *, force_cached: bool = False) -> _SpySource:
    corpus = state.ready_corpus(CORPUS_ID)
    spy = _SpySource(corpus.source, force_cached=force_cached)
    corpus.source = spy
    return spy


def _factory(state: AppState) -> LiveCascadeFactory:
    source = state.ready_corpus(CORPUS_ID).source
    assert isinstance(source, LiveCascadeFactory)
    return source


def test_the_live_cache_is_a_temporary_file_that_close_deletes(env: Env) -> None:
    state = _state(env, scripted_transport())
    cache_file = _factory(state).cache_file

    assert cache_file.exists() and cache_file.parent != Path("data")
    state.close()

    assert not cache_file.exists() and not cache_file.parent.exists()


def test_two_identical_asks_on_the_same_open_cascade_make_two_network_requests(env: Env) -> None:
    transport = scripted_transport()
    state = _state(env, transport)

    first = _ask_and_wait(state, env.answerable)
    requests_after_first = len(transport.requests)
    second = _ask_and_wait(state, env.answerable)

    assert first.state == second.state == "done"
    assert requests_after_first == 1 and len(transport.requests) == 2
    for status in (first, second):
        answer = _answer(status)
        assert answer.live.from_cache is False and not any(t.n_cached for t in answer.live.tiers)
        assert answer.cache_hit_detected is False
        assert status.clear_s is not None


def test_each_ask_has_its_own_recorded_trace_of_the_real_calls(env: Env) -> None:
    transport = scripted_transport()
    state = _state(env, transport)

    first = _answer(_ask_and_wait(state, env.answerable))
    second = _answer(_ask_and_wait(state, env.answerable))

    assert len(transport.requests) == 2
    for answer in (first, second):  # the second ask's trace holds only its own call
        assert [call.purpose for call in answer.trace.calls] == ["answer"]
        assert answer.trace.calls[0].cost_usd == pytest.approx(0.0003)
        assert answer.trace.error is None and answer.trace.unlogged_attempts == 0


def test_a_trace_call_from_a_cache_sets_the_guard_flag_too(env: Env) -> None:
    state = _state(env, scripted_transport())
    answer = _answer(_ask_and_wait(state, env.answerable))
    cached = answer.trace.calls[0].model_copy(update={"from_cache": True})

    from plantgraph.demo.app.answering import demo_answer

    corpus = state.ready_corpus(CORPUS_ID)
    flagged = demo_answer(
        corpus, answer.live, env.answerable, answer.trace.model_copy(update={"calls": (cached,)})
    )

    assert answer.cache_hit_detected is False and flagged.cache_hit_detected is True


def test_the_stored_response_is_really_there_until_the_demo_empties_it(env: Env) -> None:
    # proves the test above is meaningful: without the delete, the second ask would hit the cache
    state = _state(env, scripted_transport())
    _ask_and_wait(state, env.answerable)
    cache_file = _factory(state).cache_file

    with closing(sqlite3.connect(cache_file)) as connection:
        stored = connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    assert stored >= 1
    _factory(state).begin_ask()  # also marks a trace window; harmless here
    with closing(sqlite3.connect(cache_file)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 0


def test_the_cascade_is_opened_once_for_several_asks(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    opens: list[int] = []
    real_open = live_cascades.open_live_cascade

    def counting_open(**kwargs: Any) -> OpenedCascade:
        opens.append(1)
        return real_open(**kwargs)

    monkeypatch.setattr(live_cascades, "open_live_cascade", counting_open)
    state = _state(env, scripted_transport())
    spy = _spy_on(state)

    for question in (env.answerable, env.unanswerable, env.answerable):
        _ask_and_wait(state, question)

    assert spy.begun == 3 and len(opens) == 1


def test_emptying_works_even_before_the_table_exists(tmp_path: Path) -> None:
    empty_file = tmp_path / "fresh.sqlite"

    live_cascades._empty_cache(empty_file)

    with closing(sqlite3.connect(empty_file)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 0


def test_a_cached_call_sets_the_guard_flag(env: Env) -> None:
    state = _state(env, scripted_transport())
    _spy_on(state, force_cached=True)

    body = _ask_and_wait(state, env.answerable)

    assert body.state == "done" and _answer(body).cache_hit_detected is True


def test_came_from_cache_sees_a_cached_tier_as_well_as_a_cached_answer(env: Env) -> None:
    state = _state(env, scripted_transport())
    body = _ask_and_wait(state, env.answerable)
    live = _answer(body).live
    cached_tier = live.tiers[0].model_copy(update={"n_cached": 1})

    assert came_from_cache(live) is False
    assert came_from_cache(live.model_copy(update={"tiers": (cached_tier,)})) is True
    assert came_from_cache(live.model_copy(update={"from_cache": True})) is True


def test_the_reservation_is_released_with_the_real_spend(env: Env) -> None:
    # reservation is 0.0018; a leaked one would make the second ask pass the 0.003 cap
    state = _state(env, scripted_transport(), cap=0.003)

    first = _ask_and_wait(state, env.answerable)
    second = _ask_and_wait(state, env.answerable)

    assert first.state == second.state == "done"
    assert second.spend.session_spent_usd == pytest.approx(0.0006)


def test_without_a_model_key_the_corpus_is_an_error_with_a_code(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(live_cascades.openrouter_settings, "from_env", lambda: None)
    state = _state(env, transport=None)

    (corpus,) = state.status().corpora

    assert corpus.state == "error" and corpus.error_code == "no_api_key"
