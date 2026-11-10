"""The concurrency-1 control report (F15 / R3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from audit_fakes import make_question, make_result
from plantgraph.qa.exp0008 import c1_report
from plantgraph.qa.models import QuestionResult


def _rows(correct: list[bool], latency: float = 2.0) -> dict[str, QuestionResult]:
    rows = {}
    for number, verdict in enumerate(correct):
        question = make_question(number)
        row = make_result(question, correct=verdict)
        rows[question.question_id] = row.model_copy(update={"latency_s": latency + number})
    return rows


def test_the_comparison_counts_correct_agreement_and_latency() -> None:
    main = _rows([True, True, False, True])
    control = {qid: row for qid, row in list(_rows([True, False, False, True]).items())[:3]}

    result = c1_report.compare(main, control)

    assert result.n_questions == 3
    assert (result.main_correct, result.control_correct, result.verdicts_agree) == (2, 1, 2)
    assert result.main_latency_median_s == pytest.approx(3.0)
    assert "agrees on 2 of 3" in c1_report.render(result)


def test_a_control_question_missing_from_the_main_run_is_refused() -> None:
    with pytest.raises(ValueError, match="every control question"):
        c1_report.compare(_rows([True]), _rows([True, True]))


def test_an_empty_control_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one row"):
        c1_report.compare(_rows([True]), {})


def test_the_command_reads_two_answer_files_and_writes_the_report(tmp_path: Path) -> None:
    for name, rows in (("main", _rows([True, False])), ("control", _rows([True, False]))):
        text = "".join(row.model_dump_json() + "\n" for row in rows.values())
        (tmp_path / f"{name}.jsonl").write_text(text, encoding="utf-8")
    out = tmp_path / "out" / "report.md"

    status = c1_report.main(
        [
            "--main-answers", str(tmp_path / "main.jsonl"),
            "--control-answers", str(tmp_path / "control.jsonl"),
            "--out", str(out),
        ]
    )  # fmt: skip

    assert status == 0 and "agrees on 2 of 2" in out.read_text(encoding="utf-8")
