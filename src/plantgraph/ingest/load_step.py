"""The Neo4j step of an ingest run: optional recreation, the load, and the store measurement.

Kept apart from `pipeline.py` so that file stays about orchestration. Everything here is
optional: with no Neo4j settings the step does nothing (the `--no-neo4j` case).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from plantgraph.infra.environment import RunEnvironment, collect_run_environment
from plantgraph.infra.store_size import StoreFootprint, measure_store
from plantgraph.store.neo4j_loader import (
    LoadReport,
    load_corpus,
    read_memory_settings,
    recreate_database,
)
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings

#: `load_step.py` -> `ingest` -> `plantgraph` -> `src` -> repository root (git state is read there)
_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class StoreMeasurement:
    """Optional infrastructure-cost steps around the Neo4j load (ADR-0051, `infra-cost.md` §4.2).

    `fresh_database` recreates the database before loading, so no reserved space from
    earlier loads inflates the size. `neo4j_home` is the server's home directory;
    when given, the store is measured on disk after a checkpoint.
    """

    fresh_database: bool = False
    neo4j_home: Path | None = None

    @property
    def requested(self) -> bool:
        """Whether any infrastructure-cost step was asked for."""
        return self.fresh_database or self.neo4j_home is not None


#: the default: no recreation, no measurement
NO_MEASUREMENT = StoreMeasurement()


@dataclass
class LoadOutcome:
    """What the optional Neo4j step produced; a field is `None` when its step did not run."""

    report: LoadReport | None = None
    environment: RunEnvironment | None = None
    footprint: StoreFootprint | None = None


def load_if_requested(
    settings: Neo4jSettings | None,
    plan: LoadPlan,
    stage_seconds: dict[str, float],
    measurement: StoreMeasurement,
) -> LoadOutcome:
    """Load the plan if Neo4j settings were given; fold `LoadReport`'s own stage timings in.

    `load_corpus` already times its five sub-steps individually with
    `perf_counter` (`neo4j_loader.py`) — reusing those numbers here avoids
    timing the same wall-clock interval a second time.

    Raises:
        ValueError: a store measurement was requested but the load is skipped.
    """
    if settings is None:
        if measurement.requested:
            raise ValueError(
                "expected Neo4j settings for --fresh-database/--neo4j-home, found none "
                "(the load is skipped)"
            )
        return LoadOutcome()
    if measurement.fresh_database:
        start = time.perf_counter()
        recreate_database(settings)
        stage_seconds["load_recreate"] = time.perf_counter() - start
    report = load_corpus(settings, plan)
    stage_seconds["load_wipe"] = report.wipe_s
    stage_seconds["load_schema"] = report.schema_s
    stage_seconds["load_nodes"] = report.nodes_s
    stage_seconds["load_relationships"] = report.relationships_s
    stage_seconds["load_verify"] = report.verify_s
    stage_seconds["load_total"] = report.total_s
    return _measure_after_load(settings, report, measurement)


def _measure_after_load(
    settings: Neo4jSettings, report: LoadReport, measurement: StoreMeasurement
) -> LoadOutcome:
    """Record the environment, and the store size when `--neo4j-home` was given."""
    if not measurement.requested:
        return LoadOutcome(report=report)
    environment = collect_run_environment(
        _REPO_ROOT,
        concurrency=None,
        neo4j_version=report.neo4j_version,
        neo4j_memory_settings=read_memory_settings(settings),
    )
    footprint = None
    if measurement.neo4j_home is not None:
        footprint = measure_store(
            settings, measurement.neo4j_home, fresh_database=measurement.fresh_database
        )
    return LoadOutcome(report=report, environment=environment, footprint=footprint)
