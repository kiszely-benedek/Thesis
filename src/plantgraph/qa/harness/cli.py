"""`python -m plantgraph.qa.harness` -- start, resume or replay a run.

**Paid calls are off unless `--allow-paid-calls` is typed.** Without it the
run reads only the LLM cache and stops at the first cache miss, whatever keys
are set in the environment (`qa-system.md` §6). A run is frozen
(`run_config.json`) before its first call; running the same `--run-id` again
resumes it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from plantgraph.llm.cache import DEFAULT_CACHE_PATH
from plantgraph.llm.models import CacheMiss, ContextWall, ModelPin
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256, read_git_state
from plantgraph.qa.harness.pool import MAX_CONCURRENCY
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import RunConfig

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_RUNS_ROOT = Path("data") / "runs"
_DEFAULT_CORPORA_ROOT = Path("data") / "corpora"
_DEFAULT_QUESTIONS_ROOT = Path("data") / "questions"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.harness", description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--experiment", required=True, help='e.g. "EXP-0002", or a tooling name')
    parser.add_argument("--reported", action="store_true", help="the numbers may be cited")
    parser.add_argument(
        "--corpus", action="append", required=True, metavar="ID:ROLE", help="ROLE is dev or test"
    )
    parser.add_argument("--strategy", action="append", required=True, help="e.g. context_rag")
    parser.add_argument(
        "--strategy-params-json",
        type=Path,
        help='JSON {"<strategy name>": {parameters}}; frozen in the run config',
    )
    parser.add_argument(
        "--no-primer",
        action="store_true",
        help="leave the P&ID reading primer out of the prompts (the ablation arm); "
        "the primer is on by default",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--pin-json", required=True, type=Path, help="a ModelPin as JSON")
    parser.add_argument("--wall-json", type=Path, help="a ContextWall as JSON (pilot output)")
    parser.add_argument("--corpora-root", type=Path, default=_DEFAULT_CORPORA_ROOT)
    parser.add_argument("--questions-root", type=Path, default=_DEFAULT_QUESTIONS_ROOT)
    parser.add_argument("--runs-root", type=Path, default=_DEFAULT_RUNS_ROOT)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument(
        "--allow-paid-calls", action="store_true", help="permit real, billed model calls"
    )
    parser.add_argument(
        "--cost-per-question-usd", type=float, help="the pilot's estimate, echoed before a paid run"
    )
    parser.add_argument(
        "--max-spend-usd",
        type=float,
        help="hard spend cap in USD; required with --allow-paid-calls, recorded in the run config",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        choices=range(1, MAX_CONCURRENCY + 1),
        metavar=f"1..{MAX_CONCURRENCY}",
        help="items answered at once; rows are still written in order. A paid run above 1 "
        "needs --cost-per-question-usd",
    )
    return parser.parse_args(argv)


def _split_corpus_arg(value: str) -> tuple[str, str]:
    corpus_id, separator, role = value.partition(":")
    if not separator or not corpus_id or role not in ("dev", "test"):
        raise SystemExit(f"error: expected --corpus ID:dev or ID:test, found {value!r}")
    return corpus_id, role


def _read_strategy_params(
    path: Path | None, strategy_names: list[str]
) -> dict[str, dict[str, Any]]:
    """One parameter dict per `--strategy`; `{}` for a strategy the file does not mention.

    Raises:
        SystemExit: the file is not a JSON object of objects, or names a strategy
            that was not asked for (a typo would otherwise be ignored silently).
    """
    given: object = {} if path is None else json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(given, dict) or not all(isinstance(v, dict) for v in given.values()):
        raise SystemExit(
            f"error: expected {path} to hold a JSON object of objects, found {given!r}"
        )
    unused = sorted(set(given) - set(strategy_names))
    if unused:
        raise SystemExit(f"error: expected params only for {strategy_names}, found {unused}")
    return {name: dict(given.get(name, {})) for name in strategy_names}


def _build_config(args: argparse.Namespace, corpus_ids: list[str]) -> RunConfig:
    commit, dirty = read_git_state(_REPO_ROOT)
    files = [questions_path(args.questions_root, corpus_id) for corpus_id in corpus_ids]
    wall = None
    if args.wall_json is not None:
        wall = ContextWall.model_validate_json(args.wall_json.read_text(encoding="utf-8"))
    return RunConfig(
        run_id=args.run_id,
        experiment=args.experiment,
        reported=args.reported,
        corpora=corpus_ids,
        strategies=_read_strategy_params(args.strategy_params_json, args.strategy),
        answer_pin=ModelPin.model_validate_json(args.pin_json.read_text(encoding="utf-8")),
        prompt_hashes=prompt_hashes(),
        question_set_sha256=question_set_sha256(files),
        primer=not args.no_primer,
        context_wall=wall,
        git_commit=commit,
        git_dirty=dirty,
        created_at=datetime.now(UTC),
        repeats=args.repeats,
        allow_paid_calls=args.allow_paid_calls,  # only ever from the flag, never the environment
        max_spend_usd=args.max_spend_usd,
    )


def main(argv: list[str] | None = None) -> None:
    """Parse argv, run the harness, print the summary as JSON."""
    args = _parse_args(argv)
    if args.allow_paid_calls and args.max_spend_usd is None:
        raise SystemExit("error: --allow-paid-calls needs --max-spend-usd (a hard spend cap)")
    if args.allow_paid_calls and args.concurrency > 1 and args.cost_per_question_usd is None:
        raise SystemExit(
            "error: --concurrency > 1 on a paid run needs --cost-per-question-usd "
            "(the spend cap reserves that much for each item in flight)"
        )
    corpus_roles = dict(_split_corpus_arg(value) for value in args.corpus)
    config = _build_config(args, list(corpus_roles))
    try:
        summary = run_harness(
            config=config,
            corpus_roles=corpus_roles,
            corpora_root=args.corpora_root,
            questions_root=args.questions_root,
            runs_root=args.runs_root,
            cache_path=args.cache_path,
            cost_per_question_usd=args.cost_per_question_usd,
            concurrency=args.concurrency,
        )
    except CacheMiss as error:
        print(f"stopped at a cache miss: {error}", file=sys.stderr)
        print(
            "rerun with the same --run-id to resume; fill the cache with --allow-paid-calls "
            "only after approving the spend",
            file=sys.stderr,
        )
        raise SystemExit(2) from error
    print(summary.model_dump_json(indent=2))
    if summary.stopped_by_spend_cap:
        print("stopped by the spend cap; rerun with the same --run-id to resume", file=sys.stderr)
        raise SystemExit(3)
