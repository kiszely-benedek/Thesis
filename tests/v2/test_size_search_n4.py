"""Step 0 of T6 (design 17.14 N4): the v2.2 size search takes the total nearest the target.

A unit that opens an area adds its header sheets at once, so "at least the target" overshoots by up
to four sheets. The search now lands within +-3 of the target and inside the user's band
(90-110, 900-1,100), and raises when the nearest total is outside it. v2.1 keeps "at least".
"""

from __future__ import annotations

import pytest

from plantgraph.ingest import size_search_networked
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.size_search_networked import (
    sheet_band_of,
    smallest_n_units_total_sheets,
)


def _assert_inside(target: int, seed: int) -> None:
    found = smallest_n_units_v2(target, HeadlinePresetV22(), seed)
    low, high = sheet_band_of(target) or (0, 10**9)
    assert abs(found.predicted_sheets - target) <= 3
    assert low <= found.predicted_sheets <= high


@pytest.mark.parametrize("target", [90, 100, 110])
def test_the_hundred_scale_lands_within_three_sheets_and_in_the_band(target: int) -> None:
    _assert_inside(target, 7)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_the_hundred_target_holds_on_seeds_one_to_five(seed: int) -> None:
    _assert_inside(100, seed)


@pytest.mark.parametrize("target", [900, 1000, 1100])
def test_the_thousand_scale_lands_within_three_sheets_and_in_the_band(target: int) -> None:
    _assert_inside(target, 7)


def test_the_bands_are_the_users_and_a_ladder_target_has_none() -> None:
    assert sheet_band_of(90) == (90, 110) and sheet_band_of(110) == (90, 110)
    assert sheet_band_of(900) == (900, 1100) and sheet_band_of(1100) == (900, 1100)
    assert sheet_band_of(3) is None and sheet_band_of(500) is None


def _search(totals: dict[int, int], target: int) -> tuple[int, int]:
    """Run the search over a made-up table of totals (units -> sheets), without a plan."""

    class _Plan:
        def __init__(self, sheets: int) -> None:
            self.sheet_count = sheets

    original = size_search_networked.plan_plant
    size_search_networked.plan_plant = lambda n: _Plan(_total(totals, n))  # type: ignore[assignment]
    try:
        found = smallest_n_units_total_sheets(target, lambda n: n, 0)
    finally:
        size_search_networked.plan_plant = original
    return found.n_units, found.predicted_sheets


def _total(totals: dict[int, int], n_units: int) -> int:
    """The table's total, continued by 5 sheets a unit beyond its end (the search probes far)."""
    last = len(totals)
    return totals[n_units] if n_units <= last else totals[last] + 5 * (n_units - last)


def _totals(*sheets: int) -> dict[int, int]:
    return {n: total for n, total in enumerate(sheets, start=1)}


def test_the_nearer_of_the_two_neighbouring_totals_wins() -> None:
    # 100 lies 1 below and 4 above: the lower total is nearer
    assert _search(_totals(*range(90, 109, 1)), 100) == (11, 100)
    below_nearer = _totals(95, 99, 104, 105, 106, 107, 108, 109, 110, 111)
    assert _search(below_nearer, 100) == (2, 99)
    above_nearer = _totals(95, 97, 101, 105, 106, 107, 108, 109, 110, 111)
    assert _search(above_nearer, 100) == (3, 101)


def test_a_tie_goes_to_the_fewer_units() -> None:
    assert _search(_totals(96, 98, 102, 104, 106, 108, 110, 112, 114, 116), 100) == (2, 98)


def test_two_sizes_with_one_total_count_as_one_and_the_fewer_units_win() -> None:
    assert _search(_totals(95, 99, 99, 99, 103, 105, 107, 109, 110, 111), 100) == (2, 99)


def test_a_total_outside_the_band_raises() -> None:
    with pytest.raises(ValueError, match="expected a plant of 90-110 sheets"):
        _search(_totals(60, 70, 80, 120, 130, 140, 150, 160, 170, 180), 100)


def test_the_v21_search_keeps_at_least_semantics() -> None:
    found = smallest_n_units_v2(30, HeadlinePresetV2(), 1)
    assert found.predicted_sheets >= 30 > found.predicted_sheets_one_unit_fewer
