"""`python -m plantgraph.qa.v2tb run ...` and `... load ...` -- the two commands of the B arm.

`load` puts a B corpus into the local Neo4j with its valve positions and checks the database holds
them (`load_b.py`): `load --corpus-id H1000g22p1B --corpora-root data/runs/exp0009/corpora
[--fresh-database]`. `run` starts, resumes or replays a V2T-B run.

The flags are those of `python -m plantgraph.qa.harness` (same parser, same frozen run config); the
differences are the ones the B arm needs. Corpora are B corpora (`--corpus H1000g22p1B:test`),
strategies are `cypher_rag_lines_b` and `graph_agent_lines_b`, and `--strategy-params-json` may be
the E9 parameter file `params_b.json`, whose keys carry no `_b`. **Paid calls stay off unless
`--allow-paid-calls` is typed**, exactly as in the harness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from plantgraph.llm.models import CacheMiss
from plantgraph.qa.harness.cli import _build_config, _parse_args, _split_corpus_arg
from plantgraph.qa.v2tb.answer_b import a_name_of
from plantgraph.qa.v2tb.load_b import load_b_corpus
from plantgraph.qa.v2tb.runner_b import run_harness_b
from plantgraph.store.neo4j_settings import from_env

_USAGE = (
    "usage: python -m plantgraph.qa.v2tb run <the flags of python -m plantgraph.qa.harness>\n"
    "       python -m plantgraph.qa.v2tb load --corpus-id ...B --corpora-root DIR"
    " [--fresh-database]"
)


def b_strategy_params(path: Path | None, strategy_names: list[str]) -> dict[str, dict[str, Any]]:
    """One parameter dict per B strategy, read from a file keyed by the B or the A name.

    Raises:
        SystemExit: the file is not a JSON object of objects, names a strategy not asked for, or
            names one strategy under both its A and its B name (one of them would silently win).
    """
    given: object = {} if path is None else json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(given, dict) or not all(isinstance(v, dict) for v in given.values()):
        raise SystemExit(
            f"error: expected {path} to hold a JSON object of objects, found {given!r}"
        )
    wanted = {name: {name, a_name_of(name)} for name in strategy_names}
    unused = sorted(set(given) - set().union(*wanted.values()))
    if unused:
        raise SystemExit(f"error: expected params only for {strategy_names}, found {unused}")
    both = sorted(name for name in strategy_names if {name, a_name_of(name)} <= set(given))
    if both:
        raise SystemExit(f"error: expected one entry per strategy, found {both} under both names")
    return {
        name: dict(next((given[key] for key in (name, a_name_of(name)) if key in given), {}))
        for name in strategy_names
    }


def _load_command(arguments: list[str]) -> None:
    """Load one B corpus and print its record; refuse a database that lacks the positions."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.v2tb load")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--corpora-root", required=True, type=Path)
    parser.add_argument("--fresh-database", action="store_true")
    args = parser.parse_args(arguments)
    settings = from_env()
    if settings is None:
        raise SystemExit(
            "error: expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD, found them unset"
        )
    try:
        record = load_b_corpus(
            args.corpus_id, args.corpora_root, settings, fresh_database=args.fresh_database
        )
    except ValueError as error:
        raise SystemExit(f"error: {error}") from error
    print(record.model_dump_json(indent=2))


def main(argv: list[str] | None = None) -> None:
    """Dispatch `run` or `load`; `run` parses argv, runs the B harness, prints the summary."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "load":
        _load_command(arguments[1:])
        return
    if not arguments or arguments[0] != "run":
        raise SystemExit(_USAGE)
    args = _parse_args(arguments[1:])
    if args.allow_paid_calls and args.max_spend_usd is None:
        raise SystemExit("error: --allow-paid-calls needs --max-spend-usd (a hard spend cap)")
    if args.allow_paid_calls and args.concurrency > 1 and args.cost_per_question_usd is None:
        raise SystemExit("error: --concurrency > 1 on a paid run needs --cost-per-question-usd")
    params = b_strategy_params(args.strategy_params_json, args.strategy)
    args.strategy_params_json = None  # the frozen config builder knows only the harness's names
    corpus_roles = dict(_split_corpus_arg(value) for value in args.corpus)
    config = _build_config(args, list(corpus_roles)).model_copy(update={"strategies": params})
    try:
        summary = run_harness_b(
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
        raise SystemExit(2) from error
    print(summary.model_dump_json(indent=2))
    if summary.stopped_by_spend_cap:
        print("stopped by the spend cap; rerun with the same --run-id to resume", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
