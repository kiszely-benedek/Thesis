"""`python -m plantgraph.qa.audit` sub-commands: pilot-set, select, judge, report.

Only `judge` can spend money, and only with `--allow-paid-calls`; without it the client is
cache-only, so a run prints the prompt sizes and how many rows would be paid calls.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from pydantic import BaseModel

from plantgraph.qa.audit.budget import (
    HARD_CAP_USD,
    PILOT_CAP_USD,
    SpendLedger,
    sizing_cost_per_call,
)
from plantgraph.qa.audit.excerpt import QuestionSubgraph, SubgraphFile
from plantgraph.qa.audit.judge import judge_pin, template_sha256
from plantgraph.qa.audit.models import AuditItem, SourceRow
from plantgraph.qa.audit.pilot import build_pilot_set, parse_failure_candidates
from plantgraph.qa.audit.report import disagreement_sheet, render_report
from plantgraph.qa.audit.runner import RunContext, RunSummary, read_records, run_plan
from plantgraph.qa.audit.select import AuditPlan, select_audit
from plantgraph.qa.audit.sources import LoadedRun, load_run, source_rows
from plantgraph.qa.harness.clients import build_chat_client

#: Seed of the right-sample draw and of every stratified cut; registered in the pre-registration.
DEFAULT_SEED = 20261108


class ItemsFile(BaseModel):
    """The part of a plan file `judge` needs; an `AuditPlan` file and a pilot file both fit."""

    items: list[AuditItem]


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run", action="append", type=Path, required=True, help="a run directory")
    parser.add_argument("--questions-root", type=Path, required=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.audit", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    pilot = commands.add_parser(
        "pilot-set", help="build the G2 pilot set: every known defect row plus 20 controls (free)"
    )
    _add_run_arguments(pilot)
    pilot.add_argument("--valves-ids", type=Path, required=True, help="question ids, one a line")
    pilot.add_argument("--seed", type=int, default=DEFAULT_SEED)
    pilot.add_argument("--out", type=Path, required=True)

    select = commands.add_parser("select", help="build the audit plan within the budget (free)")
    _add_run_arguments(select)
    select.add_argument("--contextrag-run", action="append", type=Path, default=[])
    select.add_argument("--ledger", type=Path, required=True)
    select.add_argument("--cap-usd", type=float, default=HARD_CAP_USD, help="hard cap of the audit")
    select.add_argument("--call-usd", type=float, help="default: pilot mean cost x safety factor")
    select.add_argument("--seed", type=int, default=DEFAULT_SEED)
    select.add_argument("--out", type=Path, required=True)

    judge = commands.add_parser("judge", help="run a plan through the judge")
    _add_run_arguments(judge)
    judge.add_argument("--plan", type=Path, required=True)
    judge.add_argument("--subgraphs", action="append", type=Path, required=True)
    judge.add_argument("--out-dir", type=Path, required=True)
    judge.add_argument("--ledger", type=Path, required=True)
    judge.add_argument("--cap-usd", type=float, default=HARD_CAP_USD, help="hard cap of the audit")
    judge.add_argument("--stage", choices=["pilot", "audit"], required=True)
    judge.add_argument("--allow-paid-calls", action="store_true")

    report = commands.add_parser("report", help="agreement, kappa, disagreements (free)")
    report.add_argument("--verdicts", type=Path, required=True)
    report.add_argument("--plan", type=Path)
    report.add_argument("--out", type=Path, required=True)
    report.add_argument("--sheet", type=Path, required=True, help="disagreement CSV")
    return parser.parse_args(argv)


def _load_runs(run_dirs: list[Path], questions_root: Path) -> dict[str, LoadedRun]:
    runs: dict[str, LoadedRun] = {}
    for run_dir in run_dirs:
        run = load_run(run_dir, questions_root)
        if run.run_id in runs:
            raise ValueError(f"expected distinct run ids, found {run.run_id!r} twice")
        runs[run.run_id] = run
    return runs


def _pool(runs: dict[str, LoadedRun]) -> list[SourceRow]:
    return [row for run in runs.values() for row in source_rows(run)]


def _pilot_command(args: argparse.Namespace) -> int:
    runs = _load_runs(args.run, args.questions_root)
    parse_rows = [row for run in runs.values() for row in parse_failure_candidates(run)]
    valves_ids = set(args.valves_ids.read_text(encoding="utf-8").split())
    items = build_pilot_set(_pool(runs), parse_rows, valves_ids, args.seed)
    args.out.write_text(ItemsFile(items=items).model_dump_json(indent=1), encoding="utf-8")
    print(f"pilot set: {len(items)} rows -> {args.out}")
    return 0


def _select_command(args: argparse.Namespace) -> int:
    ledger = SpendLedger(args.ledger, args.cap_usd)
    call_usd = args.call_usd or sizing_cost_per_call(ledger.measured_cost_per_call("pilot"))
    runs = _load_runs(args.run, args.questions_root)
    contextrag = _load_runs(args.contextrag_run, args.questions_root) if args.contextrag_run else {}
    plan = select_audit(
        _pool(runs),
        _pool(contextrag),
        seed=args.seed,
        call_usd=call_usd,
        remaining_usd=ledger.remaining_usd(),
    )
    args.out.write_text(plan.model_dump_json(indent=1), encoding="utf-8")
    print(f"audit plan: {len(plan.items)} rows, about {plan.estimated_usd:.2f} USD -> {args.out}")
    return 0


def _load_subgraphs(paths: list[Path]) -> dict[str, QuestionSubgraph]:
    subgraphs: dict[str, QuestionSubgraph] = {}
    for path in paths:
        parsed = SubgraphFile.model_validate_json(path.read_text(encoding="utf-8"))
        subgraphs.update({sub.question_id: sub for sub in parsed.subgraphs})
    return subgraphs


def _print_summary(summary: RunSummary, ledger: SpendLedger) -> None:
    print(
        f"judged {summary.judged}, already done {summary.already_done}, not run {summary.not_run}"
    )
    print(f"failed {len(summary.failed)}; stopped by cap: {summary.stopped_by_cap}")
    for key, reason in summary.failed:
        print(f"  FAILED {key}: {reason}")
    if summary.prompt_chars:
        median = statistics.median(summary.prompt_chars)
        print(f"prompt chars: median {median:.0f}, max {max(summary.prompt_chars)}")
    print(f"spent so far: {ledger.spent_usd():.4f} of {ledger.cap_usd:.2f} USD")


def _judge_command(args: argparse.Namespace) -> int:
    items = ItemsFile.model_validate_json(args.plan.read_text(encoding="utf-8")).items
    args.out_dir.mkdir(parents=True, exist_ok=True)
    client, cache = build_chat_client(
        pin=judge_pin(),
        allow_paid_calls=args.allow_paid_calls,
        cache_path=args.out_dir / "cache.sqlite",
        calls_log_path=args.out_dir / "calls.jsonl",
    )
    ledger = SpendLedger(args.ledger, args.cap_usd)
    context = RunContext(
        runs=_load_runs(args.run, args.questions_root),
        subgraphs=_load_subgraphs(args.subgraphs),
        client=client,
        ledger=ledger,
        verdicts_path=args.out_dir / "verdicts.jsonl",
        stage=args.stage,
        stage_cap_usd=PILOT_CAP_USD if args.stage == "pilot" else None,
        calls_log_path=args.out_dir / "calls.jsonl",
    )
    try:
        summary = run_plan(items, context)
    finally:
        cache.close()
    print(f"judge prompt sha256: {template_sha256()}")
    _print_summary(summary, ledger)
    return 0


def _report_command(args: argparse.Namespace) -> int:
    records = read_records(args.verdicts)
    plan = None
    if args.plan is not None:
        plan = AuditPlan.model_validate_json(args.plan.read_text(encoding="utf-8"))
    args.out.write_text(render_report(records, plan), encoding="utf-8")
    args.sheet.write_text(disagreement_sheet(records), encoding="utf-8")
    print(f"report -> {args.out}; disagreement sheet -> {args.sheet}")
    return 0


_COMMANDS = {
    "pilot-set": _pilot_command,
    "select": _select_command,
    "judge": _judge_command,
    "report": _report_command,
}


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the exit status."""
    args = _parse_args(argv)
    return _COMMANDS[args.command](args)
