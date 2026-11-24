"""Precision, recall, F1 over the cascade's final answers: each row from the tier that gave it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_analysis_fixtures import Recipe, build_root

from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade import join
from plantgraph.qa.cascade.evaluate import Evaluation, ScoredDecision
from plantgraph.qa.cascade.models import Decision
from plantgraph.qa.exp0009 import analysis
from plantgraph.qa.exp0009.analysis_misc import final_answer_rows
from plantgraph.qa.exp0009.records import RescoreReport, RowScore
from plantgraph.qa.need.labels import NeedLabel


@pytest.fixture(autouse=True)
def _toy_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """No graph behind the toy plants: every question is GENERIC and anchors are empty."""
    monkeypatch.setattr(join, "classify_need", lambda text, finder: NeedLabel.GENERIC)
    monkeypatch.setattr(
        analysis, "corpus_finder", lambda root: lambda corpus_id: lambda t: Anchors()
    )


def _row(question_id: str, f1: float) -> RowScore:
    return RowScore(
        question_id=question_id, stored_correct=False, correct=False,
        precision=f1, recall=f1, f1=f1,
    )  # fmt: skip


def _decision(question_id: str, answered_by: str | None) -> ScoredDecision:
    decision = Decision(
        policy="cascade_v4_iso", question_id=question_id, tiers_tried=("cypher-v2t",),
        answered_by=answered_by, cost_usd=0.0, latency_s=1.0, latency_complete=True,
    )  # fmt: skip
    return ScoredDecision(decision=decision, correct=False)


def test_each_question_is_scored_from_the_tier_that_answered_it() -> None:
    evaluation = Evaluation.model_construct(
        summary=None,
        scored=(
            _decision("q1", "cypher-v2t"), _decision("q2", "agent-v2t"),
            _decision("q3", None), _decision("q4", "agent-v2t"),
        ),
    )  # fmt: skip
    cypher = RescoreReport(rows=[_row("q1", 0.1), _row("q2", 0.2), _row("q3", 0.3)])
    agent = RescoreReport(rows=[_row("q1", 0.9), _row("q2", 0.8), _row("q4", 0.7)])
    rows, counts = final_answer_rows(evaluation, {"CYP": cypher, "AG": agent})
    assert {r.question_id: r.f1 for r in rows} == {"q1": 0.1, "q2": 0.8, "q4": 0.7}
    assert counts == {"CYP": 1, "AG": 2}  # q3 failed: no tier answered it


def test_a_tier_without_a_rescore_gives_no_rows() -> None:
    evaluation = Evaluation.model_construct(summary=None, scored=(_decision("q1", "cypher-v2t"),))
    rows, counts = final_answer_rows(evaluation, {"CYP": None, "AG": RescoreReport(rows=[])})
    assert rows == [] and counts == {"CYP": 0, "AG": 0}


def test_the_analysis_writes_the_final_answer_table_and_names_a_missing_cypher_rescore(
    tmp_path: Path,
) -> None:
    root = build_root(tmp_path / "exp0009", Recipe())
    assert analysis.main(["--root", str(root)]) == 0
    data = json.loads((root / "reports" / "analysis.json").read_text(encoding="utf-8"))
    tables = {t["name"]: t for t in data["tables"]}
    assert {"precision_recall", "precision_recall_final"} <= set(tables)
    final = tables["precision_recall_final"]
    assert "from Cypher" in final["header"] and "final answers" in final["title"]
    assert "agent tier" in tables["precision_recall"]["title"]  # each table says its tier
    assert not [n for n in data["notes"] if "no re-score" in n]
    (root / "reports" / "rescore_CYP_H100g22p1.json").unlink()
    assert analysis.main(["--root", str(root)]) == 0
    notes = " ".join(json.loads((root / "reports" / "analysis.json").read_text("utf-8"))["notes"])
    assert "rescore_CYP_H100g22p1.json" in notes and "Cypher" not in notes.replace("CYP", "")
