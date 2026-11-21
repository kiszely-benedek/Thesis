"""Results sources v2 (T3a): ladder scope, several sealed sources, pooled and plant rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from plantgraph.demo.app.config import (
    DemoCorpus,
    LadderSource,
    ResultsSources,
    SealedSource,
)
from plantgraph.demo.app.results import ladder_view, results_view, sealed_view

EXP0008 = Path("data/runs/exp0008")
INTERVAL = {"estimate": 0.5, "ci_low": 0.4, "ci_high": 0.6}


def _write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _row(corpus: str, policy: str, scope: str = "headline", n: int = 220) -> dict[str, Any]:
    summary = {
        "n_questions": n,
        "n_correct_at_cutoff": n // 2,
        "cost_per_question_usd": 0.001,
        "latency_median_s": 8.0,
        "latency_p90_s": 40.0,
        "extra": "ignored",
    }
    return {
        "corpus_id": corpus,
        "scope": scope,
        "policy": policy,
        "summary": summary,
        "accuracy": INTERVAL,
    }


def _claim(rule: str, status: str, headline: str) -> dict[str, Any]:
    return {"rule": rule, "status": status, "headline": headline, "details": []}


def _sealed_json(policy: str = "cascade_v4_iso") -> dict[str, Any]:
    """The EXP-0008 shape: `sheets` names pooled ids only; `scales` lists each pool's plants."""
    rows = [
        _row("P1", policy),
        _row("P1", policy, scope="held-out", n=50),
        _row("P1", "other_policy"),
        _row("P2", policy),
        _row("S100", policy, n=1100),
        _row("S100", policy, scope="held-out", n=250),
    ]
    claims = [
        _claim("K1", "FAIL", "K1 [headline]: the cascade saves nothing"),
        _claim("K3", "FAIL", "K3 [held-out]: not fast enough"),
        _claim("Q1", "NOT_RUN", "Q1: not run - dropped"),
    ]
    sealed = {
        "sheets": {"S100": 101},
        "scales": {"S100": ["P1", "P2"]},
        "scope_rows": rows,
        "claims": claims,
    }
    return {"sealed": sealed}


def _plant(tmp_path: Path, corpus_id: str, n_sheets: int) -> DemoCorpus:
    ingest = _write(tmp_path / f"{corpus_id}.ingest.json", {"counts": {"n_sheets": n_sheets}})
    return DemoCorpus(corpus_id=corpus_id, ingest_json=ingest, drawings_dir=tmp_path, tier_runs={})


def _source(report: Path, **changes: Any) -> SealedSource:
    fields: dict[str, Any] = {
        "report": report,
        "result_row": "ROW",
        "label": "V2T-A2",
        "policies": ("cascade_v4_iso",),
    }
    return SealedSource(**{**fields, **changes})


# --- config -------------------------------------------------------------------------------------


def test_v1_flat_keys_become_the_v1_sources() -> None:
    sources = ResultsSources.model_validate(
        {"ladder_report": "l.json", "sealed_report": "s.json", "sealed_result_row": "R"}
    )

    assert sources.ladder is not None and sources.ladder.scope == "common"
    assert sources.ladder.result_row == "EXP-0001-LADDER"
    (sealed,) = sources.sealed
    assert (sealed.result_row, sealed.scopes, sealed.corpora) == ("R", ("headline",), ())
    assert sealed.policies == ("cascade_v3", "always_g_luna", "always_c_luna")


def test_mixing_v1_and_v2_keys_is_refused() -> None:
    with pytest.raises(ValueError, match="found both"):
        ResultsSources.model_validate({"ladder_report": "l.json", "sealed": []})


# --- sealed -------------------------------------------------------------------------------------


def test_pooled_row_takes_sheets_from_the_report_and_plant_row_from_ingest(
    tmp_path: Path,
) -> None:
    report = _write(tmp_path / "s.json", _sealed_json())
    source = _source(report, corpora=("S100", "P1"))

    view = sealed_view([source], [_plant(tmp_path, "P1", 99)])

    pooled, plant = sorted(view.rows, key=lambda r: not r.pooled)
    assert (pooled.corpus_id, pooled.n_sheets, pooled.n_plants) == ("S100", 101, 2)
    assert pooled.interval_method == "two-stage bootstrap"
    assert (plant.corpus_id, plant.n_sheets, plant.n_plants) == ("P1", 99, None)
    assert plant.interval_method == "wilson"
    assert {r.scope for r in view.rows} == {"headline"}


def test_scopes_select_rows_and_claim_lines(tmp_path: Path) -> None:
    report = _write(tmp_path / "s.json", _sealed_json())
    source = _source(report, scopes=("headline", "held-out"), corpora=("S100",))

    view = sealed_view([source], [])

    assert [(r.scope, r.n_questions) for r in view.rows] == [("headline", 1100), ("held-out", 250)]
    assert [(c.claim_id, c.verdict) for c in view.claims] == [
        ("K1", "FAIL"),
        ("K3", "FAIL"),
        ("Q1", "NOT_RUN"),
    ]


def test_claims_of_an_unshown_scope_are_left_out(tmp_path: Path) -> None:
    report = _write(tmp_path / "s.json", _sealed_json())

    view = sealed_view([_source(report, corpora=("S100",))], [])

    assert [c.claim_id for c in view.claims] == ["K1", "Q1"]


