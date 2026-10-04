"""A SQLite cache of LLM calls, keyed by the full request (design `qa-system.md` §6, ADR-0014).

Caching is what makes a reported run **replayable**: the professor can
re-score a run's `answers.jsonl` from this cache without an API key or a
network connection, and re-running the same question never triggers a
second paid call.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Literal

from plantgraph.llm.models import CacheMiss, ChatRequest, ChatResponse, canonical_hash

#: Default location named in `qa-system.md` §6, git-ignored (`.gitignore`:
#: "the LLM response cache") since it can hold real prompts and answers.
DEFAULT_CACHE_PATH = Path("data/llm-cache/cache.sqlite")

#: `"live"`: read-through, a miss is left to the caller to fill in.
#: `"replay"`: cache-only, a miss raises `CacheMiss` (§6).
CacheMode = Literal["live", "replay"]


def cache_key(request: ChatRequest) -> str:
    """Hash of everything that determines the answer: the pin, JSON mode and messages.

    `request.purpose` is deliberately excluded — it labels the call for the
    run log but does not change what the provider would return, so the same
    question asked for two different purposes still hits the same entry.
    """
    payload = {
        "pin": request.pin.model_dump(mode="json"),
        "json_mode": request.json_mode,
        "messages": [message.model_dump(mode="json") for message in request.messages],
    }
    return canonical_hash(payload)


class SqliteCache:
    """Maps a `ChatRequest`'s cache key to its `ChatResponse`, in one SQLite file.

    Safe to share between threads (the harness's `--concurrency N`): one connection,
    opened without SQLite's same-thread check, and every use serialized by a lock.
    """

    def __init__(self, path: Path, mode: CacheMode) -> None:
        self._mode = mode
        path.parent.mkdir(parents=True, exist_ok=True)
        # SQLite refuses a connection used from another thread by default; the lock below
        # makes sharing it safe, so the check is switched off.
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS responses "
            "(key TEXT PRIMARY KEY, response_json TEXT NOT NULL)"
        )
        self._connection.commit()

    def get(self, request: ChatRequest) -> ChatResponse | None:
        """Look up the cached response for `request`.

        Returns:
            The cached `ChatResponse`, or `None` on a miss in `"live"` mode.

        Raises:
            CacheMiss: on a miss in `"replay"` mode — a replay run must never
                fall back to a real call.
        """
        key = cache_key(request)
        with self._lock:
            row = self._connection.execute(
                "SELECT response_json FROM responses WHERE key = ?", (key,)
            ).fetchone()
        if row is not None:
            return ChatResponse.model_validate_json(row[0])
        if self._mode == "replay":
            raise CacheMiss(
                f"No cached response for key {key!r} (purpose={request.purpose!r}) in replay mode"
            )
        return None

    def put(self, request: ChatRequest, response: ChatResponse) -> None:
        """Store `response` under `request`'s cache key, replacing any existing entry."""
        key = cache_key(request)
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO responses (key, response_json) VALUES (?, ?)",
                (key, response.model_dump_json()),
            )
            self._connection.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SqliteCache:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
