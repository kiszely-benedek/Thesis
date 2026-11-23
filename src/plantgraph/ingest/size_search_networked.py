"""The size search of a v2.2 plant, counted in total sheets (design 7, decisions D4 and D5).

On v2.1 a plant's sheets are the sum of its units' sheets, so one plan answers the search
(`headline_v2.smallest_n_units_v2`). On v2.2 the network and interarea sheets are a function of the
units included (S15 restated: process parts are prefix-stable, network sheets are not), so each
candidate size is planned in full (a plan has no pyDEXPI, so that is cheap).

A unit that opens a new area adds that area's header sheets at once, so the total jumps by several
sheets. "At least the target" would then overshoot by up to four sheets and could leave the user's
band (design 17.14 N4); the search therefore takes the total **nearest** the target instead.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline import SizeSearchResult

#: the user's sheet bands (decision D5): a plant of about 100 sheets has 90-110, of about 1,000
#: has 900-1,100. A target outside both (the 1-30 sheet ladder) has no band to hold.
SHEET_BANDS: tuple[tuple[int, int], ...] = ((90, 110), (900, 1100))


def sheet_band_of(target_sheets: int) -> tuple[int, int] | None:
    """The band a target belongs to, or None for a target outside every band."""
    return next((band for band in SHEET_BANDS if band[0] <= target_sheets <= band[1]), None)


def smallest_n_units_total_sheets(
    target_sheets: int, generator_config: Callable[[int], object], seed: int
) -> SizeSearchResult:
    """The unit count whose plan has the total sheets nearest `target_sheets` (ties: fewer units).

    `generator_config(n_units)` gives the config of an `n_units` plant. The sheets per unit are
    nearly constant, so each plan rescales the guess (n * target / sheets) until it holds, then
    single steps find the edge; a plan of 1,000 sheets takes seconds, so few are made.

    Raises:
        ValueError: if `target_sheets` is below 1, or the nearest total lies outside the band the
            target belongs to.
    """
    if target_sheets < 1:
        raise ValueError(f"expected target_sheets >= 1, found {target_sheets}")
    seen: dict[int, int] = {}

    def sheets_of(n_units: int) -> int:
        if n_units not in seen:
            seen[n_units] = plan_plant(generator_config(n_units)).sheet_count  # type: ignore[arg-type]
        return seen[n_units]

    first_at_least = _first_at_least(target_sheets, sheets_of)
    n_units = _nearest(target_sheets, first_at_least, sheets_of)
    result = SizeSearchResult(
        target_sheets=target_sheets,
        n_units=n_units,
        predicted_sheets=sheets_of(n_units),
        predicted_sheets_one_unit_fewer=sheets_of(n_units - 1) if n_units > 1 else 0,
    )
    _require_inside_band(result, seed)
    return result


def _first_at_least(target: int, sheets_of: Callable[[int], int]) -> int:
    """The fewest units whose total reaches the target (totals never fall as units are added)."""
    n_units = _rescaled_guess(target, sheets_of)
    while n_units > 1 and sheets_of(n_units - 1) >= target:
        n_units -= 1
    while sheets_of(n_units) < target:
        n_units += 1
    return n_units


def _nearest(target: int, first_at_least: int, sheets_of: Callable[[int], int]) -> int:
    """Of the first size at or above the target and the one below it, the nearer (a tie: below)."""
    below = first_at_least - 1
    if below < 1:
        return first_at_least
    if target - sheets_of(below) <= sheets_of(first_at_least) - target:
        return _fewest_with_same_total(below, sheets_of)
    return first_at_least


def _fewest_with_same_total(n_units: int, sheets_of: Callable[[int], int]) -> int:
    """Walk down a plateau: two sizes with one total count as one, and the fewer units win."""
    while n_units > 1 and sheets_of(n_units - 1) == sheets_of(n_units):
        n_units -= 1
    return n_units


def _require_inside_band(result: SizeSearchResult, seed: int) -> None:
    band = sheet_band_of(result.target_sheets)
    if band is None or band[0] <= result.predicted_sheets <= band[1]:
        return
    raise ValueError(
        f"expected a plant of {band[0]}-{band[1]} sheets for target {result.target_sheets} "
        f"(seed {seed}), the nearest size ({result.n_units} units) has {result.predicted_sheets}"
    )


def _rescaled_guess(target: int, sheets_of: Callable[[int], int]) -> int:
    """A unit count near the answer: rescale until the guess stops moving (at most 4 plans)."""
    n_units = max(1, target // 3)
    for _ in range(4):
        rescaled = max(1, round(n_units * target / sheets_of(n_units)))
        if rescaled == n_units:
            break
        n_units = rescaled
    return n_units
