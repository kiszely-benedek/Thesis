"""The `infra-cypher-replay` sub-command: re-run a stored Cypher run's queries and time them.

No model is called. The output folder looks like a run folder (`timings.jsonl`,
`environment.jsonl`) plus `db_replay.json`, which `infra-report` reads as the Cypher tier's local
compute. See `plantgraph.infra.cypher_replay` for what is and is not measured.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from plantgraph.infra.cypher_replay import (
    REPLAY_META_FILE,
    CypherReplayMeta,
    CypherReplayRow,
    recorded_queries,
    replay_queries,
)
from plantgraph.infra.environment import RunEnvironment, collect_run_environment
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.harness.cypher_setup import check_store_profile, open_checked_neo4j_view
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import RunConfig
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME
from plantgraph.store.neo4j_loader import read_memory_settings, read_neo4j_version
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import from_env

_REPO_ROOT = Path(__file__).resolve().parents[4]

#: Opens (and checks) the database for a corpus; tests pass a stub.
SourceFactory = Callable[[LoadPlan], CypherSource]


def add_replay_arguments(command: argparse.ArgumentParser) -> None:
    """The options of `infra-cypher-replay`: the stored run, the corpus, the output folder."""
    command.add_argument("--source-run", required=True, type=Path, help="the stored Cypher run")
    command.add_argument("--corpus", required=True)
    command.add_argument(
        "--corpora-root",
        required=True,
        type=Path,
        help="<root>/<corpus>/ingest.json of the plant-profile corpus loaded in Neo4j",
    )
    command.add_argument("--out-run", required=True, type=Path, help="new folder for the timings")


class _SourceRun(NamedTuple):
    """What the replay takes from the stored run's config."""

    run_id: str
    strategy: str
    timeout_s: float
    row_cap: int


def _read_source_run(source_run: Path, corpus_id: str) -> _SourceRun:
    """The stored run's one Cypher strategy and its parameters.

    Raises:
        ValueError: the run is not a single-corpus run of exactly one Cypher arm.
    """
    config = RunConfig.model_validate_json(
        RunDir(source_run).config_path.read_text(encoding="utf-8")
    )
    arms = [name for name in config.strategies if name in PROFILE_OF_NAME]
    if len(arms) != 1 or list(config.corpora) != [corpus_id]:
        raise ValueError(
            f"expected run {config.run_id} to hold one Cypher arm on corpus {corpus_id}, "
            f"found strategies {sorted(config.strategies)} on corpora {list(config.corpora)}"
        )
    params = config.strategies[arms[0]]
    return _SourceRun(config.run_id, arms[0], float(params["timeout_s"]), int(params["row_cap"]))


def _write_replay(
    out_run: Path, rows: list[CypherReplayRow], environment: RunEnvironment, meta: CypherReplayMeta
) -> None:
    out_run.mkdir(parents=True)  # fails if it exists: a measurement is never overwritten
    lines = "".join(row.model_dump_json() + "\n" for row in rows)
    (out_run / "timings.jsonl").write_text(lines, encoding="utf-8")
    (out_run / "environment.jsonl").write_text(
        environment.model_dump_json() + "\n", encoding="utf-8"
    )
    (out_run / REPLAY_META_FILE).write_text(meta.model_dump_json(indent=2), encoding="utf-8")


def run_replay(
    args: argparse.Namespace, open_source: SourceFactory = open_checked_neo4j_view
) -> CypherReplayMeta:
    """Replay the stored run's queries against the loaded store and write the folder."""
    if args.out_run.exists():
        raise FileExistsError(f"expected {args.out_run} not to exist, found it; not overwriting")
    run = _read_source_run(args.source_run, args.corpus)
    queries = recorded_queries(RunDir(args.source_run).read_rows())
    ingest_json = args.corpora_root / args.corpus / "ingest.json"
    plan = load_corpus_artifacts(args.corpus, ingest_json).load_plan
    check_store_profile(plan, PROFILE_OF_NAME[run.strategy])
    source = open_source(plan)
    try:
        rows = replay_queries(
            source, queries, strategy=run.strategy, timeout_s=run.timeout_s, row_cap=run.row_cap
        )
    finally:
        source.close()
    meta = CypherReplayMeta(
        source_run=run.run_id,
        strategy=run.strategy,
        corpus_id=args.corpus,
        timeout_s=run.timeout_s,
        row_cap=run.row_cap,
        n_source_questions=len(queries),
        n_original_retrieval_errors=sum(q.original_retrieval_error for q in queries),
        n_replay_errors=sum(row.replay_outcome != "ok" for row in rows),
    )
    _write_replay(args.out_run, rows, _environment(), meta)
    return meta


def _environment() -> RunEnvironment:
    settings = from_env()
    version = read_neo4j_version(settings) if settings else None
    memory = read_memory_settings(settings) if settings else {}
    return collect_run_environment(_REPO_ROOT, 1, version, memory)


def replay_command(args: argparse.Namespace) -> None:
    """Run the replay and print its summary."""
    meta = run_replay(args)
    print(meta.model_dump_json(indent=2))
    print(f"wrote {args.out_run}")
