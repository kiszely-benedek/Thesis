"""The audit runner under the ledger (fake transport only), the report, and the CLI (F14)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from audit_fakes import CORPUS, make_question, make_result, make_run, make_subgraph
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.qa.audit import cli
from plantgraph.qa.audit import judge as judge_module
from plantgraph.qa.audit.budget import SpendLedger, worst_case_call_usd
from plantgraph.qa.audit.excerpt import SubgraphFile
from plantgraph.qa.audit.judge import judge_pin
from plantgraph.qa.audit.models import AuditItem, AuditRecord, JudgeReply, JudgeVerdict, Stratum
from plantgraph.qa.audit.report import (
    AMBIGUOUS_QUESTION,
    SCORER_RIGHT_JUDGE_INCORRECT,
    SYSTEM_RIGHT_SCORER_WRONG,
    cohens_kappa,
    disagreement_class,
    disagreement_sheet,
    g2_verdict,
    group_stats,
    render_report,
)
from plantgraph.qa.audit.runner import RunContext, read_records, run_plan
from plantgraph.qa.audit.sources import LoadedRun, source_rows
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.models import Outcome, QuestionResult, RunConfig

_CORRECT = '{"verdict": "correct", "reference_ok": true, "reason": "counted the valves"}'


def _run_and_items(n_rows: int = 4) -> tuple[LoadedRun, list[AuditItem]]:
    pairs = []
    for number in range(n_rows):
        question = make_question(number)
        pairs.append((question, make_result(question, correct=number % 2 == 0)))
    run = make_run("run-a", pairs)
    items = [AuditItem(stratum="wrong", row=row) for row in source_rows(run)]
    return run, items


def _context(
    tmp_path: Path,
    run: LoadedRun,
    transport: FakeTransport,
    *,
    paid: bool = True,
    cap_usd: float = 10.0,
    stage_cap_usd: float | None = None,
) -> RunContext:
    client, _cache = build_chat_client(
        pin=judge_pin(),
        allow_paid_calls=paid,
        cache_path=tmp_path / "cache.sqlite",
        calls_log_path=tmp_path / "calls.jsonl",
        http_client=transport.as_httpx_client(),
    )
    return RunContext(
        runs={run.run_id: run},
        subgraphs={qid: make_subgraph(qid) for qid in run.questions},
        client=client,
        ledger=SpendLedger(tmp_path / "ledger.jsonl", cap_usd),
        verdicts_path=tmp_path / "verdicts.jsonl",
        stage="audit",
        stage_cap_usd=stage_cap_usd,
    )


def _transport(text: str = _CORRECT, cost: float = 0.02) -> FakeTransport:
    return FakeTransport(default_reply=ScriptedReply(text=text, cost_usd=cost))


# --- runner ----------------------------------------------------------------------------------


def test_the_runner_judges_every_row_books_the_cost_and_sends_no_verdict(tmp_path: Path) -> None:
    run, items = _run_and_items()
    transport = _transport()
    context = _context(tmp_path, run, transport)

    summary = run_plan(items, context)

    assert summary.judged == 4 and not summary.failed
    assert len(transport.requests) == 4
    assert context.ledger.spent_usd() == pytest.approx(0.08)
    assert len(read_records(context.verdicts_path)) == 4
    bodies = [
        json.loads(request.content)["messages"][0]["content"] for request in transport.requests
    ]
    assert all("scorer" not in body.lower() and "ANSWERED" not in body for body in bodies)


def test_a_second_run_over_the_same_plan_skips_the_judged_rows(tmp_path: Path) -> None:
    run, items = _run_and_items()
    transport = _transport()
    run_plan(items, _context(tmp_path, run, transport))

    again = run_plan(items, _context(tmp_path, run, transport))

    assert again.already_done == 4 and again.judged == 0
    assert len(transport.requests) == 4


def _prompt_chars(tmp_path: Path) -> int:
    """Length of the (equal-sized) toy prompts, read from a dry pass in its own folder."""
    run, items = _run_and_items(1)
    probe = tmp_path / "probe"
    probe.mkdir()
    summary = run_plan(items, _context(probe, run, _transport(), paid=False))
    return summary.prompt_chars[0]


def test_the_hard_cap_stops_the_run_before_a_call_that_could_pass_it(tmp_path: Path) -> None:
    run, items = _run_and_items()
    transport = _transport()
    # room for one call's worst case, but not for a second after 0.02 was spent
    worst = worst_case_call_usd(_prompt_chars(tmp_path))
    context = _context(tmp_path, run, transport, cap_usd=worst + 0.01)

    summary = run_plan(items, context)

    assert summary.judged == 1 and summary.stopped_by_cap
    assert context.ledger.spent_usd() <= context.ledger.cap_usd


def test_the_worst_case_grows_with_the_prompt_length() -> None:
    # 27,584 chars is the longest pilot prompt measured; the old fixed $0.042 was too low for it
    assert worst_case_call_usd(27_584) > 0.042
    assert worst_case_call_usd(27_584) == pytest.approx(27_584 / 2.19 * 2e-6 + 2_048 * 1e-5)


def test_the_cap_check_uses_this_prompts_worst_case(tmp_path: Path) -> None:
    run, items = _run_and_items(1)
    worst = worst_case_call_usd(_prompt_chars(tmp_path))
    context = _context(tmp_path, run, _transport(), cap_usd=worst - 0.001)

    summary = run_plan(items, context)

    assert summary.judged == 0 and summary.stopped_by_cap


def test_the_stage_cap_stops_the_pilot_before_the_shared_cap(tmp_path: Path) -> None:
    run, items = _run_and_items()
    context = _context(tmp_path, run, _transport(), stage_cap_usd=0.04)

    summary = run_plan(items, context)

    assert summary.judged == 1 and summary.stopped_by_cap


def test_a_failed_call_that_reported_usage_is_booked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("plantgraph.llm.retry_loop.time.sleep", lambda _s: None)
    run, items = _run_and_items(1)
    broken = FakeTransport(
        default_reply=ScriptedReply(text="", finish_reason="error", cost_usd=0.003)
    )
    context = _context(tmp_path, run, broken)

    summary = run_plan(items, context)

    assert summary.judged == 0 and len(summary.failed) == 1
    assert context.ledger.spent_usd() == pytest.approx(0.003 * len(broken.requests))


def test_a_revised_prompt_template_judges_the_rows_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, items = _run_and_items(2)
    transport = _transport()
    context = _context(tmp_path, run, transport)
    run_plan(items, context)
    revised = tmp_path / "revised_judge.txt"
    revised.write_text(
        judge_module.TEMPLATE_PATH.read_text(encoding="utf-8") + " Also state it briefly.",
        encoding="utf-8",
    )
    monkeypatch.setattr(judge_module, "TEMPLATE_PATH", revised)

    again = run_plan(items, context)

    assert again.judged == 2 and again.already_done == 0
    assert len(read_records(context.verdicts_path)) == 2  # the newer verdict replaces the older
    assert run_plan(items, context).already_done == 2


def test_without_the_paid_flag_nothing_is_sent_and_prompt_sizes_are_reported(
    tmp_path: Path,
) -> None:
    run, items = _run_and_items()
    transport = _transport()

    summary = run_plan(items, _context(tmp_path, run, transport, paid=False))

    assert summary.not_run == 4 and summary.judged == 0
    assert transport.requests == []
    assert len(summary.prompt_chars) == 4 and all(n > 1_500 for n in summary.prompt_chars)


def test_a_missing_excerpt_is_listed_and_a_malformed_reply_is_booked_but_unjudged(
    tmp_path: Path,
) -> None:
    run, items = _run_and_items(2)
    context = _context(tmp_path, run, _transport(text="not json"))
    without_excerpt = RunContext(
        **{**context.__dict__, "subgraphs": {items[0].row.question_id: make_subgraph("x")}}
    )

    summary = run_plan(items, without_excerpt)

    reasons = " | ".join(reason for _, reason in summary.failed)
    assert len(summary.failed) == 2
    assert "no plant excerpt" in reasons and "verdict/reference_ok/reason" in reasons
    assert summary.judged == 0 and context.ledger.spent_usd() == pytest.approx(0.02)


# --- report ----------------------------------------------------------------------------------


def _record(
    verdict: JudgeVerdict,
    *,
    scorer_correct: bool,
    stratum: Stratum = "right_min",
    number: int = 0,
) -> AuditRecord:
    question = make_question(number)
    result = make_result(question, correct=scorer_correct)
    row = source_rows(make_run("r", [(question, result)]))[0]
    return AuditRecord(
        item=AuditItem(stratum=stratum, row=row),
        reply=JudgeReply(verdict=verdict, reference_ok=True, reason="because"),
        prompt_chars=100,
        prompt_tokens=10,
        completion_tokens=5,
        paid_usd=0.01,
    )


def test_disagreement_classes() -> None:
    YES, NO, MAYBE = JudgeVerdict.CORRECT, JudgeVerdict.INCORRECT, JudgeVerdict.AMBIGUOUS_QUESTION
    assert disagreement_class(_record(YES, scorer_correct=True)) is None
    assert disagreement_class(_record(NO, scorer_correct=False)) is None
    assert disagreement_class(_record(YES, scorer_correct=False)) == SYSTEM_RIGHT_SCORER_WRONG
    assert disagreement_class(_record(NO, scorer_correct=True)) == SCORER_RIGHT_JUDGE_INCORRECT
    assert disagreement_class(_record(MAYBE, scorer_correct=True)) == AMBIGUOUS_QUESTION


def test_kappa_matches_a_hand_computed_table() -> None:
    YES, NO = JudgeVerdict.CORRECT, JudgeVerdict.INCORRECT
    # scorer-right: 40 judged correct, 10 incorrect; scorer-wrong: 5 judged correct, 45 incorrect
    records = (
        [_record(YES, scorer_correct=True, number=n) for n in range(40)]
        + [_record(NO, scorer_correct=True, number=n) for n in range(10)]
        + [_record(YES, scorer_correct=False, number=n) for n in range(5)]
        + [_record(NO, scorer_correct=False, number=n) for n in range(45)]
    )
    # observed 85/100; scorer yes 0.5, judge yes 0.45; expected 0.5*0.45 + 0.5*0.55 = 0.5
    assert cohens_kappa(records) == pytest.approx((0.85 - 0.5) / 0.5)
    assert group_stats(records).agreement == pytest.approx(0.85)


def test_kappa_is_undefined_with_one_label_only() -> None:
    assert cohens_kappa([_record(JudgeVerdict.CORRECT, scorer_correct=True)]) is None
    assert cohens_kappa([]) is None


def test_g2_passes_at_80_percent_on_both_groups_and_fails_below() -> None:
    YES, NO, MAYBE = JudgeVerdict.CORRECT, JudgeVerdict.INCORRECT, JudgeVerdict.AMBIGUOUS_QUESTION
    defects = [
        _record(YES, scorer_correct=False, stratum="pilot_defect_valves", number=n)
        for n in range(7)
    ]
    defects += [
        _record(MAYBE, scorer_correct=False, stratum="pilot_defect_parse", number=n)
        for n in range(1)
    ]
    defects += [
        _record(NO, scorer_correct=False, stratum="pilot_defect_parse", number=n) for n in range(2)
    ]
    controls = [
        _record(YES, scorer_correct=True, stratum="pilot_control", number=n) for n in range(8)
    ]
    controls += [
        _record(NO, scorer_correct=True, stratum="pilot_control", number=n) for n in range(2)
    ]

    verdict = g2_verdict(defects + controls)

    assert (verdict.n_defect_found, verdict.n_defect) == (8, 10) and verdict.passed
    assert not g2_verdict(defects[:-1] + [defects[-1]] * 2 + controls).passed  # 8/11 < 80 %
    assert not g2_verdict(defects).passed  # no controls at all


def test_the_report_and_sheet_name_every_group_and_disagreement() -> None:
    records = [
        _record(JudgeVerdict.CORRECT, scorer_correct=True, stratum="right_min", number=1),
        _record(JudgeVerdict.CORRECT, scorer_correct=False, stratum="wrong", number=2),
        _record(JudgeVerdict.INCORRECT, scorer_correct=False, stratum="wrong", number=3),
    ]

    report = render_report(records)
    sheet = disagreement_sheet(records)

    assert "| right sample | 1 | 100.0 % |" in report
    assert "| wrong rows | 2 | 50.0 % |" in report
    assert f"| {SYSTEM_RIGHT_SCORER_WRONG} | LOOKUP_TYPE | 1 |" in report
    assert sheet.count("\n") == 2 and "counted" not in sheet and "because" in sheet


# --- command line ----------------------------------------------------------------------------


def _write_run_on_disk(root: Path) -> tuple[Path, Path]:
    questions = [make_question(n) for n in range(3)]
    qdir = root / "questions" / CORPUS
    qdir.mkdir(parents=True)
    (qdir / "questions.jsonl").write_text(
        "".join(q.model_dump_json() + "\n" for q in questions), encoding="utf-8"
    )
    run_dir = root / "runs" / "run-a"
    run_dir.mkdir(parents=True)
    config = RunConfig(
        run_id="run-a",
        experiment="TOOLING",
        reported=False,
        corpora=[CORPUS],
        strategies={"agent": {}},
        answer_pin=judge_pin(),
        question_set_sha256="0" * 64,
        git_commit="0" * 40,
        git_dirty=False,
        created_at=datetime(2026, 11, 8),
    )
    (run_dir / "run_config.json").write_text(config.model_dump_json(), encoding="utf-8")
    rows: list[QuestionResult] = [
        make_result(q, correct=n == 0, outcome=Outcome.ANSWERED) for n, q in enumerate(questions)
    ]
    lines = "".join(r.model_copy(update={"run_id": "run-a"}).model_dump_json() + "\n" for r in rows)
    (run_dir / "answers.jsonl").write_text(lines, encoding="utf-8")
    return run_dir, root / "questions"


def test_judge_then_report_on_a_stored_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir, questions_root = _write_run_on_disk(tmp_path)
    plan = tmp_path / "plan.json"
    items = [
        AuditItem(stratum="wrong", row=row) for row in source_rows(_loaded(run_dir, questions_root))
    ]
    plan.write_text(cli.ItemsFile(items=items).model_dump_json(), encoding="utf-8")
    subgraphs = tmp_path / "subgraphs.json"
    subgraphs.write_text(
        SubgraphFile(subgraphs=[make_subgraph(i.row.question_id) for i in items]).model_dump_json(),
        encoding="utf-8",
    )
    common = ["--run", str(run_dir), "--questions-root", str(questions_root)]

    status = cli.main(
        ["judge", *common, "--plan", str(plan), "--subgraphs", str(subgraphs)]
        + ["--out-dir", str(tmp_path / "out"), "--ledger", str(tmp_path / "ledger.jsonl")]
        + ["--stage", "pilot"]
    )  # no --allow-paid-calls: a free dry run, nothing is judged
    dry = capsys.readouterr().out

    assert status == 0 and "not run 3" in dry and "prompt chars: median" in dry
    assert "judge prompt sha256:" in dry


def _loaded(run_dir: Path, questions_root: Path) -> LoadedRun:
    from plantgraph.qa.audit.sources import load_run

    return load_run(run_dir, questions_root)


def test_the_report_command_writes_the_report_and_the_sheet(tmp_path: Path) -> None:
    record = _record(JudgeVerdict.CORRECT, scorer_correct=False, stratum="wrong")
    verdicts = tmp_path / "verdicts.jsonl"
    verdicts.write_text(record.model_dump_json() + "\n", encoding="utf-8")

    status = cli.main(
        ["report", "--verdicts", str(verdicts), "--out", str(tmp_path / "r.md")]
        + ["--sheet", str(tmp_path / "sheet.csv")]
    )

    assert status == 0
    assert "Scorer audit report" in (tmp_path / "r.md").read_text(encoding="utf-8")
    assert SYSTEM_RIGHT_SCORER_WRONG in (tmp_path / "sheet.csv").read_text(encoding="utf-8")
