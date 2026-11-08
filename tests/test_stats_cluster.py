"""Two-stage cluster bootstrap: one plant is the registered code, several cover the mean."""

from __future__ import annotations

import random
from statistics import fmean

import pytest

from plantgraph.qa.cascade.stats import paired_bootstrap, unpaired_bootstrap
from plantgraph.qa.cascade.stats_cluster import (
    cluster_mean_interval,
    cluster_paired_bootstrap,
    cluster_unpaired_bootstrap,
    pooled_mean,
    same_sign_count,
)

A = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0]
B = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0]


def test_one_plant_paired_is_exactly_the_registered_bootstrap() -> None:
    assert cluster_paired_bootstrap([A], [B]) == paired_bootstrap(A, B)


def test_one_plant_per_side_unpaired_is_exactly_the_registered_bootstrap() -> None:
    def large_minus_small(small: list[float], large: list[float]) -> float:
        return fmean(large) - fmean(small)

    registered = unpaired_bootstrap(A, B, large_minus_small)
    pooled = cluster_unpaired_bootstrap([A], [B], lambda small, large: large - small)

    assert pooled == registered


def test_pooled_mean_weights_plants_equally() -> None:
    assert pooled_mean([[1.0, 1.0], [0.0, 0.0, 0.0, 0.0]]) == 0.5


def test_every_arm_pair_is_evaluated_on_the_same_draw() -> None:
    plants_a, plants_b = [A, B, A], [B, A, B]
    zeros = [[0.0] * len(p) for p in plants_a]

    paired = cluster_paired_bootstrap(plants_a, zeros)
    interval = cluster_mean_interval(plants_a)

    # a - 0 over a shared draw is the plain two-stage resample of a
    assert (paired.mean, paired.ci_low, paired.ci_high) == (
        interval.estimate,
        interval.ci_low,
        interval.ci_high,
    )
    assert cluster_paired_bootstrap(plants_a, plants_b) == cluster_paired_bootstrap(
        plants_a, plants_b
    )


def test_paired_arms_must_hold_the_same_questions() -> None:
    with pytest.raises(ValueError, match="same plants and questions"):
        cluster_paired_bootstrap([A, B], [A, B[:-1]])


def test_an_empty_plant_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one plant"):
        cluster_mean_interval([A, []])


def test_same_sign_count_ignores_plants_on_the_other_side() -> None:
    assert same_sign_count([0.1, 0.2, -0.05, 0.0], 0.1) == 2
    assert same_sign_count([0.0, 0.0, 0.1], 0.0) == 2


def _coverage(use_plants: bool, replications: int = 100) -> float:
    """Share of datasets whose 95 % interval contains the true mean (0.5)."""
    rng = random.Random(7)
    hits = 0
    for _ in range(replications):
        plants = []
        for _ in range(10):
            p = min(max(0.5 + rng.gauss(0, 0.15), 0.02), 0.98)  # plant effect: the cluster level
            plants.append([float(rng.random() < p) for _ in range(40)])
        if use_plants:
            interval = cluster_mean_interval(plants, n_resamples=150, seed=3)
        else:  # the naive one-stage bootstrap that ignores plants
            flat = [x for plant in plants for x in plant]
            interval = cluster_mean_interval([flat], n_resamples=150, seed=3)
        hits += interval.ci_low <= 0.5 <= interval.ci_high
    return hits / replications


def test_two_stage_interval_covers_the_true_mean_and_beats_ignoring_plants() -> None:
    two_stage, naive = _coverage(True), _coverage(False)

    assert two_stage >= 0.88
    assert two_stage > naive
