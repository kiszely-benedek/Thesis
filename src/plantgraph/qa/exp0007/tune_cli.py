"""The `tune-*` commands `data/runs/exp0007/tune.sh` calls: plants, caps, the temporary database."""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.qa.exp0007 import caps as caps_module
from plantgraph.qa.exp0007.cap_plans import count_questions
from plantgraph.qa.exp0007.neo4j_tmp import drop_database
from plantgraph.qa.exp0007.tune_plan import (
    MAX_ROUNDS,
    TUNING_PLANT,
    VALIDATION_PLANTS,
    final_caps,
    require_corpus,
    round_total_usd,
    tuning_caps,
)


def _cmd_tune_corpus(args: argparse.Namespace) -> int:
    corpus = require_corpus(args.corpus_id, args.final_v)
    print(corpus.sheets, corpus.seed)
    return 0


def _print_caps(caps: caps_module.CapFile) -> None:
    for e in caps.entries:
        c = e.cost_per_question_usd
        print(f"{e.run_id:28s} n={e.n_questions:4d}  c={c:.6f}  cap ${e.cap_usd:.2f}")


def _cmd_make_tune_caps(args: argparse.Namespace) -> int:
    if args.stage == "tune":
        n = count_questions(args.questions[0])
        caps = tuning_caps(n)
    else:
        if len(args.questions) != len(VALIDATION_PLANTS):
            raise ValueError(
                f"expected one questions file per validation plant "
                f"({[p.corpus_id for p in VALIDATION_PLANTS]}), found {len(args.questions)}"
            )
        caps = final_caps(
            {
                p.corpus_id: count_questions(q)
                for p, q in zip(VALIDATION_PLANTS, args.questions, strict=True)
            }
        )
    digest = caps_module.write_cap_file(args.out, caps)
    _print_caps(caps)
    if args.stage == "tune":
        for round_no in range(1, MAX_ROUNDS + 1):
            print(f"round {round_no}: sum of caps ${round_total_usd(caps, round_no):.2f}")
    print(f"stage {caps.stage}: sum of caps ${caps.total_usd:.2f}")
    print(f"cap file {args.out}\nsha256 {digest}")
    return 0


def _cmd_drop_neo4j_database(args: argparse.Namespace) -> int:
    drop_database(args.database)
    print(f"dropped Neo4j database {args.database}")
    return 0


def add_tune_commands(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the commands on the exp0007 parser."""
    p = sub.add_parser("tune-corpus")
    p.set_defaults(handler=_cmd_tune_corpus)
    p.add_argument("--corpus-id", required=True, help=f"{TUNING_PLANT.corpus_id}, or a V plant")
    p.add_argument("--final-v", action="store_true", help="allow the held-back validation plants")
    p = sub.add_parser("make-tune-caps")
    p.set_defaults(handler=_cmd_make_tune_caps)
    p.add_argument("--stage", choices=["tune", "final"], required=True)
    p.add_argument(
        "--questions", type=Path, nargs="+", required=True, help="questions.jsonl per plant"
    )
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("drop-neo4j-database")
    p.set_defaults(handler=_cmd_drop_neo4j_database)
    p.add_argument("--database", required=True)
