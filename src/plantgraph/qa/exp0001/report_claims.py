"""The verdicts of claims X1-X6, with the design note's wording and decision rules (section 7).

Each claim reads the already-built tables (cells, paired differences, trend) and returns one
`ClaimVerdict`. Nothing here recomputes statistics; a rule is a comparison on a finished number.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from plantgraph.qa.exp0001.ladder_stats import (
    chars_per_sheet,
    first_below_zero,
    fits_in_window,
    wall_in_sheets,
)
from plantgraph.qa.exp0001.report_models import (
    CASCADE,
    CTX_HIGH,
    CTX_LOW,
    SCOPE_ALL,
    SCOPE_COMMON,
    ArmCell,
    ClaimVerdict,
    PairedDelta,
    SizePoint,
    Trend,
    Verdict,
)

#: Q4's non-inferiority margin: ContextRAG may be at most 5 points worse on one sheet (X2).
NON_INFERIORITY_MARGIN = -0.05

WORDING = {
    "X1": "The single-sheet advantage of ContextRAG shrinks with corpus size",
    "X2": "ChatP&ID's end holds: on one sheet ContextRAG is not worse than the cascade",
    "X3": "Accuracy flip point",
    "X4": "Cost and latency flip",
    "X5": "The context wall",
    "X6": "Effort sensitivity",
}


@dataclass(frozen=True)
class Edition:
    """What differs between the v1 and v2 report: the sizes X6 reads, and X3's stage C text."""

    #: Sizes where the effort sensitivity (X6) is measured; empty when X6 was not run at all.
    effort_sizes: tuple[str, ...] = ("H1", "H10")
    #: When set, X6 is reported as not run, with this text (v2: ADR-0060 point 4).
    x6_not_run: str | None = None
    #: Appended to X3's "no flip" text unless the largest size is H100 (stage C already ran).
    stage_c_note: str = "stage C becomes eligible"


V1_EDITION = Edition()
V2_EDITION = Edition(
    effort_sizes=(),
    x6_not_run="not run on v2 (ADR-0060), see EXP-0001",
    stage_c_note="stage C not applicable on v2 (ADR-0060)",
)

#: Measured ContextRAG prompt lengths of v1's two big corpora (`_results.md` PROMPT-04).
V1_BIG_PROMPTS = (("H100", 1_649_451), ("H1000", 16_747_117))


@dataclass(frozen=True)
class WallSettings:
    """What X5 needs besides the measured calls: the model's window and the big prompts."""

    #: Luna's `max_prompt_tokens` from the listing re-read on the run day (922,000 on 2026-10-10).
    max_prompt_tokens: int = 922_000
    #: (corpus id, prompt chars) of corpora too big to call; X5 says whether each fits the window.
    big_prompts: tuple[tuple[str, int], ...] = V1_BIG_PROMPTS


@dataclass(frozen=True)
class ClaimInputs:
    """The finished tables the claims read."""

    #: Every measured corpus, smallest first (the ladder, then H100 when stage C ran).
    sizes: Sequence[SizePoint]
    ladder_ids: Sequence[str]
    cells: Sequence[ArmCell]
    deltas: Sequence[PairedDelta]
    trend: Trend | None
    #: Per-call chars/token ratios of every ContextRAG-high call.
    ratios: Sequence[float]
    wall: WallSettings
    edition: Edition = V1_EDITION


def _verdict(claim: str, value: str, verdict: Verdict) -> ClaimVerdict:
    return ClaimVerdict(id=claim, wording=WORDING[claim], value=value, verdict=verdict)


def _not_run(claim: str, reason: str) -> ClaimVerdict:
    return _verdict(claim, f"not run: {reason}", "NOT_RUN")


def _pick_delta(
    deltas: Sequence[PairedDelta], corpus_id: str, scope: str, a: str, b: str, metric: str
) -> PairedDelta | None:
    for delta in deltas:
        same = (delta.corpus_id, delta.scope, delta.a, delta.b, delta.metric)
        if same == (corpus_id, scope, a, b, metric):
            return delta
    return None


def _interval_text(delta: PairedDelta, digits: int = 3) -> str:
    low, high = delta.ci.ci_low, delta.ci.ci_high
    return f"{delta.delta:+.{digits}f} [{low:+.{digits}f}, {high:+.{digits}f}]"


