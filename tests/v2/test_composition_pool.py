"""Review R2: the composition bands judged on the mean over the plants of a scale."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.benchmark.v2.composition import (
    CompositionReport,
    CompositionRow,
    main,
    make_row,
)
from plantgraph.benchmark.v2.composition_bands import CORPUS_BANDS, PLAN_BANDS, Verdict
from plantgraph.benchmark.v2.composition_pool import PooledReport, pool_reports, render_pooled

_SYMBOLS = "symbols per sheet, mean"  # band 56-109
_SHARE = "sheets with 40-134 symbols (share)"  # a reported band: never fails


def _report(
    corpus_id: str, symbols: float, extra: tuple[CompositionRow, ...] = ()
) -> CompositionReport:
    rows = (make_row(_SYMBOLS, symbols, PLAN_BANDS), make_row(_SHARE, 0.5, PLAN_BANDS), *extra)
    return CompositionReport(corpus_id=corpus_id, seed=1, n_units=10, n_sheets=10, plan_rows=rows)


def test_a_plant_outside_a_band_passes_when_the_mean_of_the_plants_is_inside() -> None:
    low, high = _report("A", 50.0), _report("B", 70.0)  # 50 is below 56-109, the mean 60 is not
    assert [r.verdict for r in low.plan_rows][0] is Verdict.FAIL
    pooled = pool_reports([low, high])
    row = next(r for r in pooled.rows if r.quantity == _SYMBOLS)
    assert (row.value, row.verdict) == (60.0, Verdict.PASS)
    assert pooled.failures == ()


def test_the_pooled_mean_can_fail_while_one_plant_passes() -> None:
    pooled = pool_reports([_report("A", 57.0), _report("B", 40.0)])  # mean 48.5 < 56
    assert [r.quantity for r in pooled.failures] == [_SYMBOLS]
    assert pooled.plants[0].failures == ()  # plant A alone would have passed


def test_a_reported_band_stays_reported_when_pooled() -> None:
    pooled = pool_reports([_report("A", 60.0), _report("B", 60.0)])
    assert next(r for r in pooled.rows if r.quantity == _SHARE).verdict is Verdict.REPORTED


def test_the_per_plant_values_ride_along_unjudged_in_the_table() -> None:
    text = render_pooled(pool_reports([_report("A", 50.0), _report("B", 70.0)]))
    assert "pooled over 2 plants (A, B)" in text
    line = next(line for line in text.splitlines() if _SYMBOLS in line)
    assert "60.000" in line and "50.000" in line and "70.000" in line and "pass" in line


def test_pooling_nothing_or_plants_with_different_quantities_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one plant"):
        pool_reports([])
    plain = _report("A", 60.0)
    corpus_row = make_row("sheets that show one unit (share)", 1.0, CORPUS_BANDS)
    with pytest.raises(ValueError, match="same quantities"):
        pool_reports(
            [plain, plain.model_copy(update={"plan_rows": (*plain.plan_rows, corpus_row)})]
        )


def test_the_command_pools_the_seeds_and_writes_one_json_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "pooled.json"
    code = main(["--target-sheets", "10", "--seeds", "1", "2", "--pool", "--json", str(target)])
    out = capsys.readouterr().out
    assert "pooled over 2 plants (D10g21, X10g21s2)" in out
    assert out.count("per pattern") == 0  # the per-plant tables are not printed when pooling
    pooled = PooledReport.model_validate(json.loads(target.read_text("utf-8")))
    assert [p.seed for p in pooled.plants] == [1, 2]
    assert code == (1 if pooled.failures else 0)  # the exit code follows the pooled verdicts
