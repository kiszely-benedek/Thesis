"""The measured quantities of one corpus (table I1), with the spread over their repeats.

Quantity names are dotted keys (`ingest.generate`, `store.data_bytes`, ...); the renderer
knows their labels and units. All functions here are pure: they only read parsed models.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from plantgraph.infra.probe_models import StartupProbe
from plantgraph.infra.report_inputs import CorpusData
from plantgraph.infra.report_models import CorpusFootprintRow, Spread
from plantgraph.ingest.models import IngestResult

#: Ingest stages in pipeline order. `load_wipe` is left out: it depends on the previous corpus.
INGEST_STAGES = (
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

#: Neo4j's manual advises data and indexes times a growth factor of about 20 % (design note E11).
PAGE_CACHE_GROWTH_FACTOR = 1.2

#: A server metric that differs from the bytes on disk by more than this share is called stale.
METRIC_STALE_SHARE = 0.10


def make_spread(values: Sequence[float]) -> Spread:
    """Median, smallest and largest of the repeats.

    Raises:
        ValueError: there are no values.
    """
    if not values:
        raise ValueError("expected at least one repeat to summarise, found none")
    return Spread(
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
        n_repeats=len(values),
    )


def spread_of_optional(name: str, values: Sequence[float | None]) -> Spread | None:
    """A spread, or `None` when no repeat has the value.

    Raises:
        ValueError: only some repeats have it (a half-measured quantity must not look complete).
    """
    present = [value for value in values if value is not None]
    if not present:
        return None
    if len(present) != len(values):
        raise ValueError(f"expected {name} in all {len(values)} repeats, found {len(present)}")
    return make_spread(present)


def spread_of_present(values: Sequence[float | None]) -> Spread | None:
    """A spread over the repeats that have the value, or `None` when none has it.

    For secondary server metrics, which can be absent in some repeats; the caller says so in a
    note (`_presence_notes`) so a part-measured quantity never looks complete.
    """
    present = [value for value in values if value is not None]
    return make_spread(present) if present else None


def corpus_footprint(corpus: CorpusData) -> CorpusFootprintRow:
    """Table I1 row: sizes, ingest stages, store, startup and memory of one corpus."""
    quantities: dict[str, Spread] = {}
    quantities.update(_ingest_quantities(corpus.ingests))
    quantities.update(_store_quantities(corpus.ingests))
    quantities.update(_startup_quantities(corpus.startups))
    quantities.update(_memory_quantities(corpus))
    return CorpusFootprintRow(
        corpus_id=corpus.corpus_id,
        sizes=_sizes(corpus.ingests[0]),
        quantities=quantities,
        notes=_presence_notes(corpus) + _stale_metric_notes(corpus.ingests),
    )


def _sizes(ingest: IngestResult) -> dict[str, int]:
    sizes = {
        "sheets": ingest.counts.n_sheets,
        "nodes": ingest.counts.n_nodes,
        "relationships": ingest.counts.n_relationships,
    }
    if ingest.store_footprint is not None:
        sizes["properties"] = ingest.store_footprint.n_properties
    return sizes


def _ingest_quantities(ingests: list[IngestResult]) -> dict[str, Spread]:
    result = {
        f"ingest.{stage}": make_spread([_stage(ingest, stage) for ingest in ingests])
        for stage in INGEST_STAGES
    }
    result["ingest.build_total"] = make_spread(
        [sum(_stage(ingest, stage) for stage in INGEST_STAGES) for ingest in ingests]
    )
    return result


def _stage(ingest: IngestResult, stage: str) -> float:
    if stage not in ingest.stage_seconds:
        raise ValueError(f"expected stage {stage!r} in ingest of {ingest.corpus_id}, found none")
    return ingest.stage_seconds[stage]


def _store_quantities(ingests: list[IngestResult]) -> dict[str, Spread]:
    footprints = [ingest.store_footprint for ingest in ingests]
    measured = [footprint for footprint in footprints if footprint is not None]
    if not measured:
        return {}
    if len(measured) != len(footprints):
        raise ValueError(
            f"expected a store footprint in all {len(footprints)} ingest repeats, "
            f"found {len(measured)}"
        )
    data = [footprint.data_bytes for footprint in measured]
    result = {
        "store.data_bytes": make_spread(data),
        "store.tx_log_bytes": make_spread([f.tx_log_bytes for f in measured]),
        "store.page_cache_needed_bytes": make_spread(
            [PAGE_CACHE_GROWTH_FACTOR * size for size in data]
        ),
    }
    # secondary metric: Neo4j's CSV is recreated with the database and may lag or be empty
    metric = spread_of_present([f.metrics_store_bytes for f in measured])
    if metric is not None:
        result["store.metrics_bytes"] = metric
    return result


def _startup_quantities(startups: list[StartupProbe]) -> dict[str, Spread]:
    result = {
        f"startup.{stage}": make_spread([_probe_stage(p, stage) for p in startups])
        for stage in startups[0].stage_seconds
    }
    totals = [sum(p.stage_seconds.values()) for p in startups]
    result["startup.total"] = make_spread(totals)
    # the regeneration is a benchmark artefact: a deployment would read a stored graph
    result["startup.without_rebuild"] = make_spread(
        [total - _probe_stage(p, "rebuild") for total, p in zip(totals, startups, strict=True)]
    )
    build = spread_of_optional(
        "startup.context_rag_build", [p.context_rag_build_s for p in startups]
    )
    if build is not None:
        result["startup.context_rag_build"] = build
    return result | _process(startups)


def _probe_stage(probe: StartupProbe, stage: str) -> float:
    if stage not in probe.stage_seconds:
        raise ValueError(f"expected startup stage {stage!r} in every probe, found it missing")
    return probe.stage_seconds[stage]


def _process(startups: list[StartupProbe]) -> dict[str, Spread]:
    result = {
        "process.baseline_bytes": make_spread([p.process_baseline_bytes for p in startups]),
        "process.peak_bytes": make_spread([p.process_peak_bytes for p in startups]),
    }
    optional = {
        "neo4j.rss_bytes": [p.neo4j_rss_bytes for p in startups],
        "neo4j.page_cache_used_bytes": [p.page_cache_used_bytes for p in startups],
    }
    for name, values in optional.items():
        spread = spread_of_present(values)
        if spread is not None:
            result[name] = spread
    return result


def _memory_quantities(corpus: CorpusData) -> dict[str, Spread]:
    memory = corpus.memory
    if memory is None:
        return {}
    return {
        "memory.view_bytes": make_spread([memory.view_net_bytes]),
        "memory.item_graph_bytes": make_spread([memory.item_graph_net_bytes]),
        "memory.traced_peak_bytes": make_spread([memory.traced_peak_bytes]),
    }


def _optional_series(corpus: CorpusData) -> dict[str, list[float | None]]:
    """The secondary quantities that may be missing in some repeats, repeat by repeat."""
    footprints = [ingest.store_footprint for ingest in corpus.ingests]
    return {
        "the server's store.size.database metric": [
            f.metrics_store_bytes if f is not None else None for f in footprints
        ],
        "Neo4j's resident memory": [p.neo4j_rss_bytes for p in corpus.startups],
        "the page cache in use": [p.page_cache_used_bytes for p in corpus.startups],
    }


def _presence_notes(corpus: CorpusData) -> list[str]:
    """One note per secondary quantity that is present in some repeats but not all."""
    notes: list[str] = []
    for label, values in _optional_series(corpus).items():
        found = sum(value is not None for value in values)
        if 0 < found < len(values):
            notes.append(f"{label} is present in {found} of {len(values)} repeats only")
    return notes


def _stale_metric_notes(ingests: list[IngestResult]) -> list[str]:
    stale = 0
    compared = 0
    for ingest in ingests:
        footprint = ingest.store_footprint
        if footprint is None or footprint.metrics_store_bytes is None:
            continue
        compared += 1
        gap = abs(footprint.metrics_store_bytes - footprint.data_bytes) / footprint.data_bytes
        stale += gap > METRIC_STALE_SHARE
    if not stale:
        return []
    return [
        f"the server's store.size.database metric differs from the bytes on disk by more than "
        f"{METRIC_STALE_SHARE:.0%} in {stale} of {compared} repeats: it lags, so the bytes on "
        "disk are the figure and the metric is secondary"
    ]
