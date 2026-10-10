"""`calls.jsonl` stays one JSON object per line when several threads log at once (ADR-0043).

The harness answers questions on a thread pool, and an abandoned call can log its late answer from
its own thread; before the log lock was used, two appends could interleave and leave a blank line.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import SecretStr

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.llm.models import ChatMessage, ChatRequest, ModelPin
from plantgraph.llm.openrouter_settings import OpenRouterSettings

_THREADS = 8
_CALLS = 200


def _request(index: int) -> ChatRequest:
    pin = ModelPin(backend="openrouter", model_id="m", temperature=0.0, max_output_tokens=16)
    message = ChatMessage(role="user", content=f"question {index}")
    return ChatRequest(pin=pin, messages=[message], purpose="answer")


def test_concurrent_calls_leave_one_json_object_per_line(tmp_path: Path) -> None:
    client = ChatClient.for_openrouter(
        OpenRouterSettings(api_key=SecretStr("test-key")),
        cache=SqliteCache(tmp_path / "cache.sqlite", "live"),
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
        http_client=FakeTransport().as_httpx_client(),
    )

    with ThreadPoolExecutor(max_workers=_THREADS) as pool:
        list(pool.map(lambda i: client.complete(_request(i), run_id="r"), range(_CALLS)))

    lines = (tmp_path / "calls.jsonl").read_text(encoding="utf-8").split("\n")
    assert lines[-1] == ""  # the file ends with a newline, and nothing else is empty
    records = [json.loads(line) for line in lines[:-1]]
    assert len(records) == _CALLS
