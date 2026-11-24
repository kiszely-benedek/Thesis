"""The analysis as END calls it: files written, B not run, and refusals that name the input."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from test_analysis_fixtures import Recipe, build_root

from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade import join
from plantgraph.qa.exp0009 import analysis
from plantgraph.qa.exp0009.analysis_models import AnalysisReport, ClaimStatus
from plantgraph.qa.need.labels import NeedLabel


@pytest.fixture(autouse=True)
def _toy_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """No graph behind the toy plants: every question is GENERIC and anchors are empty."""
    monkeypatch.setattr(join, "classify_need", lambda text, finder: NeedLabel.GENERIC)
    monkeypatch.setattr(
        analysis, "corpus_finder", lambda root: lambda corpus_id: lambda t: Anchors()
    )


def test_end_can_import_the_module_it_checks_for() -> None:
    assert importlib.import_module("plantgraph.qa.exp0009.analysis").main is analysis.main


def test_end_s_call_writes_the_json_and_the_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = build_root(
        tmp_path / "exp0009", Recipe(a2_r={100: 20, 1000: 20}, b_r={100: 20, 1000: 20})
    )
    assert analysis.main(["--root", str(root)]) == 0  # END passes --root and nothing else
    reports = root / "reports"
    report = AnalysisReport.model_validate_json((reports / "analysis.json").read_text("utf-8"))
    text = (reports / "analysis.md").read_text(encoding="utf-8")
    assert "# EXP-0009 sealed analysis" in text and "| Q4 |" in text and "SB2" in text
    assert [c.claim for c in report.claims][:2] == ["Q4", "K1"]
    effect = [c for c in report.claims if c.claim == "Data effect"]
    assert effect[0].status is ClaimStatus.NOT_RUN and "no EXP-0008 root" in effect[0].detail
    assert "Q4: PASS" in capsys.readouterr().out


def test_when_b_was_not_run_every_b_claim_is_not_run(tmp_path: Path) -> None:
    root = build_root(tmp_path / "exp0009", Recipe(), b_sealed=False)
    assert analysis.main(["--root", str(root)]) == 0
    report = AnalysisReport.model_validate_json(
        (root / "reports" / "analysis.json").read_text("utf-8")
    )
    by_name = {c.claim: c for c in report.claims}
    for name in ("Q4-B", "Q4-B sensitivity", "SB1", "SB2"):
        assert by_name[name].status is ClaimStatus.NOT_RUN
        assert "state/b_sealed = no" in by_name[name].detail
    assert by_name["Q4"].status is not ClaimStatus.NOT_RUN  # A2 is unaffected
    assert not report.b_sealed and all(p.b_runs == [] for p in report.plants)
    names = {t.name for t in report.tables}
    assert {"position", "named_by", "x_subscopes", "precision_recall"} <= names
    prf = next(t for t in report.tables if t.name == "precision_recall")
    assert {row[0] for row in prf.rows} == {"V2T-A2"}  # no B arm to re-score


def test_a_missing_b_sealed_file_is_an_error_that_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = build_root(tmp_path / "exp0009", Recipe())
    (root / "state" / "b_sealed").unlink()
    assert analysis.main(["--root", str(root)]) == 1
    assert "b_sealed" in capsys.readouterr().err
    assert not (root / "reports" / "analysis.json").exists()


def test_a_missing_run_folder_stops_the_analysis(tmp_path: Path) -> None:
    root = build_root(tmp_path / "exp0009", Recipe())
    victim = root / "p1c" / "runs" / "S9-AG-H1000g22p2"
    for part in victim.iterdir():
        part.unlink()
    victim.rmdir()
    assert analysis.main(["--root", str(root)]) == 1


def test_a_missing_scope_report_is_refused_not_skipped(tmp_path: Path) -> None:
    root = build_root(tmp_path / "exp0009", Recipe())
    (root / "questions" / "H100g22p1" / "scope_report.json").unlink()
    assert analysis.main(["--root", str(root)]) == 1


def test_optional_inputs_that_are_missing_are_listed_in_the_notes(tmp_path: Path) -> None:
    root = build_root(tmp_path / "exp0009", Recipe())
    (root / "reports" / "rescore_AG_H100g22p1B.json").unlink()
    (root / "corpora" / "H100g22p1" / "rules.json").unlink()
    assert analysis.main(["--root", str(root)]) == 0
    data = json.loads((root / "reports" / "analysis.json").read_text(encoding="utf-8"))
    notes = " ".join(data["notes"])
    assert "rescore_AG_H100g22p1B.json" in notes and "no rules.json for H100g22p1" in notes
