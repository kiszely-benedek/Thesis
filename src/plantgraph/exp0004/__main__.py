"""Command line of the free path.

python -m plantgraph.exp0004 build --target-sheets 100 --out DIR
python -m plantgraph.exp0004 tune DIR
python -m plantgraph.exp0004 decide DIR --decider d1 --taus-json DIR/taus.json
python -m plantgraph.exp0004 score DIR
python -m plantgraph.exp0004 links DIR --decider d2 [--out links.json]
python -m plantgraph.exp0004 report DIR --out report.md

The model-calling commands are cache-only unless --allow-paid-calls (needs --max-spend-usd):
python -m plantgraph.exp0004 decide DIR --decider d4 [--allow-paid-calls --max-spend-usd 0.1]
python -m plantgraph.exp0004 pilot DIR --n 20 [--allow-paid-calls --max-spend-usd 0.05]
python -m plantgraph.exp0004 open100 --out FILE [--allow-paid-calls --max-spend-usd 0.01]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.exp0004 import commands, d4_cli
from plantgraph.exp0004.bootstrap import N_RESAMPLES
from plantgraph.exp0004.corpus import ALL_FAMILIES, DEV_SEED, CorpusSpec, corpus_id_for
from plantgraph.exp0004.deciders import DECIDER_IDS


def main(argv: list[str] | None = None) -> None:
    """Parse the command line and run one step."""
    args = _parser().parse_args(argv)
    if d4_cli.is_llm_command(args):
        d4_cli.run_llm_command(args)
    elif args.command == "build":
        commands.build(_spec(args), args.out)
    elif args.command == "tune":
        print(commands.tune_thresholds(args.directory).model_dump_json())
    elif args.command == "decide":
        run = commands.decide(args.directory, args.decider, args.taus_json)
        print(run.pair_level.model_dump_json())
    elif args.command == "score":
        print(commands.score(args.directory, args.resamples).model_dump_json(indent=1))
    elif args.command == "links":
        print(commands.write_links(args.directory, args.decider, args.out))
    else:
        commands.report(args.directories, args.out)


def _spec(args: argparse.Namespace) -> CorpusSpec:
    corpus_id = args.corpus_id or corpus_id_for(
        args.target_sheets, args.seed, args.duplication_rate, args.families
    )
    return CorpusSpec(
        corpus_id=corpus_id,
        target_sheets=args.target_sheets,
        seed=args.seed,
        duplication_rate=args.duplication_rate,
        families=tuple(args.families),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plantgraph.exp0004", description="EXP-0004 free path")
    steps = parser.add_subparsers(dest="command", required=True)

    build = steps.add_parser("build", help="build a corpus and label its candidate pairs")
    build.add_argument("--target-sheets", type=int, required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--seed", type=int, default=DEV_SEED)
    build.add_argument("--duplication-rate", type=float, default=1.0)
    build.add_argument("--families", nargs="+", choices=ALL_FAMILIES, default=["format"])
    build.add_argument("--corpus-id", help="default: composed from the options (design section 4)")

    tune = steps.add_parser("tune", help="choose tau1 and tau2 (dev corpus only)")
    tune.add_argument("directory", type=Path)

    decide = steps.add_parser("decide", help="run one decider on a built corpus")
    decide.add_argument("directory", type=Path)
    decide.add_argument("--decider", choices=DECIDER_IDS, required=True)
    decide.add_argument("--taus-json", type=Path, help="needed for d1 and d2")
    d4_cli.add_llm_arguments(decide)  # only read for --decider d4

    score = steps.add_parser("score", help="score all decisions with bootstrap intervals")
    score.add_argument("directory", type=Path)
    score.add_argument("--resamples", type=int, default=N_RESAMPLES)

    links = steps.add_parser("links", help="write a decider's links for ingest --identity-links")
    links.add_argument("directory", type=Path)
    links.add_argument("--decider", choices=DECIDER_IDS, required=True)
    links.add_argument("--out", type=Path)

    pilot = steps.add_parser("pilot", help="D4 on a sample of a dev corpus: parse-failure rate")
    pilot.add_argument("directory", type=Path)
    pilot.add_argument("--n", type=int, default=20, help="number of pairs (default 20)")
    d4_cli.add_llm_arguments(pilot)

    open100 = steps.add_parser("open100", help="D4 on the OPEN100 text-only cards (qualitative)")
    open100.add_argument("--out", type=Path, required=True)
    d4_cli.add_llm_arguments(open100)

    report = steps.add_parser("report", help="Markdown report over scored corpora")
    report.add_argument("directories", type=Path, nargs="+")
    report.add_argument("--out", type=Path, required=True)
    return parser


if __name__ == "__main__":
    main()
