"""Small statistics for the cascade comparison: percentiles and a paired bootstrap.

Pure functions on number lists; nothing here knows what a question or a policy is.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

N_RESAMPLES = 5000
BOOTSTRAP_SEED = 1


class PairedDifference(BaseModel):
    """Mean of (a - b) over questions, with a 95 % percentile bootstrap interval."""

    model_config = ConfigDict(frozen=True)

    mean: float
    ci_low: float
    ci_high: float


def percentile(values: Sequence[float], q: float) -> float:
    """The q-th percentile (0..100), nearest-rank method: the smallest value covering q %."""
    if not values:
        raise ValueError("expected at least one value for a percentile, found none")
    rank = max(math.ceil(len(values) * q / 100), 1)
    return sorted(values)[rank - 1]


def median(values: Sequence[float]) -> float:
    """The usual median: the middle value, or the mean of the two middle ones."""
    if not values:
        raise ValueError("expected at least one value for a median, found none")
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    n_resamples: int = N_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> PairedDifference:
    """Resample questions with replacement; the pair (a_i, b_i) always moves together.

    Raises:
        ValueError: the two lists differ in length or are empty.
    """
    if len(a) != len(b) or not a:
        raise ValueError(f"expected two equal-length non-empty lists, found {len(a)} and {len(b)}")
    differences = [x - y for x, y in zip(a, b, strict=True)]
    rng = random.Random(seed)
    n = len(differences)
    means = sorted(
        sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_resamples)
    )
    return PairedDifference(
        mean=sum(differences) / n,
        ci_low=percentile(means, 2.5),
        ci_high=percentile(means, 97.5),
    )


class Interval(BaseModel):
    """A point estimate with a 95 % interval."""

    model_config = ConfigDict(frozen=True)

    estimate: float
    ci_low: float
    ci_high: float

    def contains_zero(self) -> bool:
        """Whether 0 lies inside the interval (borders included)."""
        return self.ci_low <= 0.0 <= self.ci_high


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Interval:
    """Wilson score interval of a proportion; unlike a bootstrap it stays sensible at 100 %.

    Raises:
        ValueError: `total` is not positive, or `successes` is outside 0..total.
    """
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError(f"expected 0 <= successes <= total, total > 0; found {successes}/{total}")
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return Interval(estimate=p, ci_low=max(centre - spread, 0.0), ci_high=min(centre + spread, 1.0))


def bootstrap_interval(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float],
    n_resamples: int = N_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Interval:
    """Percentile bootstrap of any statistic of one sample (e.g. its median or p90)."""
    if not values:
        raise ValueError("expected at least one value to bootstrap, found none")
    rng = random.Random(seed)
    draws = sorted(statistic(rng.choices(values, k=len(values))) for _ in range(n_resamples))
    return Interval(
        estimate=statistic(values), ci_low=percentile(draws, 2.5), ci_high=percentile(draws, 97.5)
    )


def unpaired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    statistic: Callable[[Sequence[float], Sequence[float]], float],
    n_resamples: int = N_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Interval:
    """Percentile bootstrap of a statistic of two independent samples (e.g. two corpora).

    Each sample is resampled on its own, because the questions of H100 and H1000 are not pairs.
    """
    if not a or not b:
        raise ValueError(f"expected two non-empty samples, found {len(a)} and {len(b)}")
    rng = random.Random(seed)
    draws = sorted(
        statistic(rng.choices(a, k=len(a)), rng.choices(b, k=len(b))) for _ in range(n_resamples)
    )
    return Interval(
        estimate=statistic(a, b), ci_low=percentile(draws, 2.5), ci_high=percentile(draws, 97.5)
    )


def interval_of(difference: PairedDifference) -> Interval:
    """A paired difference viewed as an `Interval` (its mean is the estimate)."""
    return Interval(estimate=difference.mean, ci_low=difference.ci_low, ci_high=difference.ci_high)
