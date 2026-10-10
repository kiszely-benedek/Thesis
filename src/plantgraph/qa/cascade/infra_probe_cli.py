"""The `infra-probe` sub-command: options, the probe run, and the JSON it writes."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from plantgraph.qa.cascade.infra_probe import ProbeRequest, run_memory_probe, run_startup_probe
from plantgraph.qa.cascade.live_ask import load_policy_argument, parse_tier_run_dirs


def add_probe_arguments(command: argparse.ArgumentParser) -> None:
    """The options of `infra-probe`: the corpus, the policy and its tier runs, the mode."""
    command.add_argument("--corpus", required=True)
    command.add_argument("--corpora-root", type=Path, default=Path("data") / "corpora")
    command.add_argument("--policy", required=True, help="a shipped policy name, or a JSON path")
    command.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="TIER=RUN_DIR",
        help="the stored run that fixes the tier's pin (as for `ask`)",
    )
    command.add_argument(
        "--memory",
        action="store_true",
        help="measure the graphs' memory instead of the timings (run it in its own process)",
    )
    command.add_argument(
        "--neo4j-home", type=Path, help="Neo4j directory with metrics/; adds the page cache in use"
    )
    command.add_argument("--out", required=True, type=Path, help="the probe's JSON file")


def probe_command(args: argparse.Namespace) -> None:
    """Run the timing probe, or with `--memory` the memory probe, and write its JSON."""
    request = ProbeRequest(
        corpus_id=args.corpus,
        ingest_json=args.corpora_root / args.corpus / "ingest.json",
        policy=load_policy_argument(args.policy),
        tier_run_dirs=parse_tier_run_dirs(args.run),
    )
    if args.memory:
        result: BaseModel = run_memory_probe(request)
    else:
        result = run_startup_probe(request, args.neo4j_home)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(result.model_dump_json(indent=2, exclude={"environment"}))
    print(f"wrote {args.out}")
