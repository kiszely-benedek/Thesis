"""The Results tab's projection (DP-T9): report files in, typed views out, nothing invented."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from plantgraph.demo.app.config import DemoConfig, ResultsSources
from plantgraph.demo.app.results import ladder_view, results_view, sealed_view
from plantgraph.demo.app.server import create_app
from plantgraph.demo.app.state import AppState

REAL_LADDER = Path("data/runs/exp0001/report/report.json")
REAL_SEALED = Path("data/runs/sealed/report/report.json")
INTERVAL = {"estimate": 0.5, "ci_low": 0.4, "ci_high": 0.6}


def _cell(corpus: str, policy: str, scope: str = "common") -> dict[str, Any]:
    return {
        "corpus_id": corpus,
        "policy": policy,
        "scope": scope,
        "n": 10,
        "acc_at_120": INTERVAL,
        "cost_mean": 0.001,
        "latency_median": 4.0,
        "extra_field": "ignored",
    }


def _ladder_json() -> dict[str, Any]:
    return {
        "cutoff_s": 120.0,
        "wall_sheets": 142.5,
        "absent": ["ctx-low at H3: no run"],
        "sizes": [{"corpus_id": "H1", "n_sheets": 1}, {"corpus_id": "H3", "n_sheets": 4}],
        "scope_families": {"common": ["A", "B"], "all": ["A", "B", "C"]},
        "cells": [
            _cell("H1", "ctx-high"),
            _cell("H3", "cascade_v3"),
            _cell("H3", "cascade_v3", scope="all"),
        ],
    }


def _sealed_row(corpus: str, policy: str, scope: str) -> dict[str, Any]:
    summary = {
        "n_questions": 460,
        "n_correct_at_cutoff": 422,
        "cost_per_question_usd": 0.0007,
        "latency_median_s": 8.2,
        "latency_p90_s": 22.5,
    }
    return {
        "corpus_id": corpus,
        "scope": scope,
        "policy": policy,
        "summary": summary,
        "accuracy": INTERVAL,
    }


def _sealed_json() -> dict[str, Any]:
    rows = [
        _sealed_row("H100", "cascade_v3", "headline"),
        _sealed_row("H100", "cascade_v3", "held-out"),
        _sealed_row("H100", "cascade_v3_iso", "headline"),
        _sealed_row("H1000", "always_c_luna", "headline"),
    ]
    return {"sealed": {"sheets": {"H100": 100, "H1000": 1001}, "scope_rows": rows}}


def _write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_ladder_keeps_only_the_common_scope_and_resolves_sheets(tmp_path: Path) -> None:
    view = ladder_view(_write(tmp_path / "l.json", _ladder_json()), "ROW")

    assert [(p.corpus_id, p.n_sheets, p.arm) for p in view.points] == [
        ("H1", 1, "ctx-high"),
        ("H3", 4, "cascade_v3"),
    ]
    assert view.n_families == 2
    assert view.wall_sheets == 142.5
    assert view.absent == ("ctx-low at H3: no run",)
    assert view.source.result_row == "ROW"
    assert len(view.source.sha256) == 64


def test_sealed_keeps_headline_rows_of_the_three_policies(tmp_path: Path) -> None:
    view = sealed_view(_write(tmp_path / "s.json", _sealed_json()), "ROW")

    assert [(r.corpus_id, r.policy, r.n_sheets) for r in view.rows] == [
        ("H100", "cascade_v3", 100),
        ("H1000", "always_c_luna", 1001),
    ]
    assert view.rows[0].n_correct == 422


def test_missing_field_names_the_file_and_the_field(tmp_path: Path) -> None:
    broken = _ladder_json()
    del broken["wall_sheets"]
    path = _write(tmp_path / "l.json", broken)

    with pytest.raises(ValueError, match=r"wall_sheets.*l\.json"):
        ladder_view(path, "ROW")


def test_missing_file_is_reported_with_its_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="nope.json"):
        sealed_view(tmp_path / "nope.json", "ROW")


def _client(tmp_path: Path, results: ResultsSources | None) -> TestClient:
    config = SimpleNamespace(results=results)
    state = cast(AppState, SimpleNamespace(config=cast(DemoConfig, config)))
    return TestClient(create_app(state))


def test_endpoint_serves_both_views(tmp_path: Path) -> None:
    sources = ResultsSources(
        ladder_report=_write(tmp_path / "l.json", _ladder_json()),
        sealed_report=_write(tmp_path / "s.json", _sealed_json()),
    )
    body = _client(tmp_path, sources).get("/api/results").json()

    assert body["ladder"]["scope"] == "common"
    assert body["sealed"]["scope"] == "headline"
    assert body["sealed"]["source"]["result_row"] == "EXP-0002-H100, EXP-0002-H1000"


def test_endpoint_is_404_when_not_configured(tmp_path: Path) -> None:
    response = _client(tmp_path, None).get("/api/results")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "results_not_configured"


def test_endpoint_is_404_when_a_report_is_missing(tmp_path: Path) -> None:
    sources = ResultsSources(ladder_report=tmp_path / "a", sealed_report=tmp_path / "b")
    response = _client(tmp_path, sources).get("/api/results")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "missing_file"


@pytest.mark.skipif(not (REAL_LADDER.exists() and REAL_SEALED.exists()), reason="no local runs")
def test_recorded_reports_project_to_the_published_figures() -> None:
    view = results_view(ResultsSources(ladder_report=REAL_LADDER, sealed_report=REAL_SEALED))
    ladder, sealed = view.ladder, view.sealed
    assert ladder is not None and sealed is not None

    assert ladder.n_families == 19
    assert {p.n_sheets for p in ladder.points} == {1, 4, 10, 30}
    h1_ctx = next(p for p in ladder.points if p.corpus_id == "H1" and p.arm == "ctx-high")
    assert (h1_ctx.n, round(h1_ctx.accuracy.estimate, 3)) == (68, 0.824)
    h1000 = next(r for r in sealed.rows if r.corpus_id == "H1000" and r.policy == "cascade_v3")
    assert (h1000.n_correct, h1000.n_questions) == (422, 460)
