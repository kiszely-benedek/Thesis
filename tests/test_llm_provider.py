"""The serving host is recorded from live replies, and pinning/omission reach the request body."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from plantgraph.llm.cache import SqliteCache, cache_key
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import ChatMessage, ChatRequest, ModelPin
from plantgraph.llm.openrouter_settings import OpenRouterSettings

#: A cache row as written before `ChatResponse.provider` existed: the key is absent.
_OLD_ROW = (
    '{"text":"old answer","prompt_tokens":3,"completion_tokens":2,"cost_usd":0.001,'
    '"latency_s":1.5,"provider_response_id":"gen-old","finish_reason":"stop",'
    '"from_cache":false,"created_at":"2026-10-01T00:00:00Z"}'
)


def _request(**pin_fields: Any) -> ChatRequest:
    fields: dict[str, Any] = {
        "backend": "openrouter",
        "model_id": "z-ai/glm-5.3-flash",
        "max_output_tokens": 64,
        **pin_fields,
    }
    message = ChatMessage(role="user", content="What is P-101?")
    return ChatRequest(pin=ModelPin(**fields), messages=[message], purpose="answer")


def _client(fake: FakeTransport, tmp_path: Path) -> ChatClient:
    return ChatClient.for_openrouter(
        OpenRouterSettings(api_key="sk-or-TEST"),
        cache=SqliteCache(tmp_path / "cache.sqlite", "live"),
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
        http_client=fake.as_httpx_client(),
    )


def _sent_body(fake: FakeTransport) -> dict[str, Any]:
    return json.loads(fake.requests[0].content.decode("utf-8"))


def test_live_reply_provider_is_parsed_and_logged(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="ok", provider="Fireworks"))

    response = _client(fake, tmp_path).complete(_request(), run_id="r")

    assert response.provider == "Fireworks"
    logged = json.loads((tmp_path / "calls.jsonl").read_text(encoding="utf-8"))
    assert logged["response"]["provider"] == "Fireworks"


def test_reply_without_provider_leaves_it_none_and_out_of_the_log(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="ok"))

    response = _client(fake, tmp_path).complete(_request(), run_id="r")

    assert response.provider is None
    assert "provider" not in json.loads((tmp_path / "calls.jsonl").read_text("utf-8"))["response"]


def test_cached_provider_survives_a_replay(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text="ok", provider="Cerebras"))
    client = _client(fake, tmp_path)
    client.complete(_request(), run_id="r")

    replayed = client.complete(_request(), run_id="r")

    assert replayed.from_cache is True
    assert replayed.provider == "Cerebras"
    assert len(fake.requests) == 1


def test_old_cache_entry_without_provider_still_hits(tmp_path: Path) -> None:
    request = _request()
    SqliteCache(tmp_path / "cache.sqlite", "live").close()  # creates the table
    with sqlite3.connect(tmp_path / "cache.sqlite") as connection:
        connection.execute(
            "INSERT INTO responses (key, response_json) VALUES (?, ?)",
            (cache_key(request), _OLD_ROW),
        )
    fake = FakeTransport()

    response = _client(fake, tmp_path).complete(request, run_id="r")

    assert (response.text, response.from_cache, response.provider) == ("old answer", True, None)
    assert fake.requests == []


def test_route_provider_sends_order_no_fallbacks_and_require_parameters(tmp_path: Path) -> None:
    fake = FakeTransport()

    _client(fake, tmp_path).complete(_request(route_provider="fireworks"), run_id="r")

    body = _sent_body(fake)
    assert body["provider"] == {"order": ["fireworks"], "allow_fallbacks": False}
    assert body["require_parameters"] is True


def test_temperature_and_seed_none_are_omitted_from_the_request(tmp_path: Path) -> None:
    fake = FakeTransport()

    _client(fake, tmp_path).complete(_request(temperature=None, seed=None), run_id="r")

    body = _sent_body(fake)
    assert "temperature" not in body
    assert "seed" not in body
