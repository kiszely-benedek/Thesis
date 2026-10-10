"""The `ask` sub-command: answer one question through the live cascade and print the result."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from plantgraph.qa.cascade.live_build import OpenedCascade, open_live_cascade
from plantgraph.qa.cascade.live_models import FreeTextQuestion, NeedsPaidCall
from plantgraph.qa.cascade.live_render import render_live_answer, render_needs_paid_call
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policy
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.models import AnswerType
from plantgraph.qa.strategies.base import AskedQuestion

#: Builds the cascade for parsed `ask` arguments; tests pass one over fakes.
OpenCascade = Callable[[argparse.Namespace], OpenedCascade]

_DEMO_DIR = Path("data") / "runs" / "cv1" / "demo"
_DEFAULT_CUTOFF_S = 120.0
_DEFAULT_SESSION_CAP_USD = 2.0


def add_ask_arguments(command: argparse.ArgumentParser) -> None:
    """The options of `ask`: the question, the policy and its tier runs, the cache, paid mode."""
    command.add_argument("text", nargs="?", help="a free-text question (or use --question-id)")
    command.add_argument(
        "--question-id", help="ask this benchmark question (needs --questions-root)"
    )
    command.add_argument("--questions-root", type=Path, help="holds <corpus>/questions.jsonl")
    command.add_argument(
        "--answer-type", choices=[t.value for t in AnswerType], default="FREE_TEXT"
    )
    command.add_argument("--corpus", required=True)
    command.add_argument("--policy", required=True, help="a shipped policy name, or a JSON path")
    command.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="TIER=RUN_DIR",
        help="the stored run that fixes the tier's pin, parameters and primer",
    )
    command.add_argument("--corpora-root", type=Path, default=Path("data") / "corpora")
    command.add_argument("--cache-path", type=Path, default=_DEMO_DIR / "cache.sqlite")
    command.add_argument("--calls-log", type=Path, default=_DEMO_DIR / "calls.jsonl")
    command.add_argument("--cutoff-s", type=float, default=_DEFAULT_CUTOFF_S)
    command.add_argument(
        "--replay-only", action="store_true", help="turn paid calls off: cached answers only"
    )
    command.add_argument(
        "--session-cap-usd",
        type=float,
        default=_DEFAULT_SESSION_CAP_USD,
        help="hard cap on the paid calls of this run (USD)",
    )


def ask_command(args: argparse.Namespace, open_cascade: OpenCascade) -> None:
    """Ask, print the answer and the tier table; exit 2 on a cache miss with --replay-only."""
    asked = _asked_question(args)
    with open_cascade(args) as opened:
        result = opened.cascade.ask(asked)
    if isinstance(result, NeedsPaidCall):
        print(render_needs_paid_call(result), file=sys.stderr)
        raise SystemExit(2)
    print(render_live_answer(result))


def open_for_ask(args: argparse.Namespace) -> OpenedCascade:
    """Load the corpus and open the cascade the arguments describe (live unless `--replay-only`)."""
    artifacts = load_corpus_artifacts(args.corpus, args.corpora_root / args.corpus / "ingest.json")
    return open_live_cascade(
        corpus_id=args.corpus,
        policy=_load_policy(args.policy),
        view=NetworkxGraphView(args.corpus, artifacts.localized_sheets, artifacts.resolution),
        load_plan=artifacts.load_plan,
        tier_run_dirs=_tier_run_dirs(args.run),
        cache_path=args.cache_path,
        calls_log_path=args.calls_log,
        allow_paid_calls=not args.replay_only,
        cutoff_s=args.cutoff_s,
        guard=SpendGuard(None if args.replay_only else args.session_cap_usd),
    )


def _asked_question(args: argparse.Namespace) -> AskedQuestion:
    if args.question_id is None:
        if not args.text:
            raise SystemExit("error: expected a question text or --question-id, found neither")
        return FreeTextQuestion.from_text(args.text, AnswerType(args.answer_type))
    if args.questions_root is None:
        raise SystemExit("error: --question-id needs --questions-root")
    questions = load_questions(questions_path(args.questions_root, args.corpus), args.corpus)
    for question in questions:
        if question.question_id == args.question_id:
            return question
    raise SystemExit(f"error: expected {args.question_id!r} in the {args.corpus} questions")


def _load_policy(value: str) -> CascadePolicy:
    path = Path(value) if Path(value).exists() else POLICIES_DIR / f"{value}.json"
    if not path.exists():
        raise SystemExit(f"error: expected a policy file or a shipped policy name, found {value!r}")
    return load_policy(path)


def _tier_run_dirs(values: list[str]) -> dict[str, Path]:
    dirs: dict[str, Path] = {}
    for value in values:
        tier, separator, run_dir = value.partition("=")
        if not separator or not tier:
            raise SystemExit(f"error: expected --run TIER=RUN_DIR, found {value!r}")
        dirs[tier] = Path(run_dir)
    return dirs
