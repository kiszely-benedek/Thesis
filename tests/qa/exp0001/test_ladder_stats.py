"""The ladder statistics on fixtures with known answers."""

from __future__ import annotations

import math

import pytest

from plantgraph.qa.exp0001.ladder_stats import (
    SizeSample,
    chars_per_sheet,
    first_below_zero,
    fits_in_window,
    log10_sheets,
    ols_slope,
    slope_interval,
    wall_in_sheets,
)


def test_ols_slope_of_an_exact_line() -> None:
    assert ols_slope([0, 1, 2, 3], [1, 3, 5, 7]) == pytest.approx(2.0)


def test_ols_slope_refuses_one_point_and_equal_x() -> None:
    with pytest.raises(ValueError, match="2 points"):
        ols_slope([1.0], [1.0])
    with pytest.raises(ValueError, match="different x"):
        ols_slope([1.0, 1.0], [1.0, 2.0])


def test_log10_sheets() -> None:
    assert log10_sheets(1000) == pytest.approx(3.0)
    with pytest.raises(ValueError, match="at least one sheet"):
        log10_sheets(0)


def test_slope_interval_without_noise_collapses_to_the_slope() -> None:
    # constant differences 0.2, 0.0, -0.2 at x = 0, 1, 2: every resample returns them unchanged
    samples = [SizeSample(0.0, [0.2] * 5), SizeSample(1.0, [0.0] * 5), SizeSample(2.0, [-0.2] * 5)]
    interval = slope_interval(samples, n_boot=200, seed=1)
    assert interval.estimate == pytest.approx(-0.2)
    assert interval.ci_low == pytest.approx(-0.2)
    assert interval.ci_high == pytest.approx(-0.2)


def test_slope_interval_with_a_flat_noisy_trend_contains_zero() -> None:
    # +1/-1 alternating at every size: mean 0 everywhere, so the true slope is 0
    noisy = [1.0, -1.0] * 10
    samples = [SizeSample(x, list(noisy)) for x in (0.0, 0.5, 1.0, 1.5)]
    interval = slope_interval(samples, n_boot=500, seed=3)
    assert interval.estimate == pytest.approx(0.0)
    assert interval.ci_low < 0 < interval.ci_high


def test_slope_interval_is_reproducible_for_a_seed() -> None:
    samples = [SizeSample(0.0, [1.0, 0.0, 0.0, 1.0]), SizeSample(1.0, [0.0, -1.0, 0.0, 0.0])]
    assert slope_interval(samples, 100, seed=5) == slope_interval(samples, 100, seed=5)


def test_first_below_zero() -> None:
    bounds = [("H1", 0.05), ("H3", 0.01), ("H10", -0.02), ("H30", -0.1)]
    assert first_below_zero(bounds) == ("H3", "H10")
    assert first_below_zero([("H1", -0.1)]) == (None, "H1")
    assert first_below_zero([("H1", 0.0)]) == ("H1", None)


def test_chars_per_sheet_recovers_the_per_sheet_size_beside_a_template() -> None:
    points = [(n, 768 + 16_300 * n) for n in (1, 3, 10, 30)]
    assert chars_per_sheet(points) == pytest.approx(16_300)


def test_wall_and_fit() -> None:
    assert wall_in_sheets(900_000, 3.0, 15_000) == pytest.approx(180.0)
    assert fits_in_window(1_649_451, 3.0, 922_000)
    assert not fits_in_window(16_747_117, 3.0, 922_000)
    assert not math.isnan(wall_in_sheets(1, 1.0, 1.0))
    with pytest.raises(ValueError, match="positive"):
        wall_in_sheets(1, 0.0, 1.0)
