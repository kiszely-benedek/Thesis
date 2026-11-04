"""Cluster bootstrap over blocks, with paired resamples (design section 6).

Why clusters: pairs that share a blocking key compete for the same occurrences (the one-to-one
rule), so they are not independent. We resample whole blocks, never single pairs.
Why one shared resample: every metric is computed from the SAME resampled blocks, so a difference
between two deciders is a paired difference and its interval is honest about their correlation.

Plain `random.Random(seed)` keeps the result reproducible without a numpy dependency.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.exp0004.metrics import Counts, f1_of_counts

N_RESAMPLES = 2000
SEED = 20261104
CONFIDENCE = 0.95

#: per block, the counts of every metric (a metric is e.g. "d1|format")
BlockCounts = Mapping[str, Counts]


class Interval(BaseModel):
    """A percentile confidence interval; both ends None when no resample had a defined value."""

    model_config = ConfigDict(frozen=True)

    low: float | None
    high: float | None


def resample_f1(
    blocks: Sequence[BlockCounts],
    metrics: Sequence[str],
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
) -> dict[str, list[float | None]]:
    """F1 of every metric on each of `n_resamples` block resamples (the resamples are shared)."""
    if not blocks:
        raise ValueError("expected at least one block to resample, got none")
    rng = random.Random(seed)
    n_blocks = len(blocks)
    results: dict[str, list[float | None]] = {metric: [] for metric in metrics}
    for _ in range(n_resamples):
        multiplicity = Counter(rng.choices(range(n_blocks), k=n_blocks))
        for metric in metrics:
            results[metric].append(f1_of_counts(_total(blocks, metric, multiplicity)))
    return results


def paired_difference(plus: Sequence[float | None], minus: Sequence[float | None]) -> list[float]:
    """`plus - minus` per resample, skipping resamples where either F1 is undefined."""
    if len(plus) != len(minus):
        raise ValueError(f"expected equal numbers of resamples, got {len(plus)} and {len(minus)}")
    return [a - b for a, b in zip(plus, minus, strict=True) if a is not None and b is not None]


def interval_of(values: Sequence[float | None], confidence: float = CONFIDENCE) -> Interval:
    """Percentile interval of the defined values (nearest rank, no interpolation)."""
    defined = sorted(value for value in values if value is not None)
    if not defined:
        return Interval(low=None, high=None)
    tail = (1.0 - confidence) / 2.0
    last = len(defined) - 1
    return Interval(low=defined[round(tail * last)], high=defined[round((1.0 - tail) * last)])


def _total(blocks: Sequence[BlockCounts], metric: str, multiplicity: Counter[int]) -> Counts:
    """Sum a metric's counts over the resample (each block counted as often as it was drawn)."""
    total = Counts(0, 0, 0)
    for block_index, times in multiplicity.items():
        total = total.plus(blocks[block_index][metric], times)
    return total
