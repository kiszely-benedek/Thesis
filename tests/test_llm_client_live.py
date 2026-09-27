"""One real OpenRouter call — paid, run only by the user (design `qa-system.md` §16, §18.2).

Skipped unless pytest is given `--live-llm` (`tests/conftest.py`). Even then,
this test still constructs `ChatClient` with `allow_network=True` itself —
that is the coder's business, never something read from the environment, so
`OPENROUTER_API_KEY` being set in `.env` is never mistaken for permission to
spend money (§6, the paid-call guard).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ChatMessage, ChatRequest, ModelPin
from plantgraph.llm.openrouter_settings import from_env

pytestmark = pytest.mark.live_llm


def test_one_real_openrouter_call(tmp_path: Path) -> None:
    settings = from_env()
    if settings is None:
        pytest.skip("OPENROUTER_API_KEY not set (in the environment or .env)")

    cache = SqliteCache(tmp_path / "cache.sqlite", mode="live")
    client = ChatClient.for_openrouter(
        settings,
        cache=cache,
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
    )
    # A placeholder model id: the pilot's listing snapshot (§12 step 1) picks
    # the real one this thesis pins. This smoke call only proves the key,
    # the provider pin and require_parameters reach OpenRouter and get a
    # real response back.
    pin = ModelPin(backend="openrouter", model_id="openai/gpt-5-mini", max_output_tokens=16)
    request = ChatRequest(
        pin=pin,
        messages=[ChatMessage(role="user", content="Reply with the single word: ok")],
        purpose="probe",
    )

    response = client.complete(request, run_id="live-smoke")

    assert response.text
