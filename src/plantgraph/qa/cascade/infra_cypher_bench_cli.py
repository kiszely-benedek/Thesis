"""The `infra-cypher-bench` sub-command: time queries against a loaded store, no model called.

Where `infra-cypher-replay` re-runs every query of one stored run at that run's own timeout,
this command measures *which timeout and row cap would be right*: it takes the stored run's
aborted queries (`--from-run`), a query file (`--queries`) and the generic shapes
(`--anchor`, `--route`), runs each once at the largest `--timeouts` value and prints a table
with the verdict at every listed timeout. See `plantgraph.qa.cascade.shape_bench`.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TextIO

from plantgraph.qa.cascade.shape_bench import (
    BenchQuery,
    BenchRow,
    queries_from_run_rows,
    read_queries,
    read_run_rows,
    render_table,
    run_bench,
)
from plantgraph.qa.cascade.shape_queries import generic_shapes
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.harness.cypher_setup import check_store_profile, open_checked_neo4j_view
from plantgraph.store.neo4j_plan import LoadPlan

#: Opens (and checks) the database for a corpus; tests pass a stub.
SourceFactory = Callable[[LoadPlan], CypherSource]

#: The store profile the bench queries are written for (`send_to` between `PlantItem`s).
_PROFILE: Literal["plant"] = "plant"


def add_bench_arguments(command: argparse.ArgumentParser) -> None:
    """The options of `infra-cypher-bench`."""
    command.add_argument("--corpus", required=True)
    command.add_argument("--corpora-root", required=True, type=Path)
    command.add_argument("--out-dir", required=True, type=Path, help="new folder for the results")
    command.add_argument("--timeouts", type=float, nargs="+", default=[30.0, 120.0, 300.0])
    command.add_argument("--row-cap", type=int, default=1000)
    command.add_argument("--from-run", type=Path, help="a stored Cypher run: its aborted queries")
    command.add_argument("--queries", type=Path, help="JSONL of {query_id, group, query}")
    command.add_argument("--anchor", action="append", default=[], help="tag for the set shapes")
    command.add_argument(
        "--route", action="append", default=[], metavar="START:END", help="tag pair, route shapes"
    )


def _collect_queries(args: argparse.Namespace) -> list[BenchQuery]:
    queries: list[BenchQuery] = []
    if args.from_run:
        rows = read_run_rows(args.from_run / "answers.jsonl")
        queries += queries_from_run_rows(rows, group="recorded")
    if args.queries:
        queries += read_queries(args.queries)
    routes = [tuple(pair.split(":", 1)) for pair in args.route]
    queries += generic_shapes(args.anchor, [(start, end) for start, end in routes])
    if not queries:
        raise ValueError("expected --from-run, --queries, --anchor or --route, found none")
    return queries


def run_bench_command(
    args: argparse.Namespace, open_source: SourceFactory = open_checked_neo4j_view
) -> list[BenchRow]:
    """Measure every query once at the largest timeout and write `bench.jsonl` + `bench.md`."""
    if args.out_dir.exists():
        raise FileExistsError(f"expected {args.out_dir} not to exist, found it; not overwriting")
    queries = _collect_queries(args)
    plan = load_corpus_artifacts(
        args.corpus, args.corpora_root / args.corpus / "ingest.json"
    ).load_plan
    check_store_profile(plan, _PROFILE)
    args.out_dir.mkdir(parents=True)
    with (args.out_dir / "bench.jsonl").open("w", encoding="utf-8") as sink:
        rows = run_bench(
            lambda: open_source(plan),
            queries,
            timeout_s=max(args.timeouts),
            row_cap=args.row_cap,
            on_row=lambda row: _log_row(sink, row),
        )
    table = render_table(rows, sorted(args.timeouts))
    (args.out_dir / "bench.md").write_text(table + "\n", encoding="utf-8")
    return rows


def _log_row(sink: TextIO, row: BenchRow) -> None:
    """Append the row to the results file at once, so a long run can be followed."""
    sink.write(row.model_dump_json() + "\n")
    sink.flush()
    print(
        f"{row.group:9} {row.query_id[:60]:60} {row.outcome:8} "
        f"{row.seconds:7.1f}s rows={row.n_rows}",
        flush=True,
    )


def bench_command(args: argparse.Namespace) -> None:
    """Run the bench and print the table."""
    rows = run_bench_command(args)
    print(render_table(rows, sorted(args.timeouts)))
    print(f"wrote {args.out_dir}")
