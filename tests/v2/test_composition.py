"""The composition report: hand counts on a fixture, the bands, the corpus checks and the CLI.

The report's numbers are the counting rule's output (`sheet_stats`); the fixture plan in
`composition_fixture.py` has every count worked out by hand in its docstring.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from composition_fixture import (
    HAND_COUNTS,
    HAND_EQUIPMENT,
    HAND_EQUIPMENT_IN_SPARE_SETS,
    HAND_SYMBOLS,
    hand_plan,
)
from corpus_v2 import SEED, corpus

from plantgraph.benchmark.generator_dispatch import generate_plant_graph_any
from plantgraph.benchmark.v2.composition import (
    CompositionReport,
    build_report,
    main,
    make_row,
    pattern_rows,
    plan_values,
    require_no_test_seeds,
)
from plantgraph.benchmark.v2.composition_bands import CORPUS_BANDS, PLAN_BANDS, Band, Verdict
from plantgraph.benchmark.v2.composition_corpus import split_sheets, symbol_count
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.sheet_stats import sheet_stats
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

# ---- the hand-counted fixture --------------------------------------------------------------------


def test_every_sheet_of_the_fixture_has_its_hand_counted_composition() -> None:
    stats = sheet_stats(hand_plan())
    assert [s.sheet_group for s in stats] == list(HAND_COUNTS)
    for sheet in stats:
        counted = (
            sheet.equipment,
            sheet.valves,
            sheet.fittings,
            sheet.instruments,
            sheet.stubs,
            sheet.crossings,
            sheet.signal_cuts,
        )
        assert counted == HAND_COUNTS[sheet.sheet_group], sheet.sheet_group
        assert sheet.symbols == HAND_SYMBOLS[sheet.sheet_group], sheet.sheet_group


def test_the_report_values_equal_the_hand_computed_statistics() -> None:
    plan = hand_plan()
    values = dict(plan_values(plan, sheet_stats(plan)))
    assert values == pytest.approx(
        {
            "symbols per sheet, mean": (9 + 11 + 7) / 3,
            "sheets with 40-134 symbols (share)": 0.0,
            "valves per sheet, mean": (3 + 2 + 2) / 3,
            "instruments per sheet, mean": (1 + 3 + 2) / 3,
            "instruments : valves": 6 / 7,
            "off-page stubs per sheet, mean": (2 + 3 + 1) / 3,
            "off-page stubs per sheet, max": 3,
            "equipment per sheet, min": 1,
            "equipment per sheet, max": 3,
            "sheets with at most 10 equipment (share)": 1.0,
            "equipment in A/B(/C) sets (share)": HAND_EQUIPMENT_IN_SPARE_SETS / HAND_EQUIPMENT,
            "units drawn on 2 or more sheets (share)": 1 / 2,
            "signal cuts per sheet, mean": 2 / 3,
        }
    )
    assert set(values) == set(PLAN_BANDS)  # every band has a row and every row a band


def test_the_report_judges_the_fixture_against_the_bands() -> None:
    report = build_report(hand_plan(), "fixture")
    verdicts = {row.quantity: row.verdict for row in report.plan_rows}
    assert verdicts["symbols per sheet, mean"] is Verdict.FAIL  # 9 symbols, band 56-109
    assert verdicts["equipment in A/B(/C) sets (share)"] is Verdict.PASS  # 1/3 in 0.25-0.45
    assert verdicts["sheets with 40-134 symbols (share)"] is Verdict.REPORTED
    assert "symbols per sheet, mean" in {row.quantity for row in report.failures}
    assert (report.n_units, report.n_sheets) == (2, 3)


def test_the_per_pattern_rows_name_the_sheets_that_miss() -> None:
    plan = hand_plan()
    rows = {row.label: row for row in pattern_rows(plan, sheet_stats(plan))}
    assert set(rows) == {"U4 sheet 1/2", "U4 sheet 2/2", "U6 sheet 1/1"}
    first = rows["U4 sheet 1/2"]
    assert (first.symbols_mean, first.stubs_high, first.under_40_symbols) == (9, 2, 1)
    assert first.misses and not first.over_21_stubs


# ---- bands ---------------------------------------------------------------------------------------


def test_a_band_is_inclusive_open_ended_or_reported() -> None:
    band = Band(label="1-2", low=1, high=2)
    assert [band.verdict(v) for v in (0.9, 1, 2, 2.1)] == [
        Verdict.FAIL,
        Verdict.PASS,
        Verdict.PASS,
        Verdict.FAIL,
    ]
    assert Band(label="<= 5", high=5).verdict(-3) is Verdict.PASS
    assert Band(label="r", reported=True).verdict(1e9) is Verdict.REPORTED


def test_make_row_carries_the_band_label_and_the_verdict() -> None:
    row = make_row("off-page stubs per sheet, max", 22, PLAN_BANDS)
    assert (row.band, row.verdict) == ("<= 21", Verdict.FAIL)


# ---- the corpus checks ---------------------------------------------------------------------------


def _small_plan() -> tuple[HeadlinePresetV2, PlantPlanV2]:
    preset = HeadlinePresetV2()
    n_units = smallest_n_units_v2(30, preset, SEED).n_units
    return preset, plan_plant(preset.generator_config(n_units, SEED))


def test_at_duplication_0_every_sheet_graph_equals_the_plan_exactly() -> None:
    """The one counting rule: corpus symbols, pipe connectors and signal connectors, per sheet."""
    preset, plan = _small_plan()
    report = build_report(plan, "corpus30", preset)
    rows = {row.quantity: row for row in report.corpus_rows}
    exact = [row for name, row in rows.items() if name.startswith("dup 0")]
    assert len(exact) == 3
    assert all(row.value == 1.0 and row.verdict is Verdict.PASS for row in exact)
    assert set(rows) == set(CORPUS_BANDS)
    assert rows["sheets that show one unit (share)"].value == 1.0


def test_the_preset_duplication_adds_reference_copies_to_the_sheet_graphs() -> None:
    preset, plan = _small_plan()
    plant = generate_plant_graph_any(plan.config)
    exact = split_sheets(plant, preset, SEED, 0.0)
    at_preset = split_sheets(plant, preset, SEED, preset.duplication_rate)
    assert [symbol_count(g) for g in exact] == [s.symbols - s.stubs for s in sheet_stats(plan)]
    copies = [symbol_count(g) - symbol_count(e) for g, e in zip(at_preset, exact, strict=True)]
    assert all(extra >= 0 for extra in copies) and sum(copies) > 0


def test_split_sheets_rebuilds_the_sheets_the_ingest_pipeline_cuts() -> None:
    """Same plant, same preset: node for node, the report reads the corpus the system gets."""
    preset, plan = _small_plan()
    plant = generate_plant_graph_any(plan.config)
    mine = split_sheets(plant, preset, SEED, preset.duplication_rate)
    theirs = sorted(corpus(30).sheets, key=lambda sheet: int(sheet.sheet_id))
    assert [set(g.graph.nodes) for g in mine] == [set(g.graph.nodes) for g in theirs]


# ---- the command line ----------------------------------------------------------------------------


def test_test_seeds_are_refused_unless_the_flag_is_given() -> None:
    require_no_test_seeds([1, 999], allow_test_seed=False)
    require_no_test_seeds([5001], allow_test_seed=True)
    with pytest.raises(ValueError, match=r"test seeds \[5000, 5999\]"):
        require_no_test_seeds([1, 5000, 5999], allow_test_seed=False)


def test_the_command_refuses_a_test_seed_before_planning_anything(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="test seeds"):
        main(["--target-sheets", "3", "--seeds", "5002"])
    assert capsys.readouterr().out == ""


def test_the_command_prints_the_table_and_writes_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "report.json"
    code = main(["--target-sheets", "10", "--seeds", "1", "2", "--coverage", "--json", str(target)])
    out = capsys.readouterr().out
    assert "D10g2" in out and "X10g2s2" in out  # the dev id and a tuning id
    assert "symbols per sheet, mean" in out and "class coverage:" in out
    reports = [CompositionReport.model_validate(r) for r in json.loads(target.read_text("utf-8"))]
    assert [r.seed for r in reports] == [1, 2]
    assert code == (1 if any(r.failures for r in reports) else 0)  # the exit code mirrors the fails


def test_a_test_seed_runs_with_the_flag(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--target-sheets", "3", "--seeds", "5001", "--allow-test-seed"])
    assert "H3g2" in capsys.readouterr().out
