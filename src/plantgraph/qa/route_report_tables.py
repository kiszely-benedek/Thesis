"""Aggregate per-question routing measurements into report rows, a CSV and a markdown file.

Pure: lists in, text out, no corpus and no model. `route_report.py` produces the
`QuestionMeasure` rows; this module only groups and renders them (design §3.8).

Rows are grouped along four *dimensions*: `all`, the k-bin (how many sheet
boundaries the evidence crosses), `u` (how many units it crosses) and the question
family. Every group is reported for each of the four route x budget combinations.
Every rate is over the rows that report the value; the `n_*` columns say how many
that was, so a rate over three questions cannot pass for one over three hundred.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Iterable

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.context_budget import BUDGET_MODES
from plantgraph.qa.questions.availability import KBin
from plantgraph.qa.sheet_selection import ROUTE_MODES

#: Dimension names in the order they are printed.
DIMENSIONS = ("all", "k_bin", "u", "family")


class QuestionMeasure(BaseModel):
    """What one retrieval (one question, one combination, one budget) measured."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    max_context_chars: int
    route_mode: str
    budget_mode: str
    question_id: str
    family: str
    k_bin: str
    #: Units crossed; `None` for an unanswerable question.
    u: int | None
    #: The three gold-side metrics; `None` when the question has no evidence or retrieval failed.
    strict_hit: bool | None
    relaxed_hit: bool | None
    node_recall: float | None
    #: True when retrieval returned no context (e.g. no anchor and no router).
    retrieval_failed: bool
    context_chars: int | None
    over_budget: bool | None
    #: True when the flow search found no path and the sheet graph was used instead.
    route_fallback: bool | None
    retrieval_ms: float


class ReportRow(BaseModel):
    """One line of the report: a group of questions under one combination and budget."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    max_context_chars: int
    route_mode: str
    budget_mode: str
    dimension: str
    group: str
    n_questions: int
    #: Questions with gold evidence: the denominator of the three hit/recall columns.
    n_with_evidence: int
    strict_hit: float | None
    relaxed_hit: float | None
    node_recall: float | None
    context_chars_median: float | None
    context_chars_p90: float | None
    over_budget_rate: float | None
    route_fallback_rate: float | None
    retrieval_failure_rate: float
    retrieval_ms_median: float


_GroupOf = Callable[[QuestionMeasure], str | None]

#: Dimension -> the group a measure falls in (`None`: left out of that dimension).
_GROUP_OF: dict[str, _GroupOf] = {
    "all": lambda measure: "all",
    "k_bin": lambda measure: measure.k_bin,
    "u": lambda measure: None if measure.u is None else str(measure.u),
    "family": lambda measure: measure.family,
}

_K_BIN_ORDER = [bin_.value for bin_ in KBin]
_COMBINATIONS: list[tuple[str, str]] = [
    (route, budget) for route in ROUTE_MODES for budget in BUDGET_MODES
]


def build_report_rows(measures: Iterable[QuestionMeasure]) -> list[ReportRow]:
    """Group `measures` along every dimension; the result's order is fixed (deterministic)."""
    buckets: dict[tuple[str, int, str, str, str, str], list[QuestionMeasure]] = defaultdict(list)
    for measure in measures:
        for dimension in DIMENSIONS:
            group = _GROUP_OF[dimension](measure)
            if group is not None:
                key = (
                    measure.corpus_id,
                    measure.max_context_chars,
                    measure.route_mode,
                    measure.budget_mode,
                    dimension,
                    group,
                )
                buckets[key].append(measure)
    rows = [_row_of(key, group_measures) for key, group_measures in buckets.items()]
    return sorted(rows, key=_row_order)


def _row_order(row: ReportRow) -> tuple[str, int, int, tuple[int, str], int]:
    return (
        row.corpus_id,
        row.max_context_chars,
        DIMENSIONS.index(row.dimension),
        _group_order(row.dimension, row.group),
        _COMBINATIONS.index((row.route_mode, row.budget_mode)),
    )


def _group_order(dimension: str, group: str) -> tuple[int, str]:
    """k-bins in their natural order, `u` numerically, families alphabetically."""
    if dimension == "k_bin":
        return (_K_BIN_ORDER.index(group), group)
    if dimension == "u":
        return (int(group), group)
    return (0, group)


