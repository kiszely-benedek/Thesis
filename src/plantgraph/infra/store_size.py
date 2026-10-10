"""How big the Neo4j store is on disk and in counts, measured after a checkpoint.

The size of a store follows from what was loaded *and* from what the database held
before, so the measurement is meant for a freshly recreated database (ADR-0051
point 4). Transaction logs are reported apart: their size follows the server's
retention policy, not the corpus.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.store.neo4j_loader import StoreCounts, checkpoint, count_store
from plantgraph.store.neo4j_settings import Neo4jSettings


class StoreFootprint(BaseModel):
    """The size of one Neo4j database after a checkpoint."""

    model_config = ConfigDict(frozen=True)

    database: str
    #: whether the database was recreated just before loading (so no reserved space is left over)
    fresh_database: bool
    #: recursive size of `<neo4j-home>/data/databases/<db>`
    data_bytes: int
    #: recursive size of `<neo4j-home>/data/transactions/<db>`, reported apart from the store
    tx_log_bytes: int
    #: the server's own `store.size.database` metric; `None` without the enterprise metrics CSV
    metrics_store_bytes: int | None
    #: the server's `store.size.available_reserved` metric: space held but not used
    metrics_reserved_bytes: int | None
    n_nodes: int
    n_relationships: int
    n_properties: int


def directory_bytes(path: Path) -> int:
    """Total size of all files below `path`.

    Raises:
        FileNotFoundError: `path` is not a directory (a wrong `--neo4j-home` must not read as 0).
    """
    if not path.is_dir():
        raise FileNotFoundError(f"expected a directory to measure, found nothing at {path}")
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def read_last_value(csv_path: Path) -> float | None:
    """The last value of a Neo4j metrics CSV (header `t,value`), or `None` if there is no file."""
    if not csv_path.is_file():
        return None
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return None  # header only: the server has not written a sample yet
    return float(lines[-1].split(",")[1])


def read_last_metric(csv_path: Path) -> int | None:
    """`read_last_value` rounded down to whole bytes, for the size metrics."""
    value = read_last_value(csv_path)
    return None if value is None else int(value)


def measure_store(
    settings: Neo4jSettings, neo4j_home: Path, *, fresh_database: bool
) -> StoreFootprint:
    """Checkpoint the database, then read its size from disk, from metrics, and by counting."""
    checkpoint(settings)
    counts = count_store(settings)
    return build_footprint(settings.database, neo4j_home, counts, fresh_database=fresh_database)


def build_footprint(
    database: str, neo4j_home: Path, counts: StoreCounts, *, fresh_database: bool
) -> StoreFootprint:
    """Combine disk sizes, metrics and counts; pure file reads, no database."""
    metrics = neo4j_home / "metrics"
    return StoreFootprint(
        database=database,
        fresh_database=fresh_database,
        data_bytes=directory_bytes(neo4j_home / "data" / "databases" / database),
        tx_log_bytes=directory_bytes(neo4j_home / "data" / "transactions" / database),
        metrics_store_bytes=read_last_metric(metrics / _metric_file(database, "database")),
        metrics_reserved_bytes=read_last_metric(
            metrics / _metric_file(database, "available_reserved")
        ),
        n_nodes=counts.n_nodes,
        n_relationships=counts.n_relationships,
        n_properties=counts.n_properties,
    )


def _metric_file(database: str, name: str) -> str:
    return f"neo4j.database.{database}.store.size.{name}.csv"
