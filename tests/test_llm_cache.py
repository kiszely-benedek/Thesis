"""`cache_key` and `SqliteCache` (design `qa-system.md` §6, ADR-0014, coder task QA-T1).

No network, no paid call anywhere here: every test talks to a throwaway
SQLite file under `tmp_path` and builds requests by hand.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.cache import SqliteCache, cache_key
from plantgraph.llm.models import CacheMiss, ChatMessage, ChatRequest, ChatResponse, ModelPin


def _request(**overrides: object) -> ChatRequest:
    pin = ModelPin(
        backend="openrouter",
        model_id="openai/gpt-5-mini",
        route_provider="openai",
        temperature=0.0,
        seed=42,
        max_output_tokens=512,
    )
    defaults: dict[str, object] = {
        "pin": pin,
        "messages": [ChatMessage(role="user", content="What is P-101?")],
        "json_mode": True,
        "purpose": "answer",
    }
    defaults.update(overrides)
    return ChatRequest.model_validate(defaults)


def _response(**overrides: object) -> ChatResponse:
    defaults: dict[str, object] = {
        "text": "A centrifugal pump.",
        "prompt_tokens": 240,
        "completion_tokens": 12,
        "cost_usd": 0.0009,
        "latency_s": 1.42,
        "provider_response_id": "gen-xyz",
        "finish_reason": "stop",
        "from_cache": False,
        "created_at": datetime(2026, 9, 26, 9, 30, 0),
    }
    defaults.update(overrides)
    return ChatResponse.model_validate(defaults)


def test_same_request_gives_the_same_key() -> None:
    assert cache_key(_request()) == cache_key(_request())


def test_a_changed_generation_parameter_gives_a_different_key() -> None:
    baseline = cache_key(_request())

    changed_pin = _request().pin.model_copy(update={"temperature": 0.9})
    assert cache_key(_request(pin=changed_pin)) != baseline

    changed_pin = _request().pin.model_copy(update={"seed": 1})
    assert cache_key(_request(pin=changed_pin)) != baseline

    changed_pin = _request().pin.model_copy(update={"max_output_tokens": 64})
    assert cache_key(_request(pin=changed_pin)) != baseline

    changed_pin = _request().pin.model_copy(update={"extra": {"reasoning_effort": "high"}})
    assert cache_key(_request(pin=changed_pin)) != baseline


def test_a_changed_message_gives_a_different_key() -> None:
    baseline = cache_key(_request())

    different_content = [ChatMessage(role="user", content="What is P-102?")]
    assert cache_key(_request(messages=different_content)) != baseline

    different_role = [ChatMessage(role="system", content="What is P-101?")]
    assert cache_key(_request(messages=different_role)) != baseline

    extra_message = [
        ChatMessage(role="user", content="What is P-101?"),
        ChatMessage(role="user", content="And its unit?"),
    ]
    assert cache_key(_request(messages=extra_message)) != baseline


def test_json_mode_is_part_of_the_key() -> None:
    assert cache_key(_request(json_mode=True)) != cache_key(_request(json_mode=False))


def test_purpose_is_not_part_of_the_key() -> None:
    # §6: purpose is logged for the run-log breakdown, but two identical
    # requests made for different reasons must still share one cache entry.
    assert cache_key(_request(purpose="answer")) == cache_key(_request(purpose="judge"))


def test_put_then_get_round_trips_the_full_response(tmp_path: Path) -> None:
    request = _request()
    response = _response()
    cache = SqliteCache(tmp_path / "cache.sqlite", mode="live")

    cache.put(request, response)
    restored = cache.get(request)

    assert restored == response
    assert restored is not None
    assert restored.prompt_tokens == 240
    assert restored.completion_tokens == 12
    assert restored.latency_s == 1.42
    assert restored.created_at == datetime(2026, 9, 26, 9, 30, 0)


def test_live_mode_miss_returns_none(tmp_path: Path) -> None:
    cache = SqliteCache(tmp_path / "cache.sqlite", mode="live")

    assert cache.get(_request()) is None


def test_replay_mode_miss_raises_cache_miss(tmp_path: Path) -> None:
    cache = SqliteCache(tmp_path / "cache.sqlite", mode="replay")

    with pytest.raises(CacheMiss):
        cache.get(_request())


def test_replay_mode_hit_does_not_raise(tmp_path: Path) -> None:
    request = _request()
    response = _response()
    seed_cache = SqliteCache(tmp_path / "cache.sqlite", mode="live")
    seed_cache.put(request, response)

    replay_cache = SqliteCache(tmp_path / "cache.sqlite", mode="replay")

    assert replay_cache.get(request) == response


def test_put_overwrites_an_existing_entry_for_the_same_key(tmp_path: Path) -> None:
    request = _request()
    cache = SqliteCache(tmp_path / "cache.sqlite", mode="live")

    cache.put(request, _response(text="first answer"))
    cache.put(request, _response(text="second answer"))

    restored = cache.get(request)
    assert restored is not None
    assert restored.text == "second answer"


def test_cache_survives_reopening_the_same_file(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    request = _request()
    response = _response()

    with SqliteCache(path, mode="live") as cache:
        cache.put(request, response)

    with SqliteCache(path, mode="replay") as reopened:
        assert reopened.get(request) == response


_STABILITY_SCRIPT = """
import json
from plantgraph.llm.cache import cache_key
from plantgraph.llm.models import ChatMessage, ChatRequest, ModelPin

pin = ModelPin(
    backend="openrouter",
    model_id="openai/gpt-5-mini",
    route_provider="openai",
    temperature=0.0,
    seed=42,
    max_output_tokens=512,
)
request = ChatRequest(
    pin=pin,
    messages=[ChatMessage(role="user", content="What is P-101?")],
    json_mode=True,
    purpose="answer",
)
print(cache_key(request))
"""


def _run_with_hash_seed(hash_seed: str) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    result = subprocess.run(
        [sys.executable, "-c", _STABILITY_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    return result.stdout.strip()


def test_cache_key_is_stable_across_processes_with_different_hash_seeds() -> None:
    # The key must not depend on Python's per-process randomized hash():
    # forcing two very different PYTHONHASHSEED values must still produce
    # byte-identical keys, since canonical_hash uses sha256 on sorted JSON.
    key_a = _run_with_hash_seed("0")
    key_b = _run_with_hash_seed("4000000000")

    assert key_a == key_b
    assert len(key_a) == 64, "sha256 hex digest"
    assert key_a == cache_key(_request()), "same request, in-process or subprocess"
