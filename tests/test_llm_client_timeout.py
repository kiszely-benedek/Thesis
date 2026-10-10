"""`ChatClient` request timeout: abandon, tombstone, replay, late answer (cascade-v2 §6, CV2-T2).

A "blocking" backend is the fake transport sleeping before it replies. Timeouts and
sleeps are a fraction of a second, so the whole file runs in a few seconds.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pytest
from pydantic import SecretStr

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.llm.models import (
    TIMEOUT_FINISH_REASON,
    CacheMiss,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ModelPin,
    RequestTimedOut,
)
from plantgraph.llm.openrouter_settings import OpenRouterSettings

_SLOW_S = 0.6  # how long the blocking backend takes to answer
_TIMEOUT_S = 0.15


def _request(text: str = "slow question") -> ChatRequest:
    pin = ModelPin(backend="openrouter", model_id="m", temperature=0.0, max_output_tokens=16)
    return ChatRequest(pin=pin, messages=[ChatMessage(role="user", content=text)], purpose="answer")


def _blocking_transport(seconds: float = _SLOW_S) -> FakeTransport:
    return FakeTransport(latency_for_prompt=lambda _prompt: seconds)


def _client(
    tmp_path: Path,
    fake: FakeTransport,
    *,
    mode: Literal["live", "replay"] = "live",
    allow_network: bool = True,
) -> ChatClient:
    cache = SqliteCache(tmp_path / "cache.sqlite", mode)
    settings = OpenRouterSettings(api_key=SecretStr("test-key"))
    return ChatClient.for_openrouter(
        settings,
        cache=cache,
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=allow_network,
        http_client=fake.as_httpx_client(),
    )


def _call_records(tmp_path: Path) -> list[dict[str, object]]:
    lines = (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def _wait_for(condition: Callable[[], bool], seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_a_blocking_call_times_out_within_the_budget_plus_half_a_second(tmp_path: Path) -> None:
    client = _client(tmp_path, _blocking_transport())

    started = time.monotonic()
    with pytest.raises(RequestTimedOut) as raised:
        client.complete(_request(), run_id="r", timeout_s=_TIMEOUT_S)

    assert time.monotonic() - started < _TIMEOUT_S + 0.5
    assert raised.value.latency_s == _TIMEOUT_S


def test_a_timeout_writes_a_tombstone_and_a_timeout_log_line(tmp_path: Path) -> None:
    client = _client(tmp_path, _blocking_transport())
    with pytest.raises(RequestTimedOut):
        client.complete(_request(), run_id="r", question_id="q1", timeout_s=_TIMEOUT_S)

    with SqliteCache(tmp_path / "cache.sqlite", "replay") as cache:
        tombstone = cache.get(_request())
    assert tombstone is not None
    assert tombstone.finish_reason == TIMEOUT_FINISH_REASON
    assert tombstone.latency_s == _TIMEOUT_S
    assert tombstone.text == "" and tombstone.cost_usd is None
    assert _call_records(tmp_path)[0]["error_kind"] == "timeout"


def test_replay_raises_the_same_timeout_from_the_tombstone_without_a_request(
    tmp_path: Path,
) -> None:
    live = _client(tmp_path, _blocking_transport())
    with pytest.raises(RequestTimedOut):
        live.complete(_request(), run_id="r", timeout_s=_TIMEOUT_S)

    replay_fake = _blocking_transport()
    replay = _client(tmp_path, replay_fake, mode="replay", allow_network=False)
    with pytest.raises(RequestTimedOut) as raised:
        replay.complete(_request(), run_id="r", timeout_s=_TIMEOUT_S)

    assert raised.value.latency_s == _TIMEOUT_S
    assert replay_fake.requests == []


def test_a_tombstone_of_a_smaller_budget_does_not_block_a_larger_one(tmp_path: Path) -> None:
    client = _client(tmp_path, _blocking_transport(0.3))
    with pytest.raises(RequestTimedOut):
        client.complete(_request(), run_id="r", timeout_s=0.1)

    response = client.complete(_request(), run_id="r", timeout_s=5.0)

    assert response.text == "ok" and not response.from_cache
    with SqliteCache(tmp_path / "cache.sqlite", "replay") as cache:
        stored = cache.get(_request())
    assert stored is not None and stored.finish_reason != TIMEOUT_FINISH_REASON


def test_a_replay_without_a_budget_does_not_take_a_tombstone_for_an_answer(
    tmp_path: Path,
) -> None:
    live = _client(tmp_path, _blocking_transport())
    with pytest.raises(RequestTimedOut):
        live.complete(_request(), run_id="r", timeout_s=_TIMEOUT_S)

    replay = _client(tmp_path, _blocking_transport(), mode="replay", allow_network=False)
    with pytest.raises(CacheMiss):
        replay.complete(_request(), run_id="r")


def test_the_late_answer_is_logged_and_charged_but_not_cached(tmp_path: Path) -> None:
    client = _client(tmp_path, _blocking_transport(0.4))
    charged: list[ChatResponse] = []
    client.on_late_response = charged.append

    with pytest.raises(RequestTimedOut):
        client.complete(_request(), run_id="r", question_id="q1", timeout_s=0.1)
    assert _wait_for(lambda: bool(charged))

    assert charged[0].cost_usd == 0.0001
    records = _call_records(tmp_path)
    assert [record["error_kind"] for record in records] == ["timeout", "late_after_timeout"]
    assert records[1]["response"] is not None and records[1]["question_id"] == "q1"
    with SqliteCache(tmp_path / "cache.sqlite", "replay") as cache:
        stored = cache.get(_request())
    assert stored is not None and stored.finish_reason == TIMEOUT_FINISH_REASON


def test_without_a_timeout_the_call_runs_as_before(tmp_path: Path) -> None:
    client = _client(tmp_path, _blocking_transport(0.0))

    response = client.complete(_request(), run_id="r")

    assert response.text == "ok"
    assert [record["error_kind"] for record in _call_records(tmp_path)] == [None]
