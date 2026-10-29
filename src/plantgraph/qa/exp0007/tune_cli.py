"""The `tune-*` commands `data/runs/exp0007/tune.sh` calls: plants, caps, the temporary database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from plantgraph.qa.cascade.limits import SETTINGS
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
from plantgraph.qa.exp0007.v2t_caps import (
    f1_baseline_total_usd,
    optional_total_usd,
    r4_v2t_caps,
    r5_v2t_caps,
    read_validation_costs,
)
from plantgraph.qa.strategies.cypher_rag import LINES_NAME


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


def _cmd_make_v2t_caps(args: argparse.Namespace) -> int:
    costs = read_validation_costs(args.v7_runs)
    if args.stage == "r4":
        if args.ladder_questions is None:
            raise ValueError("expected --ladder-questions for stage r4, found none")
        if args.prompt_size is None:
            raise ValueError("expected --prompt-size for stage r4, found none")
        caps = r4_v2t_caps(costs, args.ladder_questions, args.prompt_size, args.e1_runs)
    else:
        if args.sealed_questions is None or args.c1_questions is None:
            raise ValueError("expected --sealed-questions and --c1-questions for stage r5")
        caps = r5_v2t_caps(costs, args.sealed_questions, args.c1_questions, args.r4_runs)
    digest = caps_module.write_cap_file(args.out, caps)
    _print_caps(caps)
    baseline = f1_baseline_total_usd(caps)
    ctx = optional_total_usd(caps, "E7-CTXH-")
    v2t_total = caps.total_usd - baseline - ctx
    print(
        f"stage {caps.stage}: V2T caps ${v2t_total:.2f}, optional F1 baseline ${baseline:.2f}, "
        f"optional ContextRAG small ladder ${ctx:.2f}"
    )
    print(f"cap file {args.out}\nsha256 {digest}")
    return 0


def _cmd_setting_deadline(args: argparse.Namespace) -> int:
    setting = SETTINGS[args.setting]
    if setting.question_deadline_s is None:
        raise ValueError(f"expected a setting with a question deadline, found {setting.name}")
    found = json.loads(args.cypher_params.read_text(encoding="utf-8"))[LINES_NAME]["timeout_s"]
    if found != setting.cypher_timeout_s:
        raise ValueError(
            f"expected timeout_s {setting.cypher_timeout_s:g} in {args.cypher_params} "
            f"(setting {setting.name}), found {found}"
        )
    print(f"{setting.question_deadline_s:g}")
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
    p = sub.add_parser(
        "make-v2t-caps", help="R4 / R5 caps of V2T-A from the validation runs' costs"
    )
    p.set_defaults(handler=_cmd_make_v2t_caps)
    p.add_argument("--stage", choices=["r4", "r5"], required=True)
    p.add_argument("--v7-runs", type=Path, required=True, help="tune/final/runs: the V7 runs")
    p.add_argument("--ladder-questions", type=Path, help="r4: <corpus>/questions.jsonl per size")
    p.add_argument("--sealed-questions", type=Path, help="r5: <corpus>/questions.jsonl per corpus")
    p.add_argument("--prompt-size", type=Path, help="r4: prompt_size.json of the ladder corpora")
    p.add_argument("--e1-runs", type=Path, default=Path("data/runs/exp0001/runs"))
    p.add_argument("--c1-questions", type=Path, help="r5: the concurrency-1 subset")
    p.add_argument("--r4-runs", type=Path, help="r5: R4's runs; their H30g2 cost is a floor")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("setting-deadline", help="a setting's question deadline, params checked")
    p.set_defaults(handler=_cmd_setting_deadline)
    p.add_argument("--setting", choices=sorted(SETTINGS), required=True)
    p.add_argument("--cypher-params", type=Path, required=True)
    p = sub.add_parser("drop-neo4j-database")
    p.set_defaults(handler=_cmd_drop_neo4j_database)
    p.add_argument("--database", required=True)
