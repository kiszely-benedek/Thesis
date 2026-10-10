"""Cascade v2: V2/V3 verdicts, the shipped v2 policies on toy runs, TIMED_OUT cost, diagnostics."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import plantgraph.qa.cascade as cascade_package
from cascade_toy import (
    CORPUS,
    CYPHER,
    NEED,
    ToyRun,
    cypher_rows,
    need_rows,
    pin,
    row,
    write_questions,
    write_run,
)
from plantgraph.llm.models import CallRecord, ChatResponse
from plantgraph.qa.cascade.diagnostics import policy_diagnostics
from plantgraph.qa.cascade.evaluate import evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, find_gaps, join_corpus
from plantgraph.qa.cascade.labels import labels_from_run_dirs
from plantgraph.qa.cascade.late_charges import late_charge_check
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, decide_all, load_policy
from plantgraph.qa.cascade.report import build_report
from plantgraph.qa.cascade.report_render import render_markdown
from plantgraph.qa.cascade.signals import ABANDONED_CALL_COST_USD
from plantgraph.qa.models import Question
from plantgraph.qa.need.labels import NeedLabel

AGENT = "graph_agent_low_steps"


# --- toy runs: the shipped v2 policies ---


def _toy_policy(name: str) -> CascadePolicy:
    """A shipped v2 policy with the toy pins in place of the real GLM ones."""
    shipped = load_policy(POLICIES_DIR / f"{name}.json")
    toy_pins = {"cypher-low": pin("low").pin_hash(), "agent-low-steps": pin("default").pin_hash()}
    tiers = tuple(t.model_copy(update={"pin_sha256": toy_pins[t.name]}) for t in shipped.tiers)
    return shipped.model_copy(update={"tiers": tiers})


def _step(tool: str | None, keys: list[str]) -> dict[str, Any]:
    return {"index": 1, "tool": tool, "touched_keys": keys}


def _agent_trace(stop_reason: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {"retrieval": {"stop_reason": stop_reason, "agent_steps": steps}}


def _agent_rows() -> list[dict[str, Any]]:
    """q2 timed out (2 abandoned calls); q3 answered with no tool call; q4 touched nothing."""
    usage = {"n_calls": 1, "prompt_tokens": 9, "completion_tokens": 9, "cost_usd": 0.004}
    timed_out = row(
        "T1:q2",
        AGENT,
        outcome="TIMED_OUT",
        final_answer=None,
        correct=False,
        cost_usd=None,
        latency_s=10.0,
        trace={"timed_out": "deadline"},
        retrieval_usage={**usage, "llm_latency_s": 50.0, "n_abandoned": 2},
    )
    no_call = row(
        "T1:q3",
        AGENT,
        final_answer={"answer": "no", "not_present": False},
        trace=_agent_trace("done", [_step(None, [])]),
        retrieval_usage=usage,
    )
    no_item = row(
        "T1:q4",
        AGENT,
        correct=False,
        trace=_agent_trace("prompt_budget", [_step("path", [])]),
        retrieval_usage=usage,
    )
    return [timed_out, no_call, no_item]


def _toy_join(tmp_path: Path, name: str, **extra: Any) -> JoinedCorpus:
    questions_root = write_questions(tmp_path / "questions")
    runs = tmp_path / "runs"
    cypher = write_run(runs, questions_root, ToyRun("c", CYPHER, "low", cypher_rows()))
    agent = write_run(runs, questions_root, ToyRun("a", AGENT, "default", _agent_rows()))
    sources = {"cypher-low": TierSource(cypher), "agent-low-steps": TierSource(agent)}
    return join_corpus(_toy_policy(name), sources, CORPUS, questions_root, **extra)


def test_shipped_v2_policies_have_the_agreed_shape() -> None:
    v2 = load_policy(POLICIES_DIR / "cascade_v2.json")
    iso = load_policy(POLICIES_DIR / "cascade_v2_iso.json")
    always_g = load_policy(POLICIES_DIR / "always_g.json")

    assert [t.strategy for t in v2.tiers] == ["cypher_rag_plant", AGENT]
    assert iso.tiers == v2.tiers
    assert iso.start_tier_by_label == {NeedLabel.UPSTREAM_TO_FIRST_VALVE: 1}
    assert [t.strategy for t in always_g.tiers] == [AGENT]
    assert v2.fallback_to_first_answer


def test_cascade_v2_walks_the_toy_runs_and_a_timed_out_tier_falls_back(tmp_path: Path) -> None:
    joined = _toy_join(tmp_path, "cascade_v2")

    decisions = {
        d.question_id: d
        for d in decide_all(joined.policy, joined.question_ids, joined.need_labels, joined.signals)
    }

    assert decisions["T1:q1"].tiers_tried == ("cypher-low",)
    # q2: empty Cypher result -> agent TIMED_OUT -> the Cypher answer is the fallback
    assert decisions["T1:q2"].tiers_tried == ("cypher-low", "agent-low-steps")
    assert decisions["T1:q2"].answered_by == "cypher-low"
    assert decisions["T1:q3"].answered_by == "agent-low-steps"


def test_timed_out_row_is_charged_for_its_abandoned_calls(tmp_path: Path) -> None:
    joined = _toy_join(tmp_path, "cascade_v2")

    agent_signals = joined.signals["agent-low-steps"]["T1:q2"]

    # recorded query cost 0.004 + two abandoned calls at the upper bound
    assert agent_signals.cost_usd == pytest.approx(0.004 + 2 * ABANDONED_CALL_COST_USD)
    assert agent_signals.latency_s == pytest.approx(60.0)  # 10 s final share + 50 s of calls


def test_always_g_reports_the_questions_the_tier_has_no_row_for(tmp_path: Path) -> None:
    joined = _toy_join(tmp_path, "always_g")

    assert find_gaps(joined) == {"agent-low-steps": ["T1:q1"]}


def test_iso_policy_needs_a_label_and_borrows_one_from_another_run(tmp_path: Path) -> None:
    unlabelled = _toy_join(tmp_path / "a", "cascade_v2_iso")
    with pytest.raises(ValueError, match="need label"):
        decide_all(unlabelled.policy, unlabelled.question_ids, {}, unlabelled.signals)
    questions_root = write_questions(tmp_path / "q2")
    need_dir = write_run(tmp_path / "r2", questions_root, ToyRun("n", NEED, "default", need_rows()))

    labels = labels_from_run_dirs([need_dir])
    joined = _toy_join(tmp_path / "b", "cascade_v2_iso", known_labels=labels)

    assert joined.need_labels["T1:q3"] is NeedLabel.UPSTREAM_ALL
    assert evaluate_policy(joined).summary.policy == "cascade_v2_iso"


# --- diagnostics ---


def _questions_with_gold_no() -> dict[str, Question]:
    questions = {}
    for number in range(1, 5):
        question_id = f"T1:q{number}"
        questions[question_id] = Question.model_validate(
            {
                "question_id": question_id,
                "corpus_id": CORPUS,
                "family": "CONNECTED",
                "template_id": "CONNECTED",
                "template_version": "1",
                "text": "toy",
                "answer_type": "BOOLEAN",
                "answerable": True,
                "reference": "yes" if number == 4 else "no",
                "generator_seed": 1,
            }
        )
    return questions


def test_stop_reasons_and_tool_use_are_counted_over_the_tried_questions(tmp_path: Path) -> None:
    joined = _toy_join(tmp_path, "cascade_v2")

    result = policy_diagnostics(joined, evaluate_policy(joined), _questions_with_gold_no())

    assert result.agent is not None
    assert result.agent.n_tried == 3
    assert result.agent.stop_reasons == {"timed_out": 1, "done": 1, "prompt_budget": 1}
    assert (
        result.agent.answered_without_tool_call.total,
        result.agent.answered_without_tool_call.correct,
    ) == (1, 1)
    assert result.agent.answered_touching_no_item.total == 2


def test_made_up_yes_counts_gold_no_questions_answered_yes(tmp_path: Path) -> None:
    joined = _toy_join(tmp_path, "cascade_v2")

    result = policy_diagnostics(joined, evaluate_policy(joined), _questions_with_gold_no())

    # gold "no": q1 (cypher says yes), q2 (cypher fallback says yes), q3 (agent says no)
    assert result.boolean_no_questions == 3
    assert result.boolean_no_answered_yes == 2


def test_late_charges_are_checked_against_the_estimate(tmp_path: Path) -> None:
    questions_root = write_questions(tmp_path / "questions")
    run_dir = write_run(
        tmp_path / "runs", questions_root, ToyRun("a", AGENT, "default", _agent_rows())
    )
    reply = ChatResponse(
        text="{}",
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=0.0016,
        latency_s=90.0,
        provider_response_id=None,
        finish_reason="stop",
        from_cache=False,
        created_at=datetime(2026, 10, 10, tzinfo=UTC),
    )
    base: dict[str, Any] = {
        "run_id": "a",
        "question_id": "T1:q2",
        "strategy": AGENT,
        "purpose": "answer",
        "cache_key": "k",
        "pin_hash": "p",
        "prompt_sha256": "s",
    }
    lines = [
        CallRecord(**base, error_kind="timeout"),
        CallRecord(**base, error_kind="late_after_timeout", response=reply),
    ]
    (run_dir / "calls.jsonl").write_text(
        "".join(line.model_dump_json() + "\n" for line in lines), encoding="utf-8"
    )

    check = late_charge_check(run_dir, AGENT)

    assert check is not None
    assert (check.n_abandoned_in_rows, check.n_timeouts_logged, check.n_late_logged) == (2, 1, 1)
    assert check.late_cost_logged_usd == pytest.approx(0.0016)
    assert check.estimate_usd == pytest.approx(0.0212)
    assert late_charge_check(run_dir, CYPHER) is None


def test_report_carries_v2_v3_and_the_agent_tables(tmp_path: Path) -> None:
    questions_root = write_questions(tmp_path / "questions")
    runs = tmp_path / "runs"
    cypher = write_run(runs, questions_root, ToyRun("c", CYPHER, "low", cypher_rows()))
    agent = write_run(runs, questions_root, ToyRun("a", AGENT, "default", _agent_rows()))
    sources = {"cypher-low": TierSource(cypher), "agent-low-steps": TierSource(agent)}

    report = build_report([CORPUS], {CORPUS: sources}, questions_root, [_toy_policy("cascade_v2")])
    markdown = render_markdown(report)

    assert [v.rule for v in report.verdicts][-2:] == ["V2", "V3"]
    assert {v.status for v in report.verdicts[-2:]} == {"INCOMPLETE"}  # D100/D1000 not present
    assert "### Agent tier: stop reasons" in markdown
    assert "| cascade_v2 | agent-low-steps | 3 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |" in markdown


# --- the gold ban reaches the new decision-side code ---

GOLD_MODULES = ("plantgraph.qa.scoring", "plantgraph.qa.questions", "plantgraph.qa.harness.gold")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("module", ["policy", "signals", "accept", "labels", "report_verdicts_v2"])
def test_decision_side_modules_import_no_gold_code(module: str) -> None:
    path = Path(cascade_package.__file__).parent / f"{module}.py"

    banned = {m for m in _imports(path) if m.startswith(GOLD_MODULES)}

    assert not banned, f"{module}.py imports gold-side code: {sorted(banned)}"
