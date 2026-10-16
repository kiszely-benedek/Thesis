"""The Results tab's data: two recorded experiment reports, projected into what the page draws.

Nothing here is computed or typed in. Every number is read from a report file written by an
earlier experiment run (`report.json`); the page also gets the file's path, hash and date, so a
visitor can see which recorded run a figure comes from.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from plantgraph.demo.app.config import ResultsSources

# --- what the API returns ---------------------------------------------------------------------


class Interval(BaseModel):
    """A proportion with its Wilson 95 % confidence interval (a range that stays inside 0..1)."""

    estimate: float
    ci_low: float
    ci_high: float


class Provenance(BaseModel):
    """Which file a view was read from, so the figure's caption can cite it."""

    path: str
    sha256: str
    modified: datetime
    #: The row(s) of the experiment results table that record this run.
    result_row: str


class LadderPoint(BaseModel):
    """One arm (a retrieval strategy) on one corpus size of the scale ladder."""

    corpus_id: str
    n_sheets: int
    arm: str
    n: int
    accuracy: Interval
    cost_mean_usd: float
    latency_median_s: float


class LadderView(BaseModel):
    """EXP-0001: accuracy, cost and latency of each arm as the corpus grows."""

    scope: Literal["common"]
    n_families: int
    cutoff_s: float
    #: The sheet count at which the whole drawing set stops fitting in one prompt.
    wall_sheets: float
    points: tuple[LadderPoint, ...]
    #: Arm/size cells the experiment has no run for (shown, never silently dropped).
    absent: tuple[str, ...]
    source: Provenance


class SealedRow(BaseModel):
    """One policy on one sealed-test corpus."""

    corpus_id: str
    n_sheets: int
    policy: str
    n_questions: int
    n_correct: int
    accuracy: Interval
    cost_per_question_usd: float
    latency_median_s: float
    latency_p90_s: float


class SealedView(BaseModel):
    """EXP-0002: the held-out test, frozen cascade against the two single-tier policies."""

    scope: Literal["headline"]
    rows: tuple[SealedRow, ...]
    source: Provenance


class ResultsView(BaseModel):
    """Both result views; a view is `None` when its report is not configured."""

    ladder: LadderView | None
    sealed: SealedView | None


# --- the fields we read from the report files (everything else is ignored) ---------------------


class _Parsed(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Cell(_Parsed):
    corpus_id: str
    policy: str
    scope: str
    n: int
    acc_at_120: Interval
    cost_mean: float
    latency_median: float


class _Size(_Parsed):
    corpus_id: str
    n_sheets: int


class _Families(_Parsed):
    common: list[str]


class _LadderReport(_Parsed):
    cutoff_s: float
    wall_sheets: float
    absent: list[str]
    sizes: list[_Size]
    scope_families: _Families
    cells: list[_Cell]


class _Summary(_Parsed):
    n_questions: int
    n_correct_at_cutoff: int
    cost_per_question_usd: float
    latency_median_s: float
    latency_p90_s: float


class _ScopeRow(_Parsed):
    corpus_id: str
    scope: str
    policy: str
    summary: _Summary
    accuracy: Interval


class _Sealed(_Parsed):
    sheets: dict[str, int]
    scope_rows: list[_ScopeRow]


class _SealedReport(_Parsed):
    sealed: _Sealed


#: The policies the sealed table shows; `cascade_v3_iso` is an ablation and stays out.
SEALED_POLICIES = ("cascade_v3", "always_g_luna", "always_c_luna")


# --- reading ----------------------------------------------------------------------------------


def _provenance(path: Path, result_row: str) -> Provenance:
    data = path.read_bytes()
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return Provenance(
        path=path.as_posix(),
        sha256=hashlib.sha256(data).hexdigest(),
        modified=modified,
        result_row=result_row,
    )


def _read_report[T: BaseModel](path: Path, model: type[T]) -> T:
    """Parse a report file, naming the file and the broken field when it does not fit."""
    if not path.exists():
        raise FileNotFoundError(f"expected the results report at {path}, found no such file")
    try:
        return model.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise ValueError(f"expected field {where!r} in {path}, found: {first['msg']}") from error


def ladder_view(path: Path, result_row: str) -> LadderView:
    """Project the EXP-0001 report: the `common` question families only (the claim's scope)."""
    report = _read_report(path, _LadderReport)
    sheets = {size.corpus_id: size.n_sheets for size in report.sizes}
    points = tuple(
        LadderPoint(
            corpus_id=cell.corpus_id,
            n_sheets=sheets[cell.corpus_id],
            arm=cell.policy,
            n=cell.n,
            accuracy=cell.acc_at_120,
            cost_mean_usd=cell.cost_mean,
            latency_median_s=cell.latency_median,
        )
        for cell in report.cells
        if cell.scope == "common"
    )
    return LadderView(
        scope="common",
        n_families=len(report.scope_families.common),
        cutoff_s=report.cutoff_s,
        wall_sheets=report.wall_sheets,
        points=points,
        absent=tuple(report.absent),
        source=_provenance(path, result_row),
    )


def _sealed_row(row: _ScopeRow, sheets: dict[str, int]) -> SealedRow:
    summary = row.summary
    return SealedRow(
        corpus_id=row.corpus_id,
        n_sheets=sheets[row.corpus_id],
        policy=row.policy,
        n_questions=summary.n_questions,
        n_correct=summary.n_correct_at_cutoff,
        accuracy=row.accuracy,
        cost_per_question_usd=summary.cost_per_question_usd,
        latency_median_s=summary.latency_median_s,
        latency_p90_s=summary.latency_p90_s,
    )


def sealed_view(path: Path, result_row: str) -> SealedView:
    """Project the EXP-0002 report: the `headline` questions, three policies, both corpora."""
    sealed = _read_report(path, _SealedReport).sealed
    rows = tuple(
        _sealed_row(row, sealed.sheets)
        for row in sealed.scope_rows
        if row.scope == "headline" and row.policy in SEALED_POLICIES
    )
    return SealedView(scope="headline", rows=rows, source=_provenance(path, result_row))


def results_view(sources: ResultsSources) -> ResultsView:
    """Both views from the configured report files.

    Raises:
        FileNotFoundError: a configured report does not exist.
        ValueError: a report lacks a field the projection reads.
    """
    return ResultsView(
        ladder=ladder_view(sources.ladder_report, sources.ladder_result_row),
        sealed=sealed_view(sources.sealed_report, sources.sealed_result_row),
    )
