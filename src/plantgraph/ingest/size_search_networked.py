"""The size search of a v2.2 plant, counted in total sheets (design 7, decision D4).

On v2.1 a plant's sheets are the sum of its units' sheets, so one plan answers the search
(`headline_v2.smallest_n_units_v2`). On v2.2 the network and interarea sheets are a function of the
units included (S15 restated: process parts are prefix-stable, network sheets are not), so each
candidate size is planned in full (a plan has no pyDEXPI, so that is cheap).
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline import SizeSearchResult


def smallest_n_units_total_sheets(
    target_sheets: int, generator_config: Callable[[int], object], seed: int
) -> SizeSearchResult:
    """The fewest units whose plan has at least `target_sheets` sheets, network sheets included.

    `generator_config(n_units)` gives the config of an `n_units` plant. The sheets per unit are
    nearly constant, so each plan rescales the guess (n * target / sheets) until it holds, then
    single steps find the exact edge; a plan of 1,000 sheets takes seconds, so few are made.

    Raises:
        ValueError: if `target_sheets` is below 1.
    """
    if target_sheets < 1:
        raise ValueError(f"expected target_sheets >= 1, found {target_sheets}")
    seen: dict[int, int] = {}

    def sheets_of(n_units: int) -> int:
        if n_units not in seen:
            seen[n_units] = plan_plant(generator_config(n_units)).sheet_count  # type: ignore[arg-type]
        return seen[n_units]

    n_units = _rescaled_guess(target_sheets, sheets_of)
    while n_units > 1 and sheets_of(n_units - 1) >= target_sheets:
        n_units -= 1
    while sheets_of(n_units) < target_sheets:
        n_units += 1
    return SizeSearchResult(
        target_sheets=target_sheets,
        n_units=n_units,
        predicted_sheets=sheets_of(n_units),
        predicted_sheets_one_unit_fewer=sheets_of(n_units - 1) if n_units > 1 else 0,
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