def test_unknown_plant_gives_a_clear_error(tmp_path: Path) -> None:
    report = _write(tmp_path / "s.json", _sealed_json())

    with pytest.raises(ValueError, match=r"corpus 'P2'.*pooled scale.*configured plant"):
        sealed_view([_source(report, corpora=("P2",))], [_plant(tmp_path, "P1", 99)])


def test_a_selection_without_rows_is_an_error_not_an_empty_table(tmp_path: Path) -> None:
    report = _write(tmp_path / "s.json", _sealed_json())

    with pytest.raises(ValueError, match="found none for"):
        sealed_view([_source(report, policies=("nobody",))], [])
    with pytest.raises(ValueError, match=r"found none for \['S1000'\]"):
        sealed_view([_source(report, corpora=("S100", "S1000"))], [])


def test_two_sealed_sources_merge_with_their_own_labels(tmp_path: Path) -> None:
    v2 = _write(tmp_path / "v2.json", _sealed_json("cascade_v4_iso"))
    f1 = _write(tmp_path / "f1.json", _sealed_json("cascade_v3"))
    sources = [
        _source(v2, corpora=("S100",)),
        _source(f1, label="F1, previous system", policies=("cascade_v3",), corpora=("S100",)),
    ]

    view = sealed_view(sources, [])

    assert [(r.source_label, r.policy) for r in view.rows] == [
        ("V2T-A2", "cascade_v4_iso"),
        ("F1, previous system", "cascade_v3"),
    ]
    assert len(view.sources) == 2
    assert not hasattr(view, "source")  # the v1 front end that read it is gone


# --- ladder -------------------------------------------------------------------------------------


def _ladder_json() -> dict[str, Any]:
    def cell(scope: str) -> dict[str, Any]:
        return {
            "corpus_id": "H1",
            "policy": "ag",
            "scope": scope,
            "n": 10,
            "acc_at_120": INTERVAL,
            "cost_mean": 0.001,
            "latency_median": 4.0,
        }

    return {
        "cutoff_s": 120.0,
        "wall_sheets": 66.7,
        "absent": [],
        "sizes": [{"corpus_id": "H1", "n_sheets": 1, "extra": 1}],
        "scope_families": {"common": ["A"], "all": ["A", "B"]},
        "cells": [cell("common"), cell("all"), cell("all")],
        "claims": [{"id": "X1", "wording": "Shrinks", "value": "slope", "verdict": "FAIL"}],
    }


def test_ladder_common_and_all_scopes_both_work(tmp_path: Path) -> None:
    report = _write(tmp_path / "l.json", _ladder_json())

    common = ladder_view(LadderSource(report=report, result_row="ROW"))
    everything = ladder_view(LadderSource(report=report, result_row="ROW", scope="all"))

    assert (common.scope, common.n_families, len(common.points)) == ("common", 1, 1)
    assert (everything.scope, everything.n_families, len(everything.points)) == ("all", 2, 2)
    assert [(c.claim_id, c.verdict) for c in common.claims] == [("X1", "FAIL")]


# --- the real EXP-0008 reports ------------------------------------------------------------------

REAL = EXP0008 / "reports"


@pytest.mark.skipif(not (REAL / "sealed" / "report.json").exists(), reason="no local runs")
def test_recorded_exp0008_reports_match_the_result_note() -> None:
    plants = [
        DemoCorpus(
            corpus_id=c,
            ingest_json=EXP0008 / "corpora" / c / "ingest.json",
            drawings_dir=Path("."),
            tier_runs={},
        )
        for c in ("H100g21p1", "H1000g21p1")
    ]
    sources = ResultsSources(
        ladder=LadderSource(report=REAL / "ladder" / "report.json", result_row="L"),
        sealed=(
            _source(
                REAL / "sealed" / "report.json",
                corpora=("S100", "S1000", "H1000g21p1"),
                scopes=("headline", "held-out"),
            ),
            _source(
                REAL / "f1_baseline" / "report.json",
                label="F1, previous system",
                policies=("cascade_v3",),
                corpora=("S1000", "H100g21p1"),
            ),
        ),
    )

    view = results_view(sources, plants)
    sealed, ladder = view.sealed, view.ladder
    assert sealed is not None and ladder is not None

    def find(corpus: str, policy: str, scope: str = "headline") -> Any:
        return next(
            r for r in sealed.rows if (r.corpus_id, r.policy, r.scope) == (corpus, policy, scope)
        )

    s1000 = find("S1000", "cascade_v4_iso")
    assert (s1000.n_correct, s1000.n_questions, s1000.n_sheets) == (999, 1100, 1001)
    assert (s1000.pooled, s1000.n_plants) == (True, 5)
    plant = find("H1000g21p1", "cascade_v4_iso")
    assert (plant.n_correct, plant.n_questions, plant.n_sheets) == (199, 220, 1000)
    assert plant.interval_method == "wilson"
    assert find("H100g21p1", "cascade_v3").n_sheets == 100
    assert {c.claim_id: c.verdict for c in sealed.claims}["K1"] == "FAIL"
    assert ladder.scope == "common" and ladder.n_families == 19
    assert {c.claim_id: c.verdict for c in ladder.claims}["X1"] == "FAIL"
