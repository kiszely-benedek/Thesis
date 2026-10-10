"""The session spend cap, the per-question reservation and the demo's all-time spend."""

from __future__ import annotations

from pathlib import Path

from plantgraph.demo.app.models import CostEstimate, SpendStatus
from plantgraph.llm.models import CallRecord
from plantgraph.qa.harness.spend_cap import Reservation, SpendGuard


def total_spent_usd(calls_log: Path) -> float:
    """Money all calls in `calls_log` cost: cache hits are free, a late answer is billed."""
    if not calls_log.exists():
        return 0.0
    records = [
        CallRecord.model_validate_json(line)
        for line in calls_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    paid = [r.response for r in records if r.response is not None and not r.response.from_cache]
    return sum(response.cost_usd or 0.0 for response in paid)


class SessionSpend:
    """One server session's money: the guard the cascade charges, and the status shown."""

    def __init__(self, cap_usd: float | None, estimate: CostEstimate, calls_log: Path) -> None:
        self.estimate = estimate
        self._calls_log = calls_log
        # `estimate_usd` makes `guard.reserve()` set aside the estimate's reservation.
        self.guard = SpendGuard(cap_usd, estimate_usd=estimate.reservation_usd)

    def reserve(self) -> Reservation:
        """Set money aside for one confirmed question.

        The guard counts money spent plus every open reservation plus this one against the
        cap, so concurrent questions cannot jointly pass it.

        Raises:
            SpendCapReached: that total would reach the session cap.
        """
        return self.guard.reserve()

    def release(self, reservation: Reservation, spent_usd: float) -> None:
        """Close the question's reservation; `spent_usd` is what it really cost."""
        self.guard.release(reservation, spent_usd)

    def status(self) -> SpendStatus:
        """Session spend, cap and the all-time total (re-read from the calls log)."""
        return SpendStatus(
            session_spent_usd=self.guard.spent_usd,
            session_cap_usd=self.guard.cap_usd,
            demo_total_spent_usd=total_spent_usd(self._calls_log),
        )
