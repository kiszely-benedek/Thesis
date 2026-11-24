"""T12b: connectors by target kind, the per-kind report, the ch.20 table and the g22 corpus id."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from composition_fixture import hand_plan

from plantgraph.benchmark.v2 import toghraei_ch20 as ch20
from plantgraph.benchmark.v2.ch20_comparison import compare, render_markdown
from plantgraph.benchmark.v2.ch20_comparison import main as comparison_main
from plantgraph.benchmark.v2.composition import main
from plantgraph.benchmark.v2.connector_kinds import (
    SERVICE_CODE,
    ConnectorCode,
    SheetKind,
    code_of_service,
)
from plantgraph.benchmark.v2.kind_report import (
    KindReport,
    build_kind_report,
    render_kind_report,
    sheet_rows_of_plan,
)
from plantgraph.benchmark.v2.network_models import FLUID_CLASS_OF_SERVICE
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.ingest.headline_v2 import smallest_n_units_v2
from plantgraph.ingest.headline_v22 import HeadlinePresetV22


def _v22_plan(seed: int = 2, sheets: int = 30) -> PlantPlanV2:
    preset = HeadlinePresetV22()
    n_units = smallest_n_units_v2(sheets, preset, seed).n_units
    return plan_plant(preset.generator_config(n_units, seed))


def test_every_service_of_the_generator_has_a_connector_code() -> None:
    assert set(FLUID_CLASS_OF_SERVICE) <= set(SERVICE_CODE)
    assert code_of_service("FL") is ConnectorCode.NETWORK
    assert code_of_service("CWS") is ConnectorCode.UTILITY
    with pytest.raises(ValueError, match="expected a service"):
        code_of_service("XX")


def test_hand_plan_connectors_by_code_match_the_hand_counts() -> None:
    rows = {r.sheet_group: r for r in sheet_rows_of_plan(hand_plan())}
    # stubs and signal cuts per sheet are in composition_fixture.py; every pipe there is `P`
    assert [(rows[s].process, rows[s].signal) for s in ("1:1", "1:2", "2:1")] == [
        (2, 1),
        (3, 1),
        (1, 0),
    ]
    assert all(r.kind is SheetKind.PROCESS for r in rows.values())


def test_hand_plan_kind_report_numbers() -> None:
    report = build_kind_report("hand", [sheet_rows_of_plan(hand_plan())])
    process = report.summary_of(SheetKind.PROCESS)
    assert process is not None and report.summary_of(SheetKind.NETWORK) is None
    assert (process.sheets, process.equipment_max) == (3, 3)
    assert process.equipment_distribution == {1: 1, 2: 1, 3: 1}
    assert process.connectors_mean == pytest.approx((3 + 4 + 1) / 3)
    assert process.total_by_code == {"P": 6, "N": 0, "U": 0, "S": 2}
    assert process.share_with_network_connector == 0.0
    assert "process sheets: 3" in render_kind_report(report)


def test_a_report_without_sheets_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one sheet"):
        build_kind_report("none", [[]])


def test_v22_plant_splits_into_kinds_that_add_up() -> None:
    plan = _v22_plan()
    rows = sheet_rows_of_plan(plan)  # raises if a split misses a stub `sheet_stats` counted
    report = build_kind_report("v2.2", [rows])
    assert sum(s.sheets for s in report.summaries) == plan.sheet_count
    network = report.summary_of(SheetKind.NETWORK)
    assert network is not None
    assert network.equipment_max == 0 and network.total_by_code["S"] == 0
    assert network.total_by_code["P"] == 0  # header sheets carry only N and U pipes


def test_pooling_adds_the_sheets_of_every_plant() -> None:
    rows = sheet_rows_of_plan(hand_plan())
    pooled = build_kind_report("two", [rows, rows])
    assert (pooled.plants, pooled.sheets) == (2, 6)


def test_ch20_constants_agree_with_the_note() -> None:
    assert sum(ch20.PROCESS_EQUIPMENT_DISTRIBUTION.values()) == ch20.PROCESS_SHEETS
    assert sum(ch20.PROCESS_CONNECTORS_BY_CODE.values()) == 97
    assert ch20.NETWORK_SHEETS + ch20.INTERAREA_SHEETS == ch20.NETWORK_AND_INTERAREA_SHEETS


def test_comparison_puts_ch20_beside_each_run(tmp_path: Path) -> None:
    report = build_kind_report("hand", [sheet_rows_of_plan(hand_plan())])
    rows = compare([report])
    mean = next(r for r in rows if r.measure == "Process: equipment per sheet, mean")
    assert (mean.ch20, mean.runs["hand"]) == (1.72, 2.0)
    network = next(r for r in rows if r.measure == "Network sheets")
    assert network.runs["hand"] is None  # the run has no network sheet
    assert "| Measure | Toghraei ch.20 | v2.2: hand |" in render_markdown(rows)
    with pytest.raises(ValueError, match="distinct run labels"):
        compare([report, report])
    run = tmp_path / "run.json"
    run.write_text(report.model_dump_json(), encoding="utf-8")
    assert KindReport.model_validate_json(run.read_text(encoding="utf-8")) == report
    out = tmp_path / "table.json"
    assert comparison_main([str(run), "--json", str(out), "--md", str(tmp_path / "t.md")]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["source"] == ch20.NOTE_PATH


def test_the_v22_report_prints_a_g22_corpus_id_and_v21_keeps_g21(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["--target-sheets", "10", "--seeds", "2", "--generator", "v2.2"])
    assert "X10g22s2" in capsys.readouterr().out
    main(["--target-sheets", "10", "--seeds", "2"])
    assert "X10g21s2" in capsys.readouterr().out
