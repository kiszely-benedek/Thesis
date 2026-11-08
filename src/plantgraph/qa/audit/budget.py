"""The audit's spend ledger and the sizing that follows from the pilot's measured cost.

Money rule (review-fixes §5.3): the audit including the pilot may not spend more than
`HARD_CAP_USD`, and the pilot alone not more than `PILOT_CAP_USD`. One ledger file holds every
paid call of both stages, so the cap really is shared. Only money actually paid counts: a reply
served from the cache costs nothing here.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

HARD_CAP_USD = 10.0
PILOT_CAP_USD = 1.5
#: Planning figure of the design (≈ 8,000-character prompt, ≈ 800 completion tokens).
ESTIMATED_CALL_USD = 0.015
#: Design worst case: 24,000-character prompt and the full 2,048 output tokens.
WORST_CASE_CALL_USD = 0.042
#: Sizing uses the measured mean cost times this, so a dearer-than-average tail does not
#: push the plan over the budget.
SIZING_SAFETY_FACTOR = 1.25


class LedgerLine(BaseModel):
    """One judged row's payment."""

    model_config = ConfigDict(frozen=True)

    stage: str
    item_key: str
    paid_usd: float = Field(ge=0.0)


class SpendLedger:
    """Append-only JSONL file of payments, read back to decide whether the next call is allowed."""

    def __init__(self, path: Path, cap_usd: float = HARD_CAP_USD) -> None:
        self.path = path
        self.cap_usd = cap_usd

    def lines(self) -> list[LedgerLine]:
        """Every payment on file."""
        if not self.path.exists():
            return []
        text = self.path.read_text(encoding="utf-8")
        return [LedgerLine.model_validate_json(line) for line in text.splitlines() if line]

    def spent_usd(self, stage: str | None = None) -> float:
        """Money paid so far, in one stage or (with `None`) in all of them."""
        return sum(line.paid_usd for line in self.lines() if stage in (None, line.stage))

    def remaining_usd(self) -> float:
        """What is left under the shared hard cap."""
        return max(0.0, self.cap_usd - self.spent_usd())

    def allows(self, call_usd: float, stage: str, stage_cap_usd: float | None = None) -> bool:
        """Whether a call that may cost `call_usd` keeps the run under every cap."""
        if self.spent_usd() + call_usd > self.cap_usd:
            return False
        return stage_cap_usd is None or self.spent_usd(stage) + call_usd <= stage_cap_usd

    def record(self, line: LedgerLine) -> None:
        """Append one payment."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write((line.model_dump_json() + "\n").encode("utf-8"))

    def measured_cost_per_call(self, stage: str) -> float:
        """Mean cost of the paid calls of a stage (cache hits excluded).

        Raises:
            ValueError: the stage has no paid call yet, so there is nothing to measure.
        """
        paid = [line.paid_usd for line in self.lines() if line.stage == stage and line.paid_usd > 0]
        if not paid:
            raise ValueError(f"expected paid calls recorded for stage {stage!r}, found none")
        return sum(paid) / len(paid)


def sizing_cost_per_call(measured_usd: float) -> float:
    """The per-call figure the selection is sized with."""
    return measured_usd * SIZING_SAFETY_FACTOR
