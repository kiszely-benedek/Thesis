"""Loading a B corpus into Neo4j, and the database side of gate G0-B (design `v2t-b` §10 R19).

The frozen ingest builds the **unpatched** load plan, and the frozen store check compares label and
relationship counts only, so a B corpus loaded the frozen way would pass the check while the
database lacked `operating_position`. This loader sends the patched plan (`store_b.with_positions`)
and then counts, per position code, the nodes that carry the property. Those counts must equal the
positions file's counts times the profile's layers (a `both` store keeps each valve twice);
otherwise the load is refused.

It reads the occurrence map, which is gold, so it is gold side like `store_b.py`.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path

from neo4j import READ_ACCESS, GraphDatabase
from pydantic import BaseModel, ConfigDict

from plantgraph.ingest.load_step import LoadOutcome, StoreMeasurement, load_if_requested
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.v2tb.corpus_b import B_CORPUS_SUFFIX
from plantgraph.qa.v2tb.positions import POSITIONS_FILE_NAME, read_positions_file
from plantgraph.qa.v2tb.store_b import count_positioned_rows, positions_by_local_key, with_positions
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_probe import DEFAULT_CONNECTION_TIMEOUT_S
from plantgraph.store.neo4j_settings import Neo4jSettings

LOAD_RECORD_FILE_NAME = "load_b.json"

#: Sends a plan to the database (the frozen `load_if_requested`; tests pass a stub).
PlanLoader = Callable[[Neo4jSettings, LoadPlan, dict[str, float], StoreMeasurement], LoadOutcome]
#: Counts the database's nodes that carry `operating_position`, per code (tests pass a stub).
PositionCounter = Callable[[Neo4jSettings], dict[str, int]]

_COUNT_QUERY = (
    f"MATCH (n) WHERE n.{OPERATING_POSITION} IS NOT NULL "
    f"RETURN n.{OPERATING_POSITION} AS code, count(*) AS n"
)


class LoadBRecord(BaseModel):
    """One B load, as written (one JSON line) to `load_b.json` beside the corpus's `ingest.json`."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    store_profile: str
    positions_sha256: str
    #: the positions file's count per code, times the profile's layers
    expected_per_code: dict[str, int]
    #: what the database holds, per code
    database_per_code: dict[str, int]
    nodes_written: int
    total_seconds: float


def count_positions_in_database(settings: Neo4jSettings) -> dict[str, int]:
    """Nodes carrying `operating_position` in the whole database, per code (read-only)."""
    driver = GraphDatabase.driver(
        settings.uri,
        auth=(settings.username, settings.password.get_secret_value()),
        connection_timeout=DEFAULT_CONNECTION_TIMEOUT_S,
    )
    try:
        with driver.session(database=settings.database, default_access_mode=READ_ACCESS) as session:
            return {str(row["code"]): int(row["n"]) for row in session.run(_COUNT_QUERY).data()}
    finally:
        driver.close()


def expected_counts(positions: Mapping[str, str], plan: LoadPlan) -> dict[str, int]:
    """The positions file's count per code, times the layers the plan's profile stores."""
    layers = 2 if plan.profile == "both" else 1
    return {code: n * layers for code, n in Counter(positions.values()).items()}


def load_b_corpus(
    corpus_id: str,
    corpora_root: Path,
    settings: Neo4jSettings,
    *,
    fresh_database: bool,
    loader: PlanLoader = load_if_requested,
    counter: PositionCounter = count_positions_in_database,
) -> LoadBRecord:
    """Load the patched plan of a B corpus and check the database holds its positions.

    Args:
        corpus_id: a B corpus id; its folder under `corpora_root` holds `ingest.json` and the
            positions file.
        corpora_root: the folder of corpus folders.
        settings: the Neo4j connection.
        fresh_database: recreate the database first, so nothing of an earlier corpus is left.
        loader: sends the plan to the database (a stub in tests).
        counter: counts the positions the database holds (a stub in tests).

    Raises:
        ValueError: the id does not end in `B`, the patched plan lacks a position, or the
            database's per-code counts differ from the positions file's (the data is then
            already loaded: the caller must not use it).
        FileNotFoundError: the corpus has no positions file.
    """
    if not corpus_id.endswith(B_CORPUS_SUFFIX):
        raise ValueError(
            f"expected a B corpus id (ending in {B_CORPUS_SUFFIX!r}), found {corpus_id!r}"
        )
    corpus_dir = corpora_root / corpus_id
    artifacts = load_corpus_artifacts(corpus_id, corpus_dir / "ingest.json")
    positions, sha256 = read_positions_file(corpus_dir / POSITIONS_FILE_NAME)
    by_local_key = positions_by_local_key(positions, artifacts.gold.occurrence_map)
    plan = with_positions(artifacts.load_plan, by_local_key)
    expected = expected_counts(positions, plan)
    _check_plan_rows(plan, expected)
    started = time.perf_counter()
    outcome = loader(settings, plan, {}, StoreMeasurement(fresh_database=fresh_database))
    found = counter(settings)
    if found != expected:
        raise ValueError(
            f"expected the database to hold operating_position per code {expected}, found {found}"
        )
    if outcome.report is None:
        raise ValueError("expected a load report from the loader, found none")
    record = LoadBRecord(
        corpus_id=corpus_id,
        store_profile=plan.profile,
        positions_sha256=sha256,
        expected_per_code=expected,
        database_per_code=found,
        nodes_written=outcome.report.nodes_written,
        total_seconds=time.perf_counter() - started,
    )
    _append_record(corpus_dir / LOAD_RECORD_FILE_NAME, record)
    return record


def _check_plan_rows(plan: LoadPlan, expected: Mapping[str, int]) -> None:
    """Refuse before any write when the patched plan itself lacks a positioned row."""
    found = count_positioned_rows(plan)
    if found != sum(expected.values()):
        raise ValueError(
            f"expected the patched plan to carry {sum(expected.values())} positioned rows, "
            f"found {found}"
        )


def _append_record(path: Path, record: LoadBRecord) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(record.model_dump_json() + "\n")