def _row_of(key: tuple[str, int, str, str, str, str], measures: list[QuestionMeasure]) -> ReportRow:
    corpus_id, max_chars, route_mode, budget_mode, dimension, group = key
    strict = [m.strict_hit for m in measures if m.strict_hit is not None]
    chars = sorted(m.context_chars for m in measures if m.context_chars is not None)
    return ReportRow(
        corpus_id=corpus_id,
        max_context_chars=max_chars,
        route_mode=route_mode,
        budget_mode=budget_mode,
        dimension=dimension,
        group=group,
        n_questions=len(measures),
        n_with_evidence=len(strict),
        strict_hit=_mean(strict),
        relaxed_hit=_mean([m.relaxed_hit for m in measures if m.relaxed_hit is not None]),
        node_recall=_mean([m.node_recall for m in measures if m.node_recall is not None]),
        context_chars_median=statistics.median(chars) if chars else None,
        context_chars_p90=_percentile(chars, 0.9),
        over_budget_rate=_mean([m.over_budget for m in measures if m.over_budget is not None]),
        route_fallback_rate=_mean(
            [m.route_fallback for m in measures if m.route_fallback is not None]
        ),
        retrieval_failure_rate=sum(m.retrieval_failed for m in measures) / len(measures),
        retrieval_ms_median=statistics.median(m.retrieval_ms for m in measures),
    )


def _mean(values: list[bool] | list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _percentile(sorted_values: list[int], fraction: float) -> float | None:
    """Nearest-rank percentile: always one of the observed values."""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return float(sorted_values[rank - 1])


def render_csv(rows: list[ReportRow]) -> str:
    """One CSV line per row; a missing value is an empty cell."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    columns = list(ReportRow.model_fields)
    writer.writerow(columns)
    for row in rows:
        values = row.model_dump()
        writer.writerow(["" if values[name] is None else values[name] for name in columns])
    return buffer.getvalue()


_MARKDOWN_COLUMNS = (
    ("route", lambda r: r.route_mode),
    ("budget", lambda r: r.budget_mode),
    ("group", lambda r: r.group),
    ("n", lambda r: str(r.n_questions)),
    ("n evid.", lambda r: str(r.n_with_evidence)),
    ("strict", lambda r: _fmt(r.strict_hit)),
    ("relaxed", lambda r: _fmt(r.relaxed_hit)),
    ("node recall", lambda r: _fmt(r.node_recall)),
    ("chars med", lambda r: _fmt(r.context_chars_median, digits=0)),
    ("chars p90", lambda r: _fmt(r.context_chars_p90, digits=0)),
    ("over budget", lambda r: _fmt(r.over_budget_rate)),
    ("route fallback", lambda r: _fmt(r.route_fallback_rate)),
    ("retr. failed", lambda r: _fmt(r.retrieval_failure_rate)),
    ("ms med", lambda r: _fmt(r.retrieval_ms_median, digits=1)),
)


def _fmt(value: float | None, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def render_markdown(rows: list[ReportRow]) -> str:
    """One table per corpus, budget and dimension, in the rows' own order."""
    sections: dict[tuple[str, int, str], list[ReportRow]] = {}
    for row in rows:
        sections.setdefault((row.corpus_id, row.max_context_chars, row.dimension), []).append(row)
    lines = ["# Routing 2x2 (free: retrieval only, no model call)", ""]
    for (corpus_id, max_chars, dimension), section in sections.items():
        lines.append(f"## {corpus_id}, max_context_chars={max_chars}, by {dimension}")
        lines.append("")
        lines.extend(_markdown_table(section))
        lines.append("")
    return "\n".join(lines)


def _markdown_table(rows: list[ReportRow]) -> list[str]:
    header = "| " + " | ".join(name for name, _ in _MARKDOWN_COLUMNS) + " |"
    divider = "|" + "---|" * len(_MARKDOWN_COLUMNS)
    body = ["| " + " | ".join(cell(row) for _, cell in _MARKDOWN_COLUMNS) + " |" for row in rows]
    return [header, divider, *body]
