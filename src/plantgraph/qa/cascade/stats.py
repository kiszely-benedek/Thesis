"""Small statistics for the cascade comparison: percentiles and a paired bootstrap.

Pure functions on number lists; nothing here knows what a question or a policy is.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

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
