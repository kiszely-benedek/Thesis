"""Hand-made measurement models for the infrastructure-report tests (no files, no database)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from plantgraph.infra.environment import MachineInfo, RunEnvironment
from plantgraph.infra.probe_models import MemoryProbe, StartupProbe
from plantgraph.infra.report_inputs import CorpusData, ReplayStatus, RunData
from plantgraph.infra.store_size import StoreFootprint
from plantgraph.ingest.models import IngestCounts, IngestResult
from plantgraph.qa.harness.usage_meter import TimingRow
from plantgraph.resolution.models import ResolutionReport
from plantgraph.store.neo4j_loader import LoadReport

STAGES = (
    "generate",
    "split",
    "localize",
    "resolve",
    "plan",
    "load_schema",
    "load_nodes",
    "load_relationships",
    "load_verify",
)


def environment(resolution_s: float = 1e-7) -> RunEnvironment:
    machine = MachineInfo(
        cpu_name="Test CPU",
        physical_cores=2,
        logical_cores=4,
        ram_bytes=8 * 1024**3,
        os="TestOS",
        python_version="3.12",
        power_plugged=True,
    )
    return RunEnvironment(
        git_commit="abc123",
        git_dirty=False,
        machine=machine,
        clock="perf_counter",
        clock_resolution_s=resolution_s,
        concurrency=None,
        neo4j_version="5",
        neo4j_memory_settings={},
        recorded_at=datetime(2026, 10, 10, tzinfo=UTC),
    )


def footprint(data_bytes: int, nodes: int, metric: int | None) -> StoreFootprint:
    return StoreFootprint(
        database="neo4j",
        fresh_database=True,
        data_bytes=data_bytes,
        tx_log_bytes=1000,
        metrics_store_bytes=metric,
        metrics_reserved_bytes=None,
        n_nodes=nodes,
        n_relationships=nodes * 3,
        n_properties=nodes * 9,
    )


def ingest(
    corpus_id: str,
    seconds: float,
    data_bytes: int = 4_000_000,
    nodes: int = 100,
    metric: int | None = None,
    db_nodes: int | None = None,
) -> IngestResult:
    """One ingest repeat; `db_nodes` is what the database reports (default: the plan's count)."""
    resolution = ResolutionReport(
        n_sheets=10,
        n_occurrences=1,
        n_connectors=1,
        pairs_by_rule={},
        unresolved_by_reason={},
        n_identity_groups=1,
        ambiguous_tag_keys=0,
        edge_attribute_conflicts=0,
    )
    counts = IngestCounts(
        n_sheets=10,
        n_nodes=nodes,
        n_relationships=nodes * 3,
        n_connector_pairs_predicted=1,
        n_unresolved=0,
    )
    load = LoadReport(
        corpus_id=corpus_id,
        nodes_written=nodes,
        relationships_written=nodes * 3,
        batch_size=5000,
        wipe_s=0,
        schema_s=0,
        nodes_s=0,
        relationships_s=0,
        verify_s=0,
        total_s=0,
        neo4j_version="5",
    )
    return IngestResult(
        corpus_id=corpus_id,
        config={},
        counts=counts,
        stage_seconds={stage: seconds for stage in STAGES},
        resolution=resolution,
        load_report=load,
        environment=environment(),
        store_footprint=footprint(data_bytes, db_nodes or nodes, metric),
    )


def startup(corpus_id: str, rebuild_s: float, other_s: float = 1.0) -> StartupProbe:
    return StartupProbe(
        corpus_id=corpus_id,
        policy="cascade_v3",
        environment=environment(),
        stage_seconds={"rebuild": rebuild_s, "graph_view": other_s, "item_graph": other_s},
        rebuild_stage_seconds={"generate": rebuild_s},
        context_rag_build_s=0.5,
        context_rag_chars=10,
        process_baseline_bytes=100,
        process_peak_bytes=300,
        neo4j_rss_bytes=1000,
        page_cache_used_bytes=None,
    )


def memory(corpus_id: str) -> MemoryProbe:
    return MemoryProbe(
        corpus_id=corpus_id,
        environment=environment(),
        view_net_bytes=10,
        item_graph_net_bytes=20,
        traced_peak_bytes=40,
    )


def corpus(
    corpus_id: str, scale: float, data_bytes: int = 4_000_000, nodes: int = 100
) -> CorpusData:
    """Three repeats of every measurement, at `scale` times 1.0, 1.1 and 1.2 seconds."""
    factors = (1.0, 1.1, 1.2)
    return CorpusData(
        corpus_id=corpus_id,
        ingests=[ingest(corpus_id, scale * f, data_bytes, nodes) for f in factors],
        startups=[startup(corpus_id, scale * f) for f in factors],
        memory=memory(corpus_id),
    )


def timing(
    local: float,
    db: float = 0.0,
    api: float = 0.0,
    clock: Literal["monotonic", "perf_counter"] = "perf_counter",
) -> TimingRow:
    return TimingRow(
        question_id="q",
        strategy="cypher_rag_plant",
        repeat=0,
        local_compute_s=local,
        spent_usd=0.0,
        n_cached_retrieval_calls=0,
        clock=clock,
        db_client_s=db,
        db_server_s=db / 2,
        graph_api_s=api,
    )


def run(
    role: str,
    corpus_id: str,
    timings: list[TimingRow],
    status: ReplayStatus | None = "identical",
    strategy: str = "cypher_rag_plant",
    paid: bool = False,
) -> RunData:
    """A run of `role`; `status=None` makes it an old (not replayed) run."""
    return RunData(
        role=role,
        corpus_id=corpus_id,
        run_id=f"INF-{role}-{corpus_id}",
        basis="replay" if status else "old_run",
        strategy=strategy,
        replay_status=status,
        allow_paid_calls=paid,
        timings=timings,
        environments=[environment()],
        answers_cost_usd=0.01 * len(timings),
        n_cost_missing=0,
        llm_latency_s=10.0 * len(timings),
    )