def claim_x1(trend: Trend | None) -> ClaimVerdict:
    """PASS if the upper bound of the slope's 95 % interval is below 0 (common families)."""
    if trend is None:
        return _not_run(
            "X1", "fewer than two ladder sizes have both ContextRAG-high and cascade_v3"
        )
    low, high = trend.ci.ci_low, trend.ci.ci_high
    value = (
        f"slope {trend.slope:+.3f} per log10(sheets), 95% CI [{low:+.3f}, {high:+.3f}] "
        f"over {', '.join(trend.sizes)} ({trend.scope} families)"
    )
    return _verdict("X1", value, "PASS" if high < 0 else "FAIL")


def claim_x2(deltas: Sequence[PairedDelta], smallest: str) -> ClaimVerdict:
    """PASS if the CI lower bound of the difference at the smallest size is >= -0.05 (common)."""
    primary = _pick_delta(deltas, smallest, SCOPE_COMMON, CTX_HIGH, CASCADE, "acc@120")
    if primary is None:
        return _not_run("X2", f"no ContextRAG-high vs cascade_v3 comparison at {smallest}")
    secondary = _pick_delta(deltas, smallest, SCOPE_ALL, CTX_HIGH, CASCADE, "acc@120")
    value = f"{smallest} common: delta {_interval_text(primary)}, n={primary.n}"
    if secondary is not None:
        value += f"; all families: delta {_interval_text(secondary)}, n={secondary.n}"
    passed = primary.ci.ci_low >= NON_INFERIORITY_MARGIN
    return _verdict(
        "X2", value + f"; margin {NON_INFERIORITY_MARGIN}", "PASS" if passed else "FAIL"
    )


def _nominal_sheets(corpus_id: str) -> int:
    """The sheet count in a corpus id such as `H30` or `H30g2` (the design's nominal size)."""
    match = re.fullmatch(r"H(\d+)(?:g2)?", corpus_id)
    if match is None:
        raise ValueError(f"expected a corpus id like 'H30' or 'H30g2', found {corpus_id!r}")
    return int(match.group(1))


def claim_x3(inputs: ClaimInputs) -> ClaimVerdict:
    """The smallest measured size whose accuracy difference has a CI upper bound below 0."""
    bounds = []
    for size in inputs.sizes:
        delta = _pick_delta(
            inputs.deltas, size.corpus_id, SCOPE_COMMON, CTX_HIGH, CASCADE, "acc@120"
        )
        if delta is not None:
            bounds.append((size.corpus_id, delta.ci.ci_high))
    if not bounds:
        return _not_run("X3", "no ContextRAG-high vs cascade_v3 comparison at any size")
    previous, flip = first_below_zero(bounds)
    if flip is None:
        text = f"no accuracy flip up to {_nominal_sheets(bounds[-1][0])} sheets"
        if bounds[-1][0] != "H100":
            text += f"; {inputs.edition.stage_c_note}"
        return _verdict("X3", text, "REPORTED")
    if previous is None:
        return _verdict("X3", f"s_acc = {flip}, the smallest measured size", "REPORTED")
    return _verdict("X3", f"s_acc = {flip}, between {previous} and {flip}", "REPORTED")


def claim_x4(inputs: ClaimInputs) -> ClaimVerdict:
    """Smallest size where ContextRAG-high costs more per question / has a higher median latency."""
    rows = []
    for size in inputs.sizes:
        ctx = _cell(inputs.cells, size.corpus_id, CTX_HIGH)
        cascade = _cell(inputs.cells, size.corpus_id, CASCADE)
        if ctx is not None and cascade is not None:
            rows.append((size.corpus_id, ctx, cascade))
    if not rows:
        return _not_run("X4", "no size has both ContextRAG-high and cascade_v3")
    s_cost = next((c for c, ctx, cas in rows if ctx.cost_mean > cas.cost_mean), None)
    s_lat = next((c for c, ctx, cas in rows if ctx.latency_median > cas.latency_median), None)
    cost_ratios = ", ".join(f"{c} {ctx.cost_mean / cas.cost_mean:.2f}" for c, ctx, cas in rows)
    lat_ratios = ", ".join(
        f"{c} {ctx.latency_median / cas.latency_median:.2f}" for c, ctx, cas in rows
    )
    value = (
        f"s_cost = {s_cost or 'none'}; s_lat = {s_lat or 'none'}; "
        f"$/q ratio ctx-high/cascade_v3: {cost_ratios}; median-latency ratio: {lat_ratios}"
    )
    return _verdict("X4", value, "REPORTED")


