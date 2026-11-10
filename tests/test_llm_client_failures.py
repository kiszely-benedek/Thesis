"""`ChatClient` failures: empty error replies, back-off time, overflow replay, tombstones."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import (
    CacheMiss,
    CallRecord,
    ChatMessage,
    ChatRequest,
    ContextOverflow,
    ModelPin,
    ProviderError,
    RequestTimedOut,
)
from plantgraph.llm.openrouter_settings import OpenRouterSettings

_ERROR_REPLY = ScriptedReply(text="", finish_reason="error")


def _request(text: str = "question") -> ChatRequest:
    pin = ModelPin(backend="openrouter", model_id="m", temperature=0.0, max_output_tokens=16)
    return ChatRequest(pin=pin, messages=[ChatMessage(role="user", content=text)], purpose="answer")


def _client(
    tmp_path: Path, fake: FakeTransport, *, replay: bool = False, backoff: float = 0.0
) -> ChatClient:
    cache = SqliteCache(tmp_path / "cache.sqlite", "replay" if replay else "live")
    return ChatClient.for_openrouter(
        OpenRouterSettings(api_key=SecretStr("test-key")),
        cache=cache,
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=not replay,
        max_retries=2,
        backoff_base_seconds=backoff,
        http_client=fake.as_httpx_client(),
    )


def _calls(tmp_path: Path) -> list[dict[str, Any]]:
    lines = (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_an_empty_error_reply_is_retried_and_the_good_answer_is_cached(tmp_path: Path) -> None:
    fake = FakeTransport(leading_replies=[_ERROR_REPLY])
    client = _client(tmp_path, fake)

    response = client.complete(_request(), run_id="r")

    assert response.text == "ok" and len(fake.requests) == 2
    discarded, record = _calls(tmp_path)  # the thrown-away error reply is logged, then the answer
    assert discarded["error_kind"] == "provider_error" and discarded["response"] is not None
    assert record["error_kind"] is None and record["n_retries"] == 1
    again = _client(tmp_path, FakeTransport(), replay=True).complete(_request(), run_id="r")
    assert again.text == "ok"


def test_a_persistent_empty_error_reply_is_a_provider_error_and_is_not_cached(
    tmp_path: Path,
) -> None:
    fake = FakeTransport(default_reply=_ERROR_REPLY)
    client = _client(tmp_path, fake)

    with pytest.raises(ProviderError) as raised:
        client.complete(_request(), run_id="r")

    assert len(fake.requests) == 3 and raised.value.n_retries == 2
    assert _calls(tmp_path)[-1]["error_kind"] == "provider_error"
    assert _calls(tmp_path)[-1]["n_retries"] == 2
    with pytest.raises(CacheMiss):  # nothing was stored for a replay to find
        _client(tmp_path, FakeTransport(), replay=True).complete(_request(), run_id="r")


def test_an_error_finish_reason_with_text_is_still_a_failure(tmp_path: Path) -> None:
    # a half-written reply inside a 200 is not an answer: retried, never cached, then an error
    partial = ScriptedReply(text="partial", finish_reason="error", cost_usd=0.002)
    fake = FakeTransport(default_reply=partial)
    client = _client(tmp_path, fake)

    with pytest.raises(ProviderError) as raised:
        client.complete(_request(), run_id="r")

    assert len(fake.requests) == 3
    assert raised.value.paid_usd == pytest.approx(0.006)  # three billed attempts
    with pytest.raises(CacheMiss):
        _client(tmp_path, FakeTransport(), replay=True).complete(_request(), run_id="r")


def test_the_cost_of_every_discarded_error_attempt_is_in_calls_jsonl(tmp_path: Path) -> None:
    partial = ScriptedReply(text="partial", finish_reason="error", cost_usd=0.002)
    client = _client(tmp_path, FakeTransport(default_reply=partial))

    with pytest.raises(ProviderError):
        client.complete(_request(), run_id="r")

    paid = [c["response"]["cost_usd"] for c in _calls(tmp_path) if c["response"] is not None]
    assert paid == [0.002] * 3  # spend read from calls.jsonl counts them


def test_backoff_and_failed_attempts_are_in_the_latency(tmp_path: Path) -> None:
    fake = FakeTransport(fail_times=1, fail_status=503)

    response = _client(tmp_path, fake, backoff=0.2).complete(_request(), run_id="r")

    assert response.latency_s >= 0.2  # the 0.2 s back-off before the second attempt
    assert _calls(tmp_path)[0]["n_retries"] == 1


def test_a_call_without_retries_leaves_n_retries_out_of_the_line(tmp_path: Path) -> None:
    _client(tmp_path, FakeTransport()).complete(_request(), run_id="r")

    assert "n_retries" not in _calls(tmp_path)[0]


def test_an_old_call_record_without_n_retries_loads() -> None:
    line = (
        '{"run_id":"r","purpose":"answer","cache_key":"k","pin_hash":"p","prompt_sha256":"s",'
        '"response":null,"error_kind":"timeout"}'
    )

    assert CallRecord.model_validate_json(line).n_retries == 0


def test_a_context_overflow_is_cached_and_replayed_as_the_same_error(tmp_path: Path) -> None:
    long_request = _request("x" * 50)
    live_fake = FakeTransport(context_wall_chars=10)
    with pytest.raises(ContextOverflow) as live_error:
        _client(tmp_path, live_fake).complete(long_request, run_id="r")

    replay_fake = FakeTransport(context_wall_chars=10)
    with pytest.raises(ContextOverflow) as replayed:
        _client(tmp_path, replay_fake, replay=True).complete(long_request, run_id="r")

    assert str(replayed.value) == str(live_error.value)
    assert replay_fake.requests == []
    assert [c["error_kind"] for c in _calls(tmp_path)] == ["context_overflow"] * 2


def test_a_tombstone_from_a_bigger_budget_costs_only_the_smaller_budget(tmp_path: Path) -> None:
    slow = FakeTransport(latency_for_prompt=lambda _prompt: 0.5)
    with pytest.raises(RequestTimedOut):
        _client(tmp_path, slow).complete(_request(), run_id="r", timeout_s=0.3)

    with pytest.raises(RequestTimedOut) as raised:
        _client(tmp_path, FakeTransport(), replay=True).complete(
            _request(), run_id="r", timeout_s=0.1
        )

    assert raised.value.latency_s == 0.1
