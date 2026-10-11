"""`python -m plantgraph.qa.exp0001 ex01 | ex01-review | ex01-tally` (design §11, row E-T1).

**Paid calls are off unless `--allow-paid-calls` is typed**, and then `--cap` is required. Without
the flag the run reads only the response caches and stops at the first cache miss.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plantgraph.llm.models import CacheMiss
from plantgraph.qa.chatpid_qa import DEFAULT_PATH
from plantgraph.qa.exp0001.ex01_arms import ARM_DEFINITIONS
from plantgraph.qa.exp0001.ex01_review import (
    KEY_NAME,
    VERDICTS_NAME,
    load_key,
    load_verdicts,
    render_tally,
    tally,
    write_review,
)
from plantgraph.qa.exp0001.ex01_runner import Ex01Settings, load_ex01_questions, run_ex01
from plantgraph.qa.exp0001.ex01_store import Ex01RunDir

_DATA = Path("data") / "runs" / "exp0001"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0001", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    _add_run_command(commands.add_parser("ex01", help="answer CP11-CP15 with the arms"))
    review = commands.add_parser("ex01-review", help="write the blind sheet and its key")
    review.add_argument("--questions", type=Path, default=DEFAULT_PATH)
    review.add_argument("--checklist", type=Path, default=_DATA / "inputs" / "ex01_checklist.json")
    _add_out_dir(review)
    tally_command = commands.add_parser("ex01-tally", help="count the verdicts per arm and repeat")
    tally_command.add_argument("--verdicts", type=Path, help=f"default: <out-dir>/{VERDICTS_NAME}")
    _add_out_dir(tally_command)
    return parser.parse_args(argv)


def _add_out_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", type=Path, default=_DATA / "ex01")


def _add_run_command(run: argparse.ArgumentParser) -> None:
    run.add_argument("--arms", default=",".join(ARM_DEFINITIONS), help="comma-separated arm names")
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--cap", type=float, help="hard spend cap in USD; needed with paid calls")
    run.add_argument("--allow-paid-calls", action="store_true", help="permit real, billed calls")
    run.add_argument("--cost-per-question-usd", type=float, default=0.01)
    run.add_argument("--run-id", default="E1-EX01")
    run.add_argument("--inputs-dir", type=Path, default=_DATA / "inputs")
    run.add_argument("--corpora-root", type=Path, default=_DATA / "corpora")
    run.add_argument("--questions", type=Path, default=DEFAULT_PATH)
    _add_out_dir(run)


def main(argv: list[str] | None = None) -> None:
    """Dispatch to the chosen command."""
    args = _parse_args(argv)
    if args.command == "ex01":
        _cmd_run(args)
    elif args.command == "ex01-review":
        _cmd_review(args)
    else:
        _cmd_tally(args)


def _cmd_run(args: argparse.Namespace) -> None:
    if args.allow_paid_calls and args.cap is None:
        raise SystemExit("error: --allow-paid-calls needs --cap (a hard spend cap in USD)")
    settings = Ex01Settings(
        out_dir=args.out_dir,
        inputs_dir=args.inputs_dir,
        corpora_root=args.corpora_root,
        qa_path=args.questions,
        arms=args.arms.split(","),
        repeats=args.repeats,
        cap_usd=args.cap,
        allow_paid_calls=args.allow_paid_calls,
        cost_per_question_usd=args.cost_per_question_usd,
        run_id=args.run_id,
    )
    try:
        summary = run_ex01(settings)
    except CacheMiss as error:
        print(f"stopped at a cache miss: {error}", file=sys.stderr)
        print(
            "fill the cache with --allow-paid-calls only after approving the spend", file=sys.stderr
        )
        raise SystemExit(2) from error
    print(summary.model_dump_json(indent=2))
    if summary.stopped_by_spend_cap:
        raise SystemExit(3)


def _cmd_review(args: argparse.Namespace) -> None:
    rows = Ex01RunDir(args.out_dir).read_rows()
    texts = {q.question_id: q.text for q in load_ex01_questions(args.questions)}
    sheet, key = write_review(args.out_dir, rows, args.checklist, texts)
    print(f"blind sheet for the reviewer: {sheet}\nhidden key (do not open): {key}")


def _cmd_tally(args: argparse.Namespace) -> None:
    verdicts_path = args.verdicts or args.out_dir / VERDICTS_NAME
    key = load_key(args.out_dir / KEY_NAME)
    print(render_tally(tally(key, load_verdicts(verdicts_path))))
