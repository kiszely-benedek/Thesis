"""Judge the composition bands on the pooled plants of one scale, not plant by plant (review R2).

A scale (100 or 1000 sheets) has several sealed plants. One plant may sit a little outside a band
by chance, so the bands are judged on the **mean over the plants** of the scale. The per-plant
values stay in the report for reading; they are not judged. The per-plant mode of
`composition.py` remains for tuning one plant.

A quantity's pooled value is the plain mean of its per-plant values, whatever its kind: a mean, a
share, a minimum or a maximum. The exact reconciliation bands (`= 1`) therefore hold only when
every plant reaches 1.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.composition import CompositionReport, CompositionRow, make_row
from plantgraph.benchmark.v2.composition_bands import CORPUS_BANDS, PLAN_BANDS, Band, Verdict

_ALL_BANDS: dict[str, Band] = {**PLAN_BANDS, **CORPUS_BANDS}


class PooledReport(BaseModel):
    """The bands judged on the mean over `plants`; the per-plant reports ride along unjudged."""

    model_config = ConfigDict(frozen=True)

    plants: tuple[CompositionReport, ...]
    rows: tuple[CompositionRow, ...]

    @property
    def failures(self) -> tuple[CompositionRow, ...]:
        """The pooled rows whose verdict is `fail`."""
        return tuple(row for row in self.rows if row.verdict is Verdict.FAIL)


def pool_reports(reports: Sequence[CompositionReport]) -> PooledReport:
    """The pooled report of `reports`: each row is the mean over the plants, judged on its band.

    Raises:
        ValueError: if there is no plant, or the plants report different quantities (for example
            one has the corpus rows and another does not).
    """
    if not reports:
        raise ValueError("expected at least one plant to pool, got none")
    names = _quantities(reports[0])
    mismatched = [r.corpus_id for r in reports if _quantities(r) != names]
    if mismatched:
        raise ValueError(
            f"expected every pooled plant to report the same quantities as {reports[0].corpus_id}, "
            f"found different ones in {mismatched}"
        )
    rows = tuple(make_row(name, _mean_of(reports, name), _ALL_BANDS) for name in names)
    return PooledReport(plants=tuple(reports), rows=rows)


def _quantities(report: CompositionReport) -> list[str]:
    return [row.quantity for row in (*report.plan_rows, *report.corpus_rows)]


def _mean_of(reports: Sequence[CompositionReport], quantity: str) -> float:
    values = [
        row.value
        for report in reports
        for row in (*report.plan_rows, *report.corpus_rows)
        if row.quantity == quantity
    ]
    return sum(values) / len(values)


def render_pooled(pooled: PooledReport) -> str:
    """The pooled rows (mean over the plants, judged) with each plant's value beside them."""
    ids = [report.corpus_id for report in pooled.plants]
    head = f"pooled over {len(ids)} plants ({', '.join(ids)}): bands judged on the mean"
    columns = "".join(f"{report.corpus_id:>14}" for report in pooled.plants)
    lines = [head, f"  {'quantity':<64}{'mean':>9}  {'band':<42}{'verdict':<9}{columns}"]
    for row in pooled.rows:
        each = "".join(f"{_value_of(report, row.quantity):>14.3f}" for report in pooled.plants)
        lines.append(
            f"  {row.quantity:<64}{row.value:>9.3f}  {row.band:<42}{row.verdict.value:<9}{each}"
        )
    return "\n".join(lines)


def _value_of(report: CompositionReport, quantity: str) -> float:
    for row in (*report.plan_rows, *report.corpus_rows):
        if row.quantity == quantity:
            return row.value
    raise ValueError(f"expected {report.corpus_id} to report {quantity!r}, found it does not")
