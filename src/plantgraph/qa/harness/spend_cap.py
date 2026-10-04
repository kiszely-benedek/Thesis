"""The hard spend cap of a paid run: stop before money could pass `--max-spend-usd`.

Only money actually spent counts. A response served from the cache costs 0 here,
even though its recorded `cost_usd` is what the call cost when first made.

With `--concurrency N` several items run at once, so the guard also tracks
**reservations**: before an item starts it reserves its expected cost, and every
check counts the reservations of the items already in flight. The cap can then be
passed only by what an item spends beyond its own reservation.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from plantgraph.llm.models import ChatResponse


class SpendCapReached(Exception):
    """The next model call or question could take the run's cost to its cap."""


@dataclass(frozen=True)
class Reservation:
    """The cost an item in flight is expected to add; handed back to `SpendGuard.release`."""

    usd: float


class SpendGuard:
    """Tracks a run's cumulative spend and refuses calls that could exceed `cap_usd`.

    All methods are safe to call from several threads.

    Args:
        cap_usd: the hard cap; `None` disables the guard (replay runs spend nothing).
        recorded_usd: cost already recorded in `answers.jsonl` by earlier invocations.
        max_question_usd: the dearest question recorded on disk so far.
        estimate_usd: the user's `--cost-per-question-usd`, used if it is larger.
    """

    def __init__(
        self,
        cap_usd: float | None,
        *,
        recorded_usd: float = 0.0,
        max_question_usd: float = 0.0,
        estimate_usd: float | None = None,
    ) -> None:
        self.cap_usd = cap_usd
        self._lock = threading.Lock()
        self._spent_usd = recorded_usd
        self._max_question_usd = max_question_usd
        self._estimate_usd = estimate_usd or 0.0
        self._max_call_usd = 0.0  # dearest single call made in this invocation
        self._open_reserved_usd = 0.0  # sum of the reservations of items in flight

    @property
    def spent_usd(self) -> float:
        """Recorded cost of earlier invocations plus what this one has spent."""
        with self._lock:
            return self._spent_usd

    def add(self, response: ChatResponse) -> None:
        """Count a finished call; a cache hit costs nothing."""
        if response.from_cache:
            return
        cost = response.cost_usd or 0.0
        with self._lock:
            self._spent_usd += cost
            self._max_call_usd = max(self._max_call_usd, cost)

    def reserve(self) -> Reservation:
        """Open a reservation for one item, or raise if it could take the run to the cap.

        The expected cost is the dearest question seen, or the user's estimate if larger.
        The item's own spend is also in `spent`, so the check is slightly conservative.
        """
        with self._lock:
            expected = max(self._max_question_usd, self._estimate_usd)
            self._check(expected, self._open_reserved_usd, "the next question")
            self._open_reserved_usd += expected
            return Reservation(expected)

    def release(self, reservation: Reservation, spent_usd: float) -> None:
        """Close an item's reservation; what it really spent (0 if cached) feeds the next one."""
        with self._lock:
            self._open_reserved_usd -= reservation.usd
            self._max_question_usd = max(self._max_question_usd, spent_usd)

    def check_before_question(self) -> None:
        """Raise if one more question of the dearest size seen could pass the cap."""
        with self._lock:
            expected = max(self._max_question_usd, self._estimate_usd)
            self._check(expected, self._open_reserved_usd, "the next question")

    def check_before_call(self, own: Reservation | None = None) -> None:
        """Raise if one more call of the dearest size seen could pass the cap.

        Args:
            own: the calling item's reservation; it is left out of the others' total,
                because the item's own spend is already counted in `spent`.
        """
        with self._lock:
            others = self._open_reserved_usd - (own.usd if own is not None else 0.0)
            self._check(self._max_call_usd, others, "the next call")

    def _check(self, expected_usd: float, reserved_usd: float, what: str) -> None:
        """Caller holds the lock."""
        if self.cap_usd is None:
            return
        if self._spent_usd + reserved_usd + expected_usd >= self.cap_usd:
            raise SpendCapReached(
                f"{what} (expected up to {expected_usd:.6f} USD, with {reserved_usd:.6f} USD "
                f"reserved by items in flight) could reach or pass the run's cap of "
                f"{self.cap_usd:.6f} USD; {self._spent_usd:.6f} USD spent so far"
            )