def _cell(
    cells: Sequence[ArmCell], corpus_id: str, arm: str, scope: str = SCOPE_ALL
) -> ArmCell | None:
    return next(
        (c for c in cells if (c.corpus_id, c.policy, c.scope) == (corpus_id, arm, scope)), None
    )


@dataclass(frozen=True)
class WallFigures:
    """X5's measured numbers: chars per token, chars per sheet, and the wall in sheets."""

    chars_per_token: float
    n_calls: int
    chars_per_sheet: float
    wall_sheets: float


def wall_figures(inputs: ClaimInputs) -> WallFigures | str:
    """Fit the wall from the ContextRAG-high calls; a string says why it cannot be fitted."""
    points = [(s.n_sheets, float(s.ctx_prompt_chars)) for s in inputs.sizes if s.ctx_prompt_chars]
    if not inputs.ratios or len(points) < 2:
        return "needs ContextRAG-high calls at two or more sizes"
    ratio = statistics.median(inputs.ratios)
    per_sheet = chars_per_sheet(points)
    if per_sheet <= 0:
        return f"the fitted chars per sheet is not positive (found {per_sheet:.1f})"
    wall = wall_in_sheets(inputs.wall.max_prompt_tokens, ratio, per_sheet)
    return WallFigures(ratio, len(inputs.ratios), per_sheet, wall)


def claim_x5(inputs: ClaimInputs) -> ClaimVerdict:
    """Chars per token, chars per sheet, the wall in sheets, and whether the big corpora fit."""
    figures = wall_figures(inputs)
    if isinstance(figures, str):
        return _not_run("X5", figures)
    limit = inputs.wall.max_prompt_tokens
    parts = [
        f"r = {figures.chars_per_token:.2f} chars/token over {figures.n_calls} calls",
        f"c = {figures.chars_per_sheet:,.0f} chars/sheet",
        f"W = {figures.wall_sheets:,.0f} sheets (window {limit:,} prompt tokens)",
    ]
    for name, chars in inputs.wall.big_prompts:
        fits = fits_in_window(chars, figures.chars_per_token, limit)
        tokens = chars / figures.chars_per_token
        verdict = "fits" if fits else "does not fit"
        parts.append(f"{name} ({chars:,} chars = {tokens:,.0f} tokens): {verdict}")
    return _verdict("X5", "; ".join(parts), "REPORTED")


def claim_x6(deltas: Sequence[PairedDelta], edition: Edition = V1_EDITION) -> ClaimVerdict:
    """Accuracy and cost difference of ContextRAG-low against -high, where both ran."""
    if edition.x6_not_run is not None:
        return _verdict("X6", edition.x6_not_run, "NOT_RUN")
    parts = []
    for corpus_id in edition.effort_sizes:
        accuracy = _pick_delta(deltas, corpus_id, SCOPE_ALL, CTX_LOW, CTX_HIGH, "acc@120")
        cost = _pick_delta(deltas, corpus_id, SCOPE_ALL, CTX_LOW, CTX_HIGH, "cost_usd")
        if accuracy is not None and cost is not None:
            parts.append(
                f"{corpus_id}: delta acc {_interval_text(accuracy)}, "
                f"delta $/q {_interval_text(cost, digits=5)} (low minus high, n={accuracy.n})"
            )
    if not parts:
        return _not_run("X6", "no size has both ContextRAG-low and ContextRAG-high")
    return _verdict("X6", "; ".join(parts), "REPORTED")


def all_claims(inputs: ClaimInputs) -> list[ClaimVerdict]:
    """X1-X6 in order."""
    smallest = inputs.ladder_ids[0]
    return [
        claim_x1(inputs.trend),
        claim_x2(inputs.deltas, smallest),
        claim_x3(inputs),
        claim_x4(inputs),
        claim_x5(inputs),
        claim_x6(inputs.deltas, inputs.edition),
    ]
