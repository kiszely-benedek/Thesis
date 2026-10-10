"""Split timers for the local (non-model) part of one question's time (`infra-cost.md` §4.1).

The harness reports a question's local compute as one number. A `LocalTimer` breaks it up by
what the time was spent on: the database round-trip as the client sees it (`db_client`), the
database's own share of it as the server reports it (`db_server`), and the plant-API tools
(`graph_api`). What is left over is "other". One timer belongs to one question; callers write
`with local_timer("graph_api"):` and the time lands in the timer of the question the thread
is answering. With no active timer (tests, the demo) the block just runs.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field

#: Kinds the code uses; the timer itself accepts any name.
DB_CLIENT = "db_client"
DB_SERVER = "db_server"
GRAPH_API = "graph_api"


@dataclass
class LocalTimer:
    """Seconds and call counts per kind for one question (a plain dataclass: hot path)."""

    #: Injectable so tests get exact sums.
    clock: Callable[[], float] = time.perf_counter
    seconds: dict[str, float] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)
    #: How many blocks of each kind are open now, so a nested block of the same kind is not
    #: counted twice.
    _open: dict[str, int] = field(default_factory=dict)

    def add(self, kind: str, seconds: float) -> None:
        """Count one call of `kind` that took `seconds`."""
        self.seconds[kind] = self.seconds.get(kind, 0.0) + seconds
        self.calls[kind] = self.calls.get(kind, 0) + 1

    def seconds_of(self, kind: str) -> float:
        """Total seconds of `kind` (0 when none was timed)."""
        return self.seconds.get(kind, 0.0)

    def calls_of(self, kind: str) -> int:
        """Number of calls of `kind` (0 when none was timed)."""
        return self.calls.get(kind, 0)

    def activate(self) -> Token[LocalTimer | None]:
        """Make this the timer of the current thread's question; pass the token to `deactivate`."""
        return _ACTIVE_TIMER.set(self)


#: The timer of the question this thread is answering (one per thread, like the usage meter).
_ACTIVE_TIMER: ContextVar[LocalTimer | None] = ContextVar("active_local_timer", default=None)


def deactivate(token: Token[LocalTimer | None]) -> None:
    """Undo `LocalTimer.activate`."""
    _ACTIVE_TIMER.reset(token)


def active_local_timer() -> LocalTimer | None:
    """The timer of the question this thread is answering, if any."""
    return _ACTIVE_TIMER.get()


def add_local_seconds(kind: str, seconds: float) -> None:
    """Add already-measured seconds (the server's own figure) to the active timer, if any."""
    timer = _ACTIVE_TIMER.get()
    if timer is not None:
        timer.add(kind, seconds)


@contextmanager
def local_timer(kind: str) -> Iterator[None]:
    """Time the block under `kind`; a no-op without an active timer."""
    timer = _ACTIVE_TIMER.get()
    if timer is None:
        yield
        return
    depth = timer._open.get(kind, 0)
    timer._open[kind] = depth + 1
    started = timer.clock()
    try:
        yield
    finally:
        timer._open[kind] = depth
        if depth == 0:  # only the outermost block of a kind counts
            timer.add(kind, timer.clock() - started)
