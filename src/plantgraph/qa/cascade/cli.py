"""`python -m plantgraph.qa.cascade {join,needed}` -- check a join, or write a tier's subset."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from plantgraph.qa.cascade.join import (
    DEFAULT_QSUB_ROOT,
    JoinedCorpus,
    TierSource,
    find_gaps,
    join_corpus,
)
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.needed import write_needed


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
    commands.choices["needed"].add_argument("--tier", required=True)
    commands.choices["needed"].add_argument("--out-root", type=Path, default=DEFAULT_QSUB_ROOT)
    return parser.parse_args(argv)


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


def main(argv: list[str] | None = None) -> None:
    """Run the `join` (print a summary) or `needed` (write a subset file) sub-command."""
    args = _parse_args(argv)
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
