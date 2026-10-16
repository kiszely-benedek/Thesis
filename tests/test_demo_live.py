"""The demo answers live only: no stored answer can come back (DP-T12), tested over the toy plant.

The model is a scripted fake transport; its request list is the proof of what was sent. The toy
fixtures of `test_demo_app` are reused.
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

import time
from pathlib import Path

import pytest

from plantgraph.demo.app import live_cascades
from plantgraph.demo.app.answering import came_from_cache
from plantgraph.demo.app.api_models import AskRequest, DemoAnswer, JobStatus
from plantgraph.demo.app.live_cascades import LIVE_CACHE, CascadeSource, OpenedForAsk
from plantgraph.demo.app.state import AppState, build_app_state
from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.models import Question
from plantgraph.qa.strategies.base import AskedQuestion
from qa_harness_toy import CORPUS_ID
from test_demo_app import Env, env, scripted_transport, toy  # noqa: F401


def _state(env: Env, transport: FakeTransport | None, cap: float | None = None) -> AppState:
    state = build_app_state(
        env.config,
        session_cap_usd=cap,
        http_client=transport.as_httpx_client() if transport else None,
        held_corpora_probe=lambda: ("D1000",),  # no real Neo4j in tests
    )
    state.load_all()
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


class _SpyOpened:
    """An opened cascade that remembers whether it was closed, and may rewrite its answers."""

    def __init__(self, real: OpenedForAsk, *, force_cached: bool) -> None:
        self._real = real
        self._force_cached = force_cached
        self.closed = False

    @property
    def cascade(self) -> _SpyOpened:
        return self

    def ask(self, asked: AskedQuestion) -> LiveAnswer | NeedsPaidCall:
        result = self._real.cascade.ask(asked)
        if self._force_cached and isinstance(result, LiveAnswer):
            return result.model_copy(update={"from_cache": True})
        return result

    def close(self) -> None:
        self.closed = True
        self._real.close()


class _SpySource:
    """Wraps a corpus's cascade source and keeps every cascade it opened."""

    def __init__(self, real: CascadeSource, *, force_cached: bool = False) -> None:
        self._real = real
        self._force_cached = force_cached
        self.opened: list[_SpyOpened] = []
        self.tiers = real.tiers
        self.tier1_store = real.tier1_store
        self.store = real.store

    def open_for_ask(self) -> tuple[OpenedForAsk, float]:
        real, open_s = self._real.open_for_ask()
        spy = _SpyOpened(real, force_cached=self._force_cached)
        self.opened.append(spy)
        return spy, open_s


def _spy_on(state: AppState, *, force_cached: bool = False) -> _SpySource:
    corpus = state.ready_corpus(CORPUS_ID)
    spy = _SpySource(corpus.source, force_cached=force_cached)
    corpus.source = spy
    return spy


def test_the_live_cache_is_an_empty_database_in_memory_not_a_file() -> None:
    assert str(LIVE_CACHE) == ":memory:"
    assert not Path(":memory:").exists()


def test_two_identical_asks_make_two_network_requests(env: Env) -> None:
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


def test_the_cascade_is_closed_after_every_ask(env: Env) -> None:
    state = _state(env, scripted_transport())
    spy = _spy_on(state)

    _ask_and_wait(state, env.answerable)
    _ask_and_wait(state, env.unanswerable)

    assert len(spy.opened) == 2 and all(o.closed for o in spy.opened)
    assert spy.opened[0] is not spy.opened[1]  # a fresh cascade per ask


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
