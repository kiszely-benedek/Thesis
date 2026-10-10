"""`cascade infra-probe`: how long the live cascade takes to start, and how big its graphs are.

It calls the same builders `open_for_ask` calls, in the same order, but times each one apart
(opening the whole cascade would give a single number). No question is asked and no model is
called. Memory is measured by a second run of the probe (`--memory`) in a fresh process,
because `tracemalloc` slows the code it watches and would spoil the timings (ADR-0051 point 3).
"""

from __future__ import annotations

import gc
import statistics
import time
import tracemalloc
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from plantgraph.infra.environment import collect_run_environment
from plantgraph.infra.probe_models import MemoryProbe, StartupProbe
from plantgraph.infra.process_memory import (
    neo4j_rss_bytes,
    page_cache_used_bytes,
    process_peak_bytes,
)
from plantgraph.qa.cascade.live import LivePolicyRefused, refuse_label_routing
from plantgraph.qa.cascade.live_build import load_tier_from_run
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.graph_view import GraphView, NetworkxGraphView
from plantgraph.qa.harness.cypher_setup import check_store_profile
from plantgraph.qa.neo4j_view import Neo4jGraphView
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.strategies.context_rag import ContextRag
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME
from plantgraph.store.neo4j_loader import read_memory_settings, read_neo4j_version
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env

#: `infra_probe.py` -> `cascade` -> `qa` -> `plantgraph` -> `src` -> repository root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONTEXT_RAG_REPEATS = 3


def _networkx_view(artifacts: CorpusArtifacts) -> GraphView:
    return NetworkxGraphView(artifacts.corpus_id, artifacts.localized_sheets, artifacts.resolution)


def _check_tier_runs(policy: CascadePolicy, tier_run_dirs: Mapping[str, Path]) -> None:
    """Read every tier's source run, which also checks its pin (as `open_live_cascade` does)."""
    for spec in policy.tiers:
        run_dir = tier_run_dirs.get(spec.name)
        if run_dir is None:
            raise LivePolicyRefused(
                f"expected a source run for tier {spec.name!r}, found only {sorted(tier_run_dirs)}"
            )
        load_tier_from_run(spec, run_dir)


def _check_store(view: Neo4jGraphView, plan: LoadPlan, policy: CascadePolicy) -> None:
    """Refuse a database that does not hold this corpus in the profile the Cypher tiers read."""
    for spec in policy.tiers:
        if spec.strategy in PROFILE_OF_NAME:
            check_store_profile(plan, PROFILE_OF_NAME[spec.strategy])
    view.check_store()


def _context_prompt(view: GraphView) -> str:
    context = ContextRag(view).retrieve("").context
    if context is None:
        raise RuntimeError("expected ContextRAG to return a prompt, found a retrieval failure")
    return context


@dataclass(frozen=True)
class ProbeSteps:
    """The builders the probe times. The defaults are the real ones; tests record calls instead."""

    rebuild: Callable[[str, Path], CorpusArtifacts] = load_corpus_artifacts
    graph_view: Callable[[CorpusArtifacts], GraphView] = _networkx_view
    check_tier_runs: Callable[[CascadePolicy, Mapping[str, Path]], None] = _check_tier_runs
    #: Creating the database view builds its schema text; the driver connects later.
    store_view: Callable[[Neo4jSettings, LoadPlan], Neo4jGraphView] = Neo4jGraphView
    check_store: Callable[[Neo4jGraphView, LoadPlan, CascadePolicy], None] = _check_store
    item_graph: Callable[[GraphView], ItemGraph] = build_item_graph
    context_prompt: Callable[[GraphView], str] = _context_prompt


@dataclass(frozen=True)
class ProbeRequest:
    """What to probe: one corpus, read back from its `ingest.json`, under one policy."""

    corpus_id: str
    ingest_json: Path
    policy: CascadePolicy
    tier_run_dirs: Mapping[str, Path]


@dataclass(frozen=True)
class StartupTimings:
    """What the timed stages produced, before the process and server readings are added."""

    stage_seconds: dict[str, float]
    rebuild_stage_seconds: dict[str, float]
    context_rag_build_s: float
    context_rag_chars: int


class _Stages:
    """Runs steps and keeps the seconds each took, in run order."""

    def __init__(self) -> None:
        self.seconds: dict[str, float] = {}

    def run[T](self, name: str, step: Callable[[], T]) -> T:
        start = time.perf_counter()
        result = step()
        self.seconds[name] = time.perf_counter() - start
        return result


