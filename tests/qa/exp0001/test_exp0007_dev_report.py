"""The EXP-0007 dev quality check's report: per-family accuracy and the failure list."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from report_toy import (
    AGENT,
    CYPHER,
    luna_pin,
    row,
    write_ingest,
    write_questions,
    write_run,
)

from plantgraph.qa.exp0007.dev_report import (
    load_dev_report,
    render_dev_markdown,
    write_dev_report,
)

CORPUS = "D100g2"
FAMILIES = {
    f"{CORPUS}:1": "CONNECTED",
    f"{CORPUS}:2": "CONNECTED",
    f"{CORPUS}:3": "FLOW_PATH",
    f"{CORPUS}:4": "FLOW_PATH",
}


def _cypher_rows() -> list[dict[str, Any]]:
    """q1 right; q2 accepted but wrong; q3 returns no rows; q4 is a retrieval error."""
    q1, q2, q3, q4 = FAMILIES
    return [
        row(q1, CYPHER, True),
        row(q2, CYPHER, False, final_answer={"answer": "no", "not_present": False}),
        row(q3, CYPHER, False, trace={"retrieval": {"n_rows": 0}}),
        row(q4, CYPHER, False, outcome="RETRIEVAL_ERROR", final_answer=None),
    ]


def _agent_rows() -> list[dict[str, Any]]:
    """The agent answers every question; it is right on q1 and q3 only."""
    q1, q2, q3, q4 = FAMILIES
    return [
        row(q1, AGENT, True),
        row(q2, AGENT, False),
        row(q3, AGENT, True),
        row(q4, AGENT, False),
    ]


def _write(root: Path) -> tuple[Path, Path]:
    write_questions(root / "questions", CORPUS, FAMILIES)
    write_ingest(root / "corpora", CORPUS, n_sheets=1, n_nodes=10)
    runs, questions = root / "runs", root / "questions"
    cyp = write_run(runs, questions, CORPUS, "Q7-CYP", CYPHER, luna_pin("low"), _cypher_rows())
    agent = write_run(runs, questions, CORPUS, "Q7-AG", AGENT, luna_pin("high"), _agent_rows())
    return cyp, agent


def test_per_family_counts_and_who_answered(tmp_path: Path) -> None:
    cyp, agent = _write(tmp_path)
    report = load_dev_report(CORPUS, cyp, agent, tmp_path / "questions", 120.0)
    by_family = {r.family: r for r in report.rows}
    connected, flow = by_family["CONNECTED"], by_family["FLOW_PATH"]
    assert (connected.n, connected.cypher_correct, connected.agent_correct) == (2, 1, 1)
    assert connected.cascade_correct == 1 and connected.answered_by_cypher == 2
    assert (flow.cypher_correct, flow.agent_correct, flow.cascade_correct) == (0, 1, 1)
    assert flow.answered_by_agent == 2  # q3 and q4 escalate to the agent


def test_failures_say_expected_got_and_which_tier_answered(tmp_path: Path) -> None:
    cyp, agent = _write(tmp_path)
    report = load_dev_report(CORPUS, cyp, agent, tmp_path / "questions", 120.0)
    assert [f.question_id for f in report.failures] == [f"{CORPUS}:2", f"{CORPUS}:4"]
    wrong_cypher, wrong_agent = report.failures
    assert (wrong_cypher.expected, wrong_cypher.got) == ("yes", "no")
    assert wrong_cypher.answered_by == "cypher-luna" and not wrong_cypher.agent_correct
    assert wrong_agent.answered_by == "agent-luna" and not wrong_agent.cypher_correct
    assert wrong_agent.family == "FLOW_PATH"


def test_the_report_is_written_as_markdown_json_and_a_failure_list(tmp_path: Path) -> None:
    cyp, agent = _write(tmp_path)
    report = load_dev_report(CORPUS, cyp, agent, tmp_path / "questions", 120.0)
    paths = write_dev_report(report, tmp_path / "out")
    assert [p.name for p in paths] == ["dev_report.md", "dev_report.json", "failures.jsonl"]
    assert len((tmp_path / "out" / "failures.jsonl").read_text().splitlines()) == 2
    text = render_dev_markdown(report)
    assert "| CONNECTED | 2 |" in text and "ALL without LOOP_ACTUATED_VALVE" in text
    assert f"| {CORPUS}:2 | CONNECTED | yes | no | cypher-luna |" in text
