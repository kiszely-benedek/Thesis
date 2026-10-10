"""`python -m plantgraph.qa.cascade {join,needed,report,ask}` -- check, subset, report or ask."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from plantgraph.qa.cascade.evaluate import DEFAULT_CUTOFF_S, LatencyBound
from plantgraph.qa.cascade.join import (
    DEFAULT_QSUB_ROOT,
    JoinedCorpus,
    TierSource,
    find_gaps,
    join_corpus,
)
from plantgraph.qa.cascade.live_ask import (
    OpenCascade,
    add_ask_arguments,
    ask_command,
    open_for_ask,
)
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.needed import write_needed
from plantgraph.qa.cascade.policy import load_policy
from plantgraph.qa.cascade.report import build_report
from plantgraph.qa.cascade.report_render import write_report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.cascade", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("join", "needed"):
        command = commands.add_parser(name)
        command.add_argument("--policy", action="append", required=True, type=Path, help="JSON")
        command.add_argument("--corpus", required=True)
        command.add_argument("--questions-root", required=True, type=Path)
        command.add_argument(
            "--run",
            action="append",
            required=True,
            metavar="TIER=RUN_DIR[@QUESTIONS_ROOT]",
            help="a tier's stored run; the questions root defaults to --questions-root",
        )
    _add_report_arguments(commands.add_parser("report"))
    add_ask_arguments(commands.add_parser("ask"))
    commands.choices["needed"].add_argument("--tier", required=True)
    commands.choices["needed"].add_argument("--out-root", type=Path, default=DEFAULT_QSUB_ROOT)
    return parser.parse_args(argv)


def _add_report_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--policy", action="append", type=Path, help="JSON; default: all shipped")
    command.add_argument("--corpus", action="append", required=True, help="repeat for several")
    command.add_argument("--questions-root", required=True, type=Path)
    command.add_argument(
        "--cutoff-s",
        type=float,
        default=DEFAULT_CUTOFF_S,
        help="LB-3: answers later than this many seconds count as wrong, for every arm alike",
    )
    command.add_argument("--out", required=True, type=Path, help="directory for report.md/.json")
    command.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="CORPUS:TIER=RUN_DIR[@QUESTIONS_ROOT]",
        help="a tier's stored run on one corpus; the questions root defaults to --questions-root",
    )


def _parse_corpus_run(value: str) -> tuple[str, str, TierSource]:
    corpus, separator, rest = value.partition(":")
    if not separator or not corpus:
        raise SystemExit(f"error: expected --run CORPUS:TIER=RUN_DIR[@ROOT], found {value!r}")
    tier, source = _parse_run(rest)
    return corpus, tier, source


def _run_report(args: argparse.Namespace) -> None:
    sources: dict[str, dict[str, TierSource]] = {}
    for value in args.run:
        corpus, tier, source = _parse_corpus_run(value)
        sources.setdefault(corpus, {})[tier] = source
    policies = [load_policy(path) for path in args.policy] if args.policy else None
    report = build_report(
        args.corpus, sources, args.questions_root, policies, LatencyBound(cutoff_s=args.cutoff_s)
    )
    markdown, json_path = write_report(report, args.out)
    print(markdown.read_text(encoding="utf-8"))
    print(f"wrote {markdown} and {json_path}")


def _parse_run(value: str) -> tuple[str, TierSource]:
    name, separator, location = value.partition("=")
    if not separator or not name:
        raise SystemExit(f"error: expected --run TIER=RUN_DIR[@QUESTIONS_ROOT], found {value!r}")
    run_dir, _, root = location.partition("@")
    return name, TierSource(Path(run_dir), Path(root) if root else None)


def _summary(joined: JoinedCorpus) -> str:
    lines = [f"{joined.policy.name} on {joined.corpus_id}: {len(joined.question_ids)} questions"]
    for tier in joined.policy.tiers:
        rows = joined.signals.get(tier.name, {})
        outcomes = Counter(s.outcome.value for s in rows.values())
        runaways = sum(1 for s in rows.values() if s.runaway)
        cost = sum(s.cost_usd for s in rows.values())
        lines.append(
            f"  {tier.name}: {len(rows)} rows, {dict(outcomes)}, {runaways} runaways, "
            f"total cost ${cost:.4f}"
        )
    lines.append(f"  gaps: { {t: len(ids) for t, ids in find_gaps(joined).items()} }")
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, open_cascade: OpenCascade = open_for_ask) -> None:
    """Run a sub-command: `join` (summary), `needed` (subset file), `report` or `ask`.

    `open_cascade` builds the cascade for `ask`; tests pass one over fakes.
    """
    args = _parse_args(argv)
    if args.command == "ask":
        ask_command(args, open_cascade)
        return
    if args.command == "report":
        _run_report(args)
        return
    policies = [
        CascadePolicy.model_validate_json(path.read_text(encoding="utf-8")) for path in args.policy
    ]
    sources = dict(_parse_run(value) for value in args.run)
    if args.command == "join":
        for policy in policies:
            print(_summary(join_corpus(policy, sources, args.corpus, args.questions_root)))
        return
    result = write_needed(
        policies, args.tier, sources, args.corpus, args.questions_root, args.out_root
    )
    print(
        f"wrote {len(result.question_ids)} questions to {result.path} "
        f"({result.n_already_answered} already have a row in the tier's run)"
    )
