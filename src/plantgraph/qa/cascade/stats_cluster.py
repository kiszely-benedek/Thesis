"""Two-stage cluster bootstrap over plants, then questions (design `review-fixes.md` section 5.2).

Questions of one plant share a plant, so they are not independent. A resample first draws plants
with replacement, then draws the questions inside each drawn plant with replacement; the pooled
value is the equal-weight mean of the drawn plants' means. The resample count and the seed are the
EXP-0007 claims code's (`stats.N_RESAMPLES`, `stats.BOOTSTRAP_SEED`).

With ONE plant on each side the registered single-plant bootstrap runs unchanged, so a one-plant
call reproduces the first measurement's interval exactly (same seed, same random draws).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from statistics import fmean

from plantgraph.qa.cascade.stats import (
    BOOTSTRAP_SEED,
    N_RESAMPLES,
    Interval,
    PairedDifference,
    paired_bootstrap,
    percentile,
    unpaired_bootstrap,
)

#: One value per question, grouped by plant: `plants[p][q]`.
PlantValues = Sequence[Sequence[float]]


def pooled_mean(plants: PlantValues) -> float:
    """Equal-weight mean over plants of each plant's mean (equal n makes it the question mean)."""
    _require_plants(plants, "a pooled mean")
    return fmean(fmean(values) for values in plants)


def _require_plants(plants: PlantValues, what: str) -> None:
    if not plants or any(not values for values in plants):
        sizes = [len(values) for values in plants]
        raise ValueError(
            f"expected at least one plant, each with questions, for {what}; found {sizes}"
        )


def _draw_pooled_mean(plants: PlantValues, rng: random.Random) -> float:
    """One two-stage resample: draw plants, then each drawn plant's questions."""
    drawn = [rng.randrange(len(plants)) for _ in range(len(plants))]
    return fmean(_resampled_mean(plants[p], rng) for p in drawn)


def _resampled_mean(values: Sequence[float], rng: random.Random) -> float:
    n = len(values)
    return sum(values[rng.randrange(n)] for _ in range(n)) / n


def _differences(a: PlantValues, b: PlantValues) -> list[list[float]]:
    """Per plant, the per-question differences a - b; both arms must hold the same questions."""
    if [len(x) for x in a] != [len(y) for y in b]:
        raise ValueError(
            f"expected both arms on the same plants and questions, "
            f"found sizes {[len(x) for x in a]} and {[len(y) for y in b]}"
        )
    return [[x - y for x, y in zip(xs, ys, strict=True)] for xs, ys in zip(a, b, strict=True)]


def cluster_paired_bootstrap(
    a: PlantValues,
    b: PlantValues,
    n_resamples: int = N_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> PairedDifference:
    """Pooled mean of (a - b) with a two-stage bootstrap; the pair (a, b) always moves together.

    The same seed and the same plant sizes give the same draw for every arm pair, so all paired
    claims of one report are evaluated on one common set of resamples.

    Raises:
        ValueError: the arms differ in plants or questions, or a plant is empty.
    """
    differences = _differences(a, b)
    _require_plants(differences, "a paired bootstrap")
    if len(differences) == 1:  # registered single-plant path
        return paired_bootstrap(a[0], b[0], n_resamples, seed)
    rng = random.Random(seed)
    means = sorted(_draw_pooled_mean(differences, rng) for _ in range(n_resamples))
    return PairedDifference(
        mean=pooled_mean(differences),
        ci_low=percentile(means, 2.5),
        ci_high=percentile(means, 97.5),
    )


def cluster_unpaired_bootstrap(
    a: PlantValues,
    b: PlantValues,
    combine: Callable[[float, float], float],
    n_resamples: int = N_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Interval:
    """`combine(pooled mean of a, pooled mean of b)`, a two-stage bootstrap on each side on its own.

    For samples with no shared questions (the 100- and 1,000-sheet plants, Q4). One plant on
    each side runs the registered `unpaired_bootstrap`.

    Raises:
        ValueError: a side has no plant, or a plant is empty.
    """
    _require_plants(a, "the first sample")
    _require_plants(b, "the second sample")
    if len(a) == 1 and len(b) == 1:  # registered single-plant path
        return unpaired_bootstrap(
            a[0], b[0], lambda x, y: combine(fmean(x), fmean(y)), n_resamples, seed
        )
    rng = random.Random(seed)
    draws = sorted(
        combine(_draw_pooled_mean(a, rng), _draw_pooled_mean(b, rng)) for _ in range(n_resamples)
    )
    return Interval(
        estimate=combine(pooled_mean(a), pooled_mean(b)),
        ci_low=percentile(draws, 2.5),
        ci_high=percentile(draws, 97.5),
    )


def cluster_mean_interval(
    plants: PlantValues, n_resamples: int = N_RESAMPLES, seed: int = BOOTSTRAP_SEED
) -> Interval:
    """The pooled mean with a two-stage bootstrap interval (a pooled accuracy, say)."""
    _require_plants(plants, "a pooled interval")
    rng = random.Random(seed)
    draws = sorted(_draw_pooled_mean(plants, rng) for _ in range(n_resamples))
    return Interval(
        estimate=pooled_mean(plants), ci_low=percentile(draws, 2.5), ci_high=percentile(draws, 97.5)
    )


def same_sign_count(per_plant: Sequence[float], pooled: float) -> int:
    """How many plants' point estimates have the pooled estimate's sign (0 counts for nobody)."""
    if pooled == 0:
        return sum(1 for value in per_plant if value == 0)
    return sum(1 for value in per_plant if value * pooled > 0)
