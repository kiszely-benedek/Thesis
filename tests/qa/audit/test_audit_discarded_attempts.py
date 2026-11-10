"""Error attempts retried before a judge call succeeded are billed, so the ledger must hold them."""

from __future__ import annotations

from pathlib import Path

import pytest

from audit_fakes import make_question, make_result, make_run, make_subgraph
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.qa.audit.budget import SpendLedger
from plantgraph.qa.audit.call_log import discarded_attempts_usd, log_size
from plantgraph.qa.audit.judge import judge_pin
from plantgraph.qa.audit.models import AuditItem
from plantgraph.qa.audit.runner import RunContext, run_plan
from plantgraph.qa.audit.sources import source_rows
from plantgraph.qa.harness.clients import build_chat_client

_CORRECT = '{"verdict": "correct", "reference_ok": true, "reason": "counted"}'


def _one_row_context(
    tmp_path: Path, transport: FakeTransport, with_log: bool
) -> tuple[RunContext, list[AuditItem]]:
    question = make_question(0)
    run = make_run("run-a", [(question, make_result(question, correct=False))])
    client, _cache = build_chat_client(
        pin=judge_pin(),
        allow_paid_calls=True,
        cache_path=tmp_path / "cache.sqlite",
        calls_log_path=tmp_path / "calls.jsonl",
        http_client=transport.as_httpx_client(),
    )
    context = RunContext(
        runs={run.run_id: run},
        subgraphs={question.question_id: make_subgraph(question.question_id)},
        client=client,
        ledger=SpendLedger(tmp_path / "ledger.jsonl", 10.0),
        verdicts_path=tmp_path / "verdicts.jsonl",
        stage="audit",
        calls_log_path=tmp_path / "calls.jsonl" if with_log else None,
    )
    return context, [AuditItem(stratum="wrong", row=row) for row in source_rows(run)]


def _two_errors_then_a_reply() -> FakeTransport:
    broken = ScriptedReply(text="", finish_reason="error", cost_usd=0.003)
    good = ScriptedReply(text=_CORRECT, cost_usd=0.02)
    return FakeTransport(leading_replies=[broken, broken, good])


def test_discarded_error_attempts_before_a_success_are_booked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("plantgraph.llm.retry_loop.time.sleep", lambda _s: None)
    context, items = _one_row_context(tmp_path, _two_errors_then_a_reply(), with_log=True)

    summary = run_plan(items, context)

    assert summary.judged == 1
    assert context.ledger.spent_usd() == pytest.approx(0.02 + 2 * 0.003)


def test_without_the_log_only_the_final_reply_is_booked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("plantgraph.llm.retry_loop.time.sleep", lambda _s: None)
    context, items = _one_row_context(tmp_path, _two_errors_then_a_reply(), with_log=False)

    run_plan(items, context)

    assert context.ledger.spent_usd() == pytest.approx(0.02)  # the gap this module closes


def test_only_lines_after_the_mark_count(tmp_path: Path) -> None:
    missing = tmp_path / "none.jsonl"
    assert log_size(missing) == 0 and discarded_attempts_usd(missing, 0) == 0.0