def time_startup(
    request: ProbeRequest, settings: Neo4jSettings | None, steps: ProbeSteps | None = None
) -> StartupTimings:
    """Run the startup stages one by one and time each.

    Raises:
        LivePolicyRefused: label routing, or a tier without a source run or with a wrong pin.
        ValueError: a Cypher tier but no Neo4j settings.
        StoreMismatch: the database does not hold this corpus in the profile the tier reads.
    """
    steps = steps or ProbeSteps()
    policy = request.policy
    refuse_label_routing(policy)
    stages = _Stages()
    artifacts = stages.run("rebuild", lambda: steps.rebuild(request.corpus_id, request.ingest_json))
    view = stages.run("graph_view", lambda: steps.graph_view(artifacts))
    stages.run("tier_runs", lambda: steps.check_tier_runs(policy, request.tier_run_dirs))
    if any(spec.strategy in PROFILE_OF_NAME for spec in policy.tiers):
        _time_store_stages(stages, policy, artifacts.load_plan, settings, steps)
    # the tiers that are not Cypher are the agents, which all read the merged plant graph
    if any(spec.strategy not in PROFILE_OF_NAME for spec in policy.tiers):
        stages.run("item_graph", lambda: steps.item_graph(view))
    build_s, chars = _time_context_prompt(view, steps)
    return StartupTimings(stages.seconds, artifacts.stage_seconds, build_s, chars)


def _time_store_stages(
    stages: _Stages,
    policy: CascadePolicy,
    plan: LoadPlan,
    settings: Neo4jSettings | None,
    steps: ProbeSteps,
) -> None:
    if settings is None:
        raise ValueError("expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD for a Cypher tier")
    store = stages.run("schema_text", lambda: steps.store_view(settings, plan))
    try:
        stages.run("neo4j_open_check", lambda: steps.check_store(store, plan, policy))
    finally:
        store.close()


def _time_context_prompt(view: GraphView, steps: ProbeSteps) -> tuple[float, int]:
    """Median seconds of three prompt builds, and the prompt's length in characters."""
    seconds: list[float] = []
    for _ in range(_CONTEXT_RAG_REPEATS):
        start = time.perf_counter()
        prompt = steps.context_prompt(view)
        seconds.append(time.perf_counter() - start)
    return statistics.median(seconds), len(prompt)


def run_startup_probe(
    request: ProbeRequest, neo4j_home: Path | None, steps: ProbeSteps | None = None
) -> StartupProbe:
    """Time the startup, then read this process's peak and, if a server is there, its memory."""
    baseline = process_peak_bytes()  # the imports are done, the corpus is not built yet
    settings = from_env()
    timings = time_startup(request, settings, steps)
    peak = process_peak_bytes()
    memory_settings = read_memory_settings(settings) if settings else {}
    version = read_neo4j_version(settings) if settings else None
    page_cache = page_cache_used_bytes(neo4j_home, memory_settings) if neo4j_home else None
    return StartupProbe(
        corpus_id=request.corpus_id,
        policy=request.policy.name,
        environment=collect_run_environment(_REPO_ROOT, None, version, memory_settings),
        stage_seconds=timings.stage_seconds,
        rebuild_stage_seconds=timings.rebuild_stage_seconds,
        context_rag_build_s=timings.context_rag_build_s,
        context_rag_chars=timings.context_rag_chars,
        process_baseline_bytes=baseline,
        process_peak_bytes=peak,
        neo4j_rss_bytes=neo4j_rss_bytes(),
        page_cache_used_bytes=page_cache,
    )


def run_memory_probe(request: ProbeRequest, steps: ProbeSteps | None = None) -> MemoryProbe:
    """Bytes the occurrence-graph view and the plant graph keep alive (no Neo4j, no timings)."""
    steps = steps or ProbeSteps()
    refuse_label_routing(request.policy)
    artifacts = steps.rebuild(request.corpus_id, request.ingest_json)
    gc.collect()
    tracemalloc.start()  # after the rebuild: the corpus build is not what is being sized
    try:
        start = tracemalloc.get_traced_memory()[0]
        view = steps.graph_view(artifacts)
        after_view = _retained_bytes()
        item_graph = steps.item_graph(view)
        after_item_graph = _retained_bytes()
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    del item_graph  # kept until here, so that the second reading counts it
    return MemoryProbe(
        corpus_id=request.corpus_id,
        environment=collect_run_environment(_REPO_ROOT, None),
        view_net_bytes=after_view - start,
        item_graph_net_bytes=after_item_graph - after_view,
        traced_peak_bytes=peak - start,
    )


def _retained_bytes() -> int:
    gc.collect()  # drop build garbage, so only what is still referenced is counted
    return tracemalloc.get_traced_memory()[0]
