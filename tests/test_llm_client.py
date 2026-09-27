"""`ChatClient` — OpenAI-compatible client for OpenRouter and local backends
(design `qa-system.md` §3, §6, coder task QA-T2).

No network anywhere here: every test injects `FakeTransport` in place of the
HTTP transport (`fake_transport.py`), so the `openai` SDK never opens a
socket. `_TEST_KEY` is a fake credential used only to prove it never leaks —
see the key-hygiene tests at the bottom of this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.local_settings import LocalLLMSettings
from plantgraph.llm.models import (
    CacheMiss,
    ChatMessage,
    ChatRequest,
    ContextOverflow,
    ModelPin,
    ProviderError,
)
from plantgraph.llm.openrouter_settings import OpenRouterSettings

#: Fake, never-real credential. Every key-hygiene test below asserts this
#: exact string is absent from some output; a real key would make that
#: assertion meaningless.
_TEST_KEY = "sk-or-TEST-SECRET"


def _pin(**overrides: object) -> ModelPin:
    defaults: dict[str, object] = {
        "backend": "openrouter",
        "model_id": "openai/gpt-5-mini",
        "route_provider": "openai",
        "temperature": 0.0,
        "seed": 42,
        "max_output_tokens": 64,
    }
    defaults.update(overrides)
    return ModelPin.model_validate(defaults)


def _request(**overrides: object) -> ChatRequest:
    defaults: dict[str, object] = {
        "pin": _pin(),
        "messages": [ChatMessage(role="user", content="What is P-101?")],
        "json_mode": False,
        "purpose": "answer",
    }
    defaults.update(overrides)
    return ChatRequest.model_validate(defaults)


def _client(
    fake: FakeTransport,
    *,
    tmp_path: Path,
    allow_network: bool = True,
    cache_mode: Literal["live", "replay"] = "live",
    max_retries: int = 3,
    backoff_base_seconds: float = 0.0,
) -> ChatClient:
    """A `ChatClient` for OpenRouter, wired to `fake` instead of a real connection."""
    cache = SqliteCache(tmp_path / "cache.sqlite", mode=cache_mode)
    settings = OpenRouterSettings(api_key=_TEST_KEY)
    return ChatClient.for_openrouter(
        settings,
        cache=cache,
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=allow_network,
        max_retries=max_retries,
        backoff_base_seconds=backoff_base_seconds,
        http_client=fake.as_httpx_client(),
    )


def _read_calls(tmp_path: Path) -> list[dict[str, Any]]:
    text = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def _sent_body(fake: FakeTransport, index: int = 0) -> dict[str, Any]:
    return json.loads(fake.requests[index].content.decode("utf-8"))


# --- success, retries, overflow ---------------------------------------------


def test_success_returns_the_scripted_reply_and_logs_one_call(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="A centrifugal pump."))
    client = _client(fake, tmp_path=tmp_path)

    response = client.complete(_request(), run_id="run-1", question_id="Q1", strategy="context_rag")

    assert response.text == "A centrifugal pump."
    assert response.from_cache is False
    assert len(fake.requests) == 1
    calls = _read_calls(tmp_path)
    assert len(calls) == 1
    assert calls[0]["error_kind"] is None
    assert calls[0]["response"]["text"] == "A centrifugal pump."
    assert calls[0]["question_id"] == "Q1"
    assert calls[0]["strategy"] == "context_rag"


def test_transport_429_then_success_is_retried(tmp_path: Path) -> None:
    fake = FakeTransport(fail_times=1, fail_status=429, default_reply=ScriptedReply(text="ok"))
    client = _client(fake, tmp_path=tmp_path)

    response = client.complete(_request(), run_id="run-1")

    assert response.text == "ok"
    assert len(fake.requests) == 2, "one 429, then a retry that succeeded"
    logged_call = _read_calls(tmp_path)[0]
    assert logged_call["error_kind"] is None, "only the final, successful attempt is logged"


def test_persistent_5xx_exhausts_retries_and_raises_provider_error(tmp_path: Path) -> None:
    fake = FakeTransport(fail_times=10, fail_status=503)
    client = _client(fake, tmp_path=tmp_path, max_retries=2)

    with pytest.raises(ProviderError):
        client.complete(_request(), run_id="run-1")

    assert len(fake.requests) == 3, "first attempt plus 2 retries, all failing"
    assert _read_calls(tmp_path)[-1]["error_kind"] == "provider_error"


def test_a_4xx_content_error_is_never_retried(tmp_path: Path) -> None:
    fake = FakeTransport(fail_times=10, fail_status=400)
    client = _client(fake, tmp_path=tmp_path, max_retries=5)

    with pytest.raises(ProviderError):
        client.complete(_request(), run_id="run-1")

    assert len(fake.requests) == 1, "a 4xx content error must not be retried (§6)"


def test_context_overflow_is_raised_and_logged_with_no_retry(tmp_path: Path) -> None:
    fake = FakeTransport(context_wall_chars=10)
    client = _client(fake, tmp_path=tmp_path)
    long_request = _request(messages=[ChatMessage(role="user", content="x" * 50)])

    with pytest.raises(ContextOverflow):
        client.complete(long_request, run_id="run-1")

    assert len(fake.requests) == 1, "an overflow is a content error, not a transport one: no retry"
    calls = _read_calls(tmp_path)
    assert calls[-1]["error_kind"] == "context_overflow"
    assert calls[-1]["response"] is None


# --- cache and the paid-call guard -------------------------------------------


def test_cache_hit_makes_zero_transport_calls(tmp_path: Path) -> None:
    request = _request()
    warm_fake = FakeTransport(default_reply=ScriptedReply(text="cached answer"))
    _client(warm_fake, tmp_path=tmp_path).complete(request, run_id="run-1")

    cold_fake = FakeTransport(fail_times=999)  # would fail every call if it were ever reached
    response = _client(cold_fake, tmp_path=tmp_path).complete(request, run_id="run-2")

    assert response.text == "cached answer"
    assert response.from_cache is True, "the hit, not the original write, sets this"
    assert len(cold_fake.requests) == 0


def test_replay_mode_miss_raises_cache_miss_and_makes_zero_calls(tmp_path: Path) -> None:
    fake = FakeTransport()
    client = _client(fake, tmp_path=tmp_path, cache_mode="replay")

    with pytest.raises(CacheMiss):
        client.complete(_request(), run_id="run-1")

    assert len(fake.requests) == 0


def test_allow_network_false_refuses_a_live_call(tmp_path: Path) -> None:
    """The paid-call guard: `allow_network=False` must refuse before any request, key or no key."""
    fake = FakeTransport()
    client = _client(fake, tmp_path=tmp_path, allow_network=False, cache_mode="live")

    with pytest.raises(CacheMiss):
        client.complete(_request(), run_id="run-1")

    assert len(fake.requests) == 0


# --- calls.jsonl fields, and the outgoing request body -----------------------


def test_calls_jsonl_has_the_designed_fields_and_no_key(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="ok"))
    client = _client(fake, tmp_path=tmp_path)

    client.complete(_request(), run_id="run-1", question_id="Q1", strategy="context_rag")

    calls = _read_calls(tmp_path)
    record = calls[0]
    for field in (
        "run_id",
        "question_id",
        "strategy",
        "purpose",
        "cache_key",
        "pin_hash",
        "prompt_sha256",
        "response",
        "error_kind",
    ):
        assert field in record, f"calls.jsonl is missing {field!r} (design §4, §6)"
    raw_text = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    assert _TEST_KEY not in raw_text


def test_provider_pin_and_require_parameters_are_sent(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="ok"))
    client = _client(fake, tmp_path=tmp_path)

    client.complete(_request(pin=_pin(route_provider="openai")), run_id="run-1")

    body = _sent_body(fake)
    assert body["require_parameters"] is True
    assert body["provider"] == {"order": ["openai"], "allow_fallbacks": False}


def test_json_mode_sets_response_format(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text='{"answer": 1}'))
    client = _client(fake, tmp_path=tmp_path)

    client.complete(_request(json_mode=True), run_id="run-1")

    assert _sent_body(fake)["response_format"] == {"type": "json_object"}


def test_local_backend_sends_no_openrouter_extras(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="ok"))
    cache = SqliteCache(tmp_path / "cache.sqlite", mode="live")
    settings = LocalLLMSettings(base_url="http://127.0.0.1:1234/v1")
    client = ChatClient.for_local(
        settings,
        cache=cache,
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
        backoff_base_seconds=0.0,
        http_client=fake.as_httpx_client(),
    )
    local_pin = _pin(backend="local", route_provider=None)

    client.complete(_request(pin=local_pin), run_id="run-1")

    body = _sent_body(fake)
    assert "provider" not in body
    assert "require_parameters" not in body


# --- key hygiene (design §6, §16) --------------------------------------------


def test_repr_of_client_never_contains_the_key(tmp_path: Path) -> None:
    client = _client(FakeTransport(), tmp_path=tmp_path)

    assert _TEST_KEY not in repr(client)
    assert "openrouter" in repr(client)


def test_key_never_leaks_through_a_provider_error_that_echoes_headers(tmp_path: Path) -> None:
    # A provider that echoes the Authorization header back in its error body
    # is the worst case for a leak; ChatClient must redact it before the
    # value reaches an exception, a log line, or any file on disk.
    fake = FakeTransport(fail_times=999, fail_status=500, echo_authorization_header=True)
    client = _client(fake, tmp_path=tmp_path, max_retries=0)

    with pytest.raises(ProviderError) as excinfo:
        client.complete(_request(), run_id="run-1")

    assert _TEST_KEY not in str(excinfo.value)
    assert "***" in str(excinfo.value), "the redacted key is replaced, not merely dropped"
    assert _TEST_KEY.encode() not in (tmp_path / "calls.jsonl").read_bytes()
    assert _TEST_KEY.encode() not in (tmp_path / "cache.sqlite").read_bytes()
