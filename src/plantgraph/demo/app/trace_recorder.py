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
    """One HTTP attempt: the body sent and, if one came back, the body received.

    An attempt is recorded when it starts, so the page can show it while it is still waiting
    for the model; `running` tells such an attempt apart from a finished one.
    """

    request_json: dict[str, Any]
    #: `None` while the attempt runs, or when it failed before a reply (a timeout, a dropped link).
    response_json: dict[str, Any] | None
    #: The HTTP status; `None` while the attempt runs or when no reply came.
    status: int | None
    #: Seconds the attempt took; `0.0` while it runs.
    elapsed_s: float
    #: When the attempt was sent: seconds since the recorder was made (`RecordingTransport.now_s`).
    started_s: float = 0.0
    #: Why the attempt failed: the exception's class name (`ReadTimeout`), or `HTTP 502` for a
    #: reply with status 400 or more. `None` for a reply that was accepted, and while it runs.
    error: str | None = None

    @property
    def running(self) -> bool:
        """True while the attempt has neither a reply nor an error."""
        return self.status is None and self.response_json is None and self.error is None

    @property
    def failed(self) -> bool:
        """True when the provider or the network refused the attempt."""
        return self.error is not None


class RecordingTransport(httpx2.BaseTransport):
    """Passes every request to `inner` unchanged and keeps a copy of both bodies."""

    def __init__(self, inner: httpx2.BaseTransport) -> None:
        self._inner = inner
        self._epoch = time.perf_counter()
        self._lock = threading.Lock()  # abandoned calls finish on their own threads
        self._exchanges: list[Exchange] = []

    def now_s(self) -> float:
        """Seconds since this recorder was made, on the clock `Exchange.started_s` uses."""
        return time.perf_counter() - self._epoch

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        """Send the request through `inner`; errors propagate exactly as without recording."""
        started_s = self.now_s()
        position = self._start(Exchange(_json_object(request.content), None, None, 0.0, started_s))
        try:
            response = self._inner.handle_request(request)
            response.read()  # the SDK reads the whole body anyway (no streaming is used)
        except Exception as error:
            self._finish(position, None, None, started_s, type(error).__name__)
            raise
        status = response.status_code
        failure = f"HTTP {status}" if status >= 400 else None
        self._finish(position, _json_object(response.content) or None, status, started_s, failure)
        return response

    def exchanges(self) -> tuple[Exchange, ...]:
        """A snapshot of every attempt so far, running ones included, in the order they started."""
        with self._lock:
            return tuple(self._exchanges)

    def close(self) -> None:
        """Close the wrapped transport."""
        self._inner.close()

    def _start(self, running: Exchange) -> int:
        """Keep the attempt now; the returned position is where its result will be filled in."""
        with self._lock:
            self._exchanges.append(running)
            return len(self._exchanges) - 1

    def _finish(
        self,
        position: int,
        response_json: dict[str, Any] | None,
        status: int | None,
        started_s: float,
        error: str | None,
    ) -> None:
        with self._lock:
            request_json = self._exchanges[position].request_json
            elapsed_s = self.now_s() - started_s
            self._exchanges[position] = Exchange(
                request_json, response_json, status, elapsed_s, started_s, error
            )


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
    #: The recorder's clock at the mark: an attempt's start is shown as seconds into the ask.
    mark_s: float = 0.0

    @classmethod
    def open(cls, recorder: RecordingTransport, calls_log_path: Path) -> TraceWindow:
        """Mark the present moment as the start of an ask."""
        size = calls_log_path.stat().st_size if calls_log_path.exists() else 0
        return cls(recorder, len(recorder.exchanges()), calls_log_path, size, recorder.now_s())

    def exchanges(self) -> tuple[Exchange, ...]:
        """The attempts recorded since the mark, running ones included."""
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
