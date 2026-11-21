"""Results sources v2 (T3b): the infrastructure and end-to-end readers and the startup check."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from plantgraph.demo.app.config import (
    E2ESource,
    InfraRow,
    InfraSource,
    LadderSource,
    ResultsSources,
)
from plantgraph.demo.app.results import check_results_sources, results_view
from plantgraph.demo.app.results_infra import e2e_view, infra_view

REAL = Path("data/runs/exp0008")
INTERVAL = {"estimate": 0.9, "ci_low": 0.8, "ci_high": 0.95}


def _write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _growth(name: str, small: float, large: float) -> dict[str, Any]:
    return {
        "name": name,
        "from_corpus": "P1",
        "to_corpus": "P2",
        "from_value": small,
        "to_value": large,
        "note": "ignored",
    }


def _infra_json() -> dict[str, Any]:
    checks = [
        {"name": "M1 replay answers byte-identical", "status": "fail", "detail": "fell back"},
        {"name": "M2 clock resolution", "status": "pass", "detail": "fine"},
        {"name": "Old-run rows", "status": "flag", "detail": "agent rows are source timings"},
    ]
    growth = [
        _growth("ingest.build_total", 9.4, 427.3),
        _growth("store.data_bytes", 6891281, 58951570),
        _growth("size.sheets", 100, 1000),
    ]
    return {"machine_summary": "a laptop", "checks": checks, "growth": growth, "compute": []}


def _infra_source(path: Path, *rows: InfraRow) -> InfraSource:
    return InfraSource(report=path, result_row="EXP-0008", rows=rows)


def test_infra_rows_follow_the_config_with_its_units(tmp_path: Path) -> None:
    report = _write(tmp_path / "infra.json", _infra_json())
    source = _infra_source(
        report,
        InfraRow(name="store.data_bytes", unit="bytes"),
        InfraRow(name="ingest.build_total", unit="s"),
    )
    view = infra_view(source)
    assert [(r.name, r.unit) for r in view.rows] == [
        ("store.data_bytes", "bytes"),
        ("ingest.build_total", "s"),
    ]
    assert (view.rows[1].from_value, view.rows[1].to_value) == (9.4, 427.3)
    assert view.machine == "a laptop"
    assert view.source.result_row == "EXP-0008"


def test_infra_failed_and_flagged_checks_are_check_lines(tmp_path: Path) -> None:
    report = _write(tmp_path / "infra.json", _infra_json())
    view = infra_view(_infra_source(report, InfraRow(name="size.sheets", unit="count")))
    verdicts = {line.claim_id: line.verdict for line in view.checks}
    assert verdicts == {"M1": "FAIL", "M2": "PASS", "Old-run rows": "FLAG"}


def test_infra_unknown_row_name_is_a_clear_error(tmp_path: Path) -> None:
    report = _write(tmp_path / "infra.json", _infra_json())
    source = _infra_source(report, InfraRow(name="ingest.nonsense", unit="s"))
    with pytest.raises(ValueError, match="ingest.nonsense"):
        infra_view(source)


def _arm(label: str, n: int = 220) -> dict[str, Any]:
    return {"label": label, "n": n, "n_correct": 190, "accuracy": INTERVAL, "spend_usd": 9.99}


def _e2e_json() -> dict[str, Any]:
    claim = {
        "claim": "E1",
        "description": "acc(V,D0) - acc(R5)",
        "rule": "CI upper < 0",
        "difference": {"mean": -0.085, "ci_low": -0.108, "ci_high": -0.065},
        "passed": True,
        "n_plants": 5,
    }
    failed = {**claim, "claim": "E3", "passed": False}
    return {
        "policy": "cascade_v4_iso",
        "plants": [{"plant_id": "P1", "arms": [_arm("R5"), _arm("V-d0")]}],
        "arms": [_arm("R5", 1100), _arm("V-d0", 1100)],
        "claims": [claim, failed],
        "notes": ["# EXP-0004 is a mislabelled title"],
    }


def test_e2e_maps_mean_and_passed_and_hides_spend(tmp_path: Path) -> None:
    report = _write(tmp_path / "e2e.json", _e2e_json())
    view = e2e_view(
        E2ESource(report=report, result_row="EXP-0008", arms=("R5", "V-d0"), plant="P1")
    )
    assert [(a.corpus, a.label, a.n, a.interval_method) for a in view.arms] == [
        ("pooled", "R5", 1100, "two-stage bootstrap"),
        ("pooled", "V-d0", 1100, "two-stage bootstrap"),
        ("P1", "R5", 220, "wilson"),
        ("P1", "V-d0", 220, "wilson"),
    ]
    assert [(c.claim_id, c.verdict) for c in view.claims] == [("E1", "PASS"), ("E3", "FAIL")]
    assert "-0.085" in view.claims[0].text
    dumped = view.model_dump_json()
    assert "spend" not in dumped and "EXP-0004" not in dumped


def test_e2e_without_a_plant_shows_pooled_arms_only(tmp_path: Path) -> None:
    report = _write(tmp_path / "e2e.json", _e2e_json())
    view = e2e_view(E2ESource(report=report, result_row="r", arms=("R5",)))
    assert [a.corpus for a in view.arms] == ["pooled"]


def test_e2e_unknown_plant_or_arm_is_a_clear_error(tmp_path: Path) -> None:
    report = _write(tmp_path / "e2e.json", _e2e_json())
    with pytest.raises(ValueError, match="'P9'"):
        e2e_view(E2ESource(report=report, result_row="r", arms=("R5",), plant="P9"))
    with pytest.raises(ValueError, match="V-d9"):
        e2e_view(E2ESource(report=report, result_row="r", arms=("V-d9",)))


def test_v1_config_still_parses_without_the_new_sources() -> None:
    sources = ResultsSources.model_validate({"ladder_report": "a.json", "sealed_report": "b.json"})
    assert sources.infra is None and sources.e2e is None


def test_startup_check_passes_without_results_and_names_a_missing_file(tmp_path: Path) -> None:
    check_results_sources(None, ())
    missing = ResultsSources(e2e=E2ESource(report=tmp_path / "nope.json", result_row="r"))
    with pytest.raises(FileNotFoundError, match="nope.json"):
        check_results_sources(missing, ())


def test_startup_check_catches_an_unknown_infra_row(tmp_path: Path) -> None:
    report = _write(tmp_path / "infra.json", _infra_json())
    bad = ResultsSources(infra=_infra_source(report, InfraRow(name="typo", unit="s")))
    with pytest.raises(ValueError, match="typo"):
        check_results_sources(bad, ())


def test_real_exp0008_infra_and_e2e_match_the_results_note() -> None:
    sources = ResultsSources(
        infra=_infra_source(
            REAL / "infra" / "report.json",
            InfraRow(name="store.data_bytes", unit="bytes"),
            InfraRow(name="ingest.build_total", unit="s"),
        ),
        e2e=E2ESource(
            report=REAL / "reports" / "e2e" / "report.json",
            result_row="EXP-0008",
            plant="H1000g21p1",
        ),
    )
    check_results_sources(sources, ())
    view = results_view(sources)
    assert view.infra is not None and view.e2e is not None
    store = view.infra.rows[0]
    # the note's "6.6 MiB -> 56.2 MiB", as the report gives it in bytes
    assert round(store.from_value / 2**20, 1) == 6.6
    assert round(store.to_value / 2**20, 1) == 56.2
    assert {c.claim_id: c.verdict for c in view.infra.checks}["M1"] == "FAIL"
    pooled = {a.label: a for a in view.e2e.arms if a.corpus == "pooled"}
    assert round(pooled["V-d2"].accuracy.estimate, 3) == 0.856
    assert {c.claim_id: c.verdict for c in view.e2e.claims}["E3"] == "FAIL"


def test_ladder_source_is_unaffected_by_the_new_fields() -> None:
    assert LadderSource(report=Path("x.json"), result_row="r").scope == "common"
