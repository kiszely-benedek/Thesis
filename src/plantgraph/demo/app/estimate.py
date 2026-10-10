"""What a question is expected to cost, read from recorded runs (never typed in).

A tier's cost per question is taken from every recorded run that used the tier's strategy
under the tier's model pin; the figures are the median (what usually happens) and the
maximum (the worst seen, which a spending reservation is built on).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from pathlib import Path

from plantgraph.demo.app.models import CostEstimate, TierCostStats
from plantgraph.qa.cascade.models import CascadePolicy, TierSpec
from plantgraph.qa.cascade.signals import abandoned_cost_usd
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import QuestionResult, RunConfig

#: A reservation is this many times the sum of the tiers' worst seen costs.
RESERVATION_FACTOR = 1.5


class NoCostEvidence(ValueError):
    """No recorded run matches a tier, so its cost cannot be estimated."""


def estimate_cost(policy: CascadePolicy, run_dirs: Sequence[Path], corpus_id: str) -> CostEstimate:
    """Cost figures per tier of `policy`, preferring runs of `corpus_id`.

    Raises:
        NoCostEvidence: a tier has no matching run on any corpus.
    """
    runs = [_RecordedRun.load(path) for path in run_dirs]
    per_tier = {tier.name: _tier_stats(tier, runs, corpus_id) for tier in policy.tiers}
    worst_total = sum(stats.max_usd for stats in per_tier.values())
    return CostEstimate(per_tier=per_tier, reservation_usd=RESERVATION_FACTOR * worst_total)


class _RecordedRun:
    """A finished run's config and rows, read once."""

    def __init__(self, config: RunConfig, rows: list[QuestionResult]) -> None:
        self.config = config
        self.rows = rows

    @classmethod
    def load(cls, path: Path) -> _RecordedRun:
        run = RunDir(path)
        if not run.config_path.exists():
            raise FileNotFoundError(f"expected run_config.json in {path}, found none")
        config = RunConfig.model_validate_json(run.config_path.read_text(encoding="utf-8"))
        return cls(config, run.read_rows())

    def costs_of(self, tier: TierSpec) -> list[float]:
        """Per-question cost of the tier's rows; empty when the pin or strategy differs."""
        if self.config.answer_pin.pin_hash() != tier.pin_sha256:
            return []
        return [_question_cost(row) for row in self.rows if row.strategy == tier.strategy]


def _question_cost(row: QuestionResult) -> float:
    """All calls of the question, plus the estimate for abandoned ones (as the cascade counts)."""
    total = row.total_cost_usd
    if total is None:
        raise ValueError(f"expected a cost on every call of {row.question_id!r}, found a gap")
    return total + abandoned_cost_usd(row)


def _tier_stats(tier: TierSpec, runs: Sequence[_RecordedRun], corpus_id: str) -> TierCostStats:
    own = [run for run in runs if run.config.corpora == [corpus_id] and run.costs_of(tier)]
    others = [run for run in runs if run not in own and run.costs_of(tier)]
    chosen = own or others
    if not chosen:
        raise NoCostEvidence(
            f"expected a recorded run of strategy {tier.strategy!r} under pin "
            f"{tier.pin_sha256[:8]} for tier {tier.name!r}, found none among {len(runs)} runs"
        )
    costs = [cost for run in chosen for cost in run.costs_of(tier)]
    return TierCostStats(
        median_usd=statistics.median(costs),
        max_usd=max(costs),
        n_questions=len(costs),
        run_ids=tuple(run.config.run_id for run in chosen),
        other_corpus=not own,
    )
