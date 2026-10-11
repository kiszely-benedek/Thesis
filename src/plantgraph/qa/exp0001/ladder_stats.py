"""Pure statistics of the EXP-0001 ladder: the slope over size, flip points, the context wall.

No file or model knowledge here, only numbers, so every function is tested on hand-made fixtures.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from plantgraph.qa.cascade.stats import Interval, percentile


@dataclass(frozen=True)
class SizeSample:
    """One ladder size: its x position and the per-question differences measured there."""

    x: float
    differences: list[float]


def log10_sheets(n_sheets: int) -> float:
    """The size axis: log10 of the realized sheet count."""
    if n_sheets < 1:
        raise ValueError(f"expected at least one sheet, found {n_sheets}")
    return math.log10(n_sheets)


def ols_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Slope of the ordinary least-squares line through (x, y).

    Raises:
        ValueError: fewer than two points, unequal lengths, or all x equal.
    """
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError(
            f"expected two equal-length lists of >= 2 points, found {len(xs)}, {len(ys)}"
        )
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    spread = sum((x - mean_x) ** 2 for x in xs)
    if spread == 0:
        raise ValueError(f"expected at least two different x values, found all equal to {xs[0]}")
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / spread


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean of a non-empty list."""
    if not values:
        raise ValueError("expected at least one value for a mean, found none")
    return sum(values) / len(values)


def slope_interval(samples: Sequence[SizeSample], n_boot: int, seed: int) -> Interval:
    """OLS slope of the mean difference over x, with a bootstrap that resamples questions per size.

    Each resample redraws the questions of every size on its own, recomputes each size's mean
    difference, and refits the line; the 2.5 and 97.5 percentiles of those slopes are the interval.
    """
    xs = [s.x for s in samples]
    observed = ols_slope(xs, [mean(s.differences) for s in samples])
    rng = random.Random(seed)
    slopes = sorted(_resampled_slope(samples, xs, rng) for _ in range(n_boot))
    return Interval(
        estimate=observed, ci_low=percentile(slopes, 2.5), ci_high=percentile(slopes, 97.5)
    )


def _resampled_slope(samples: Sequence[SizeSample], xs: list[float], rng: random.Random) -> float:
    means = [mean(rng.choices(s.differences, k=len(s.differences))) for s in samples]
    return ols_slope(xs, means)


def first_below_zero(upper_bounds: Sequence[tuple[str, float]]) -> tuple[str | None, str | None]:
    """The flip point in a list of (size, CI upper bound) sorted by size.

    Returns (previous size, first size whose upper bound is below 0); the first is `None` when the
    flip is at the smallest size, the second `None` when there is no flip.
    """
    previous: str | None = None
    for size, upper in upper_bounds:
        if upper < 0:
            return previous, size
        previous = size
    return previous, None


def chars_per_sheet(points: Sequence[tuple[int, float]]) -> float:
    """Least-squares slope of prompt characters on sheets; the template is the intercept."""
    return ols_slope([float(sheets) for sheets, _ in points], [chars for _, chars in points])


def wall_in_sheets(max_prompt_tokens: int, chars_per_token: float, per_sheet_chars: float) -> float:
    """Sheets that fit in the window: tokens x chars-per-token / chars-per-sheet."""
    if chars_per_token <= 0 or per_sheet_chars <= 0:
        raise ValueError(
            f"expected positive chars/token and chars/sheet, "
            f"found {chars_per_token}, {per_sheet_chars}"
        )
    return max_prompt_tokens * chars_per_token / per_sheet_chars


def fits_in_window(prompt_chars: int, chars_per_token: float, max_prompt_tokens: int) -> bool:
    """Whether a prompt of this many characters stays under the model's prompt-token limit."""
    return prompt_chars / chars_per_token < max_prompt_tokens
