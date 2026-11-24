"""The GLM report: a paired difference with an interval, and cost, latency and outcomes per tier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_records import two_runs

from plantgraph.qa.exp0009 import glm_arm, glm_report, launcher
from plantgraph.qa.exp0009.cascade_report import ArmReport
from plantgraph.qa.exp0009.glm_report import SystemRuns
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import QuestionResult


def _rows() -> list[QuestionResult]:
    return RunDir(two_runs().a_run).read_rows()


def _system(name: str, correct: set[str], rows: list[QuestionResult]) -> SystemRuns:
    return SystemRuns(
        name=name, correct_ids=frozenset(correct), rows_by_tier={"cyp": rows, "ag": rows}
    )


def test_paired_difference_is_glm_minus_luna_on_the_same_questions() -> None:
    rows = _rows()
    ids = sorted({r.question_id for r in rows})
    luna = _system("Luna", set(ids[:4]), rows)
    glm = _system("GLM", set(ids[:7]), rows)
    result = glm_report.compare_plant("H100g22p1", 100, ids, luna, glm)
    assert (result.luna.n_correct, result.glm.n_correct) == (4, 7)
    assert result.glm_minus_luna.mean == pytest.approx(3 / len(ids))
    assert (
        result.glm_minus_luna.ci_low <= result.glm_minus_luna.mean <= result.glm_minus_luna.ci_high
    )


def test_cost_latency_and_outcomes_come_from_each_tiers_rows() -> None:
    rows = _rows()
    ids = frozenset(r.question_id for r in rows)
    tier = glm_report.summarize_tier("ag", rows, ids)
    expected = sum(r.total_cost_usd or 0.0 for r in rows) / len(rows)
    assert tier.cost_per_question_usd == pytest.approx(expected)
    assert sum(tier.outcomes.values()) == len(rows) and tier.p90_latency_s >= tier.median_latency_s


def test_a_run_missing_a_row_is_not_compared() -> None:
    rows = _rows()
    ids = frozenset(r.question_id for r in rows)
    with pytest.raises(ValueError, match="a cyp row for each"):
        glm_report.summarize_tier("cyp", rows[:-1], ids)


def test_the_markdown_has_the_difference_interval_cost_and_outcomes() -> None:
    rows = _rows()
    ids = sorted({r.question_id for r in rows})
    both = glm_report.compare_plant(
        "H100g22p1",
        100,
        ids,
        _system("Luna", set(ids[:2]), rows),
        _system("GLM", set(ids[:3]), rows),
    )
    text = glm_report.render_markdown([both])
    for expected in (
        "H100g22p1",
        "GLM - Luna (points)",
        "95 % interval",
        "$ per question",
        "ANSWERED",
    ):
        assert expected in text


def test_glm_report_command_reads_both_systems_from_disk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prereg = tmp_path / "prereg"
    assert launcher.main(["draw", "--smoke", "--prereg", str(prereg)]) == 0
    rows_file = two_runs().a_run / "answers.jsonl"
    questions_file = two_runs().root / "questions" / "D100g22" / "questions.jsonl"
    ids = sorted({r.question_id for r in _rows()})
    for plant in ("H100g22p1", "H1000g22p1"):
        folder = tmp_path / glm_arm.FOLDER / "questions" / plant
        folder.mkdir(parents=True)
        (folder / "questions.jsonl").write_bytes(questions_file.read_bytes())
        runs = {
            glm_arm.run_id(t, plant): tmp_path / glm_arm.FOLDER / "runs" for t in ("cyp", "ag")
        } | {f"S9-{t.upper()}-{plant}": tmp_path / "p1c" / "runs" for t in ("cyp", "ag")}
        for name, parent in runs.items():
            (parent / name).mkdir(parents=True, exist_ok=True)
            (parent / name / "answers.jsonl").write_bytes(rows_file.read_bytes())
        for system, path, k in (
            ("luna", tmp_path / "reports" / f"{plant}_a2.json", 3),
            ("glm", tmp_path / "reports" / "glm" / f"{plant}_glm.json", 5),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            report = ArmReport(
                corpus_id=plant, arm="A2", policy="cascade_v4_iso", n_questions=len(ids),
                n_correct=k, by_family={"X": (k, len(ids))}, correct_ids=tuple(ids[:k]),
            )  # fmt: skip
            path.write_text(report.model_dump_json(), encoding="utf-8")
            assert system
    argv = ["glm-report", "--root", str(tmp_path), "--prereg", str(prereg)]
    assert launcher.main(argv) == 0
    assert "H1000g22p1" in capsys.readouterr().out
    document = json.loads(
        (tmp_path / "reports" / "glm_comparison.json").read_text(encoding="utf-8")
    )
    assert [c["plant_id"] for c in document] == ["H100g22p1", "H1000g22p1"]
    assert document[0]["glm_minus_luna"]["mean"] == pytest.approx(2 / len(ids))
    assert (tmp_path / "reports" / "glm_comparison.md").is_file()
