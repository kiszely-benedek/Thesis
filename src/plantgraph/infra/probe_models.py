"""What `cascade infra-probe` records: how long the live cascade takes to start, and how big it is.

Two separate probes, because tracing memory slows the code it traces: timings come from one
process, memory figures from another (ADR-0051 point 3).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.infra.environment import RunEnvironment


class StartupProbe(BaseModel):
    """Startup time per stage and process memory of one live-cascade start, with no model call."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    policy: str
    environment: RunEnvironment
    #: Seconds per startup stage, in the order `open_for_ask` runs them.
    stage_seconds: dict[str, float]
    #: The corpus rebuild's own stages (generate, split, ...): the regeneration share of `rebuild`.
    rebuild_stage_seconds: dict[str, float]
    #: Median of three builds of the ContextRAG prompt; `None` when it was not measured.
    context_rag_build_s: float | None
    context_rag_chars: int | None
    #: Peak memory of this process just after the imports, before the corpus was touched.
    process_baseline_bytes: int
    #: Peak memory of this process at the end of the probe.
    process_peak_bytes: int
    #: Resident memory of the Neo4j server process; `None` when no such process was found.
    neo4j_rss_bytes: int | None
    #: Page cache in use (usage ratio x configured size); `None` without the metrics files.
    page_cache_used_bytes: int | None


class MemoryProbe(BaseModel):
    """Bytes the in-memory graph structures keep alive, counted by `tracemalloc`."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    environment: RunEnvironment
    #: Net bytes kept after building the occurrence-graph view (`NetworkxGraphView`).
    view_net_bytes: int
    #: Net bytes the merged plant graph (`ItemGraph`) adds on top of the view.
    item_graph_net_bytes: int
    #: Highest traced size during both builds.
    traced_peak_bytes: int
