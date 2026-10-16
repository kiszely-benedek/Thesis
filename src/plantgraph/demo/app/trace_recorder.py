"""Records every model request and reply of an ask, by sitting between the SDK and the network.

The model client sends plain HTTP requests; a transport is the layer that actually carries one.
`RecordingTransport` wraps the real (or, in tests, a fake) transport, passes each request on
unchanged and keeps a copy of the request body and the reply body. That copy is what lets the
demo show the query the model wrote, the rows it was given and every tool result it saw.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2

from plantgraph.llm.models import CallRecord


@dataclass(frozen=True)
class Exchange:
    """One HTTP attempt: the body sent and, if one came back, the body received."""

    request_json: dict[str, Any]
    #: `None` when the attempt failed before a reply (a timeout, a connection error).
    response_json: dict[str, Any] | None
    status: int | None
    elapsed_s: float


class RecordingTransport(httpx2.BaseTransport):
    """Passes every request to `inner` unchanged and keeps a copy of both bodies."""

    def __init__(self, inner: httpx2.BaseTransport) -> None:
        self._inner = inner
        self._lock = threading.Lock()  # abandoned calls finish on their own threads
        self._exchanges: list[Exchange] = []

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        """Send the request through `inner`; errors propagate exactly as without recording."""
        started = time.perf_counter()
        request_json = _json_object(request.content)
        try:
            response = self._inner.handle_request(request)
            response.read()  # the SDK reads the whole body anyway (no streaming is used)
        except Exception:
            self._keep(Exchange(request_json, None, None, time.perf_counter() - started))
            raise
        elapsed = time.perf_counter() - started
        body = _json_object(response.content)
        self._keep(Exchange(request_json, body or None, response.status_code, elapsed))
        return response

    def exchanges(self) -> tuple[Exchange, ...]:
        """A snapshot of every exchange so far, in the order the attempts finished."""
        with self._lock:
            return tuple(self._exchanges)

    def close(self) -> None:
        """Close the wrapped transport."""
        self._inner.close()

    def _keep(self, exchange: Exchange) -> None:
        with self._lock:
            self._exchanges.append(exchange)


def _json_object(raw: bytes) -> dict[str, Any]:
    """The body as a JSON object; anything else gives `{}` (the exchange is still kept)."""
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass(frozen=True)
class TraceWindow:
    """Where one ask starts: how much was recorded, and how long the call log was, at that moment.

    Asks run one at a time (the Busy lock), so "everything after the mark" is exactly this ask's
    traffic. A late reply of an earlier, abandoned call may land in the window; the trace builder
    drops it because its call-log line says `late_after_timeout`.
    """

    recorder: RecordingTransport
    exchange_mark: int
    calls_log_path: Path
    log_offset: int

    @classmethod
    def open(cls, recorder: RecordingTransport, calls_log_path: Path) -> TraceWindow:
        """Mark the present moment as the start of an ask."""
        size = calls_log_path.stat().st_size if calls_log_path.exists() else 0
        return cls(recorder, len(recorder.exchanges()), calls_log_path, size)

    def exchanges(self) -> tuple[Exchange, ...]:
        """The exchanges recorded since the mark."""
        return self.recorder.exchanges()[self.exchange_mark :]

    def log_lines(self) -> list[CallRecord]:
        """The call-log lines written since the mark (a half-written last line is left out)."""
        if not self.calls_log_path.exists():
            return []
        with self.calls_log_path.open("rb") as handle:
            handle.seek(self.log_offset)
            raw = handle.read()
        complete = raw.rpartition(b"\n")[0]
        return [CallRecord.model_validate_json(line) for line in complete.splitlines() if line]
