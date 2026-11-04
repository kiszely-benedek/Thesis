"""Pure orchestration for `python -m plantgraph.ingest` (design `kg-construction.md` §8).

Two entry points, one per CLI subcommand: `run_synthetic` builds a corpus with
the generator and the splitter; `run_proteus` imports one real DEXPI drawing.
Both funnel through the same `localize -> resolve -> build_load_plan` steps
(ADR-0009's rationale: EXP-0001 and EXP-0002 must run the same downstream
code), and both time every stage with `time.perf_counter` — never
`tracemalloc`, which distorts exactly the allocation-heavy stages this timing
cares about most (see `benchmark/scale_smoke.py`'s docstring).

`build_synthetic_corpus` and `build_proteus_corpus` are the one place the
generate/import -> localize -> resolve steps run (design `qa-system.md`
§18.1 item 1, QA-T0): `run_synthetic`/`run_proteus` call them and then add
the gate check, the load plan and the optional Neo4j load, and
`qa/corpus.py` calls them again — with the same configs, read back from a
saved `ingest.json` — to rebuild a corpus for the Q&A side. Without this,
each caller would repeat the pipeline itself, and the in-memory corpus a
strategy is tested against could silently drift from the one actually loaded
into Neo4j.

Neither function touches argv, environment variables, `sys.exit`, or `print`:
`__main__.py` owns the command line, this module only orchestrates and
returns an `IngestResult`. A caller who wants no Neo4j at all passes
`settings=None` — the `--no-neo4j` case is therefore not a special path here,
just an absent argument.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from plantgraph.adapters.pydexpi_proteus_import import (
    ImportedSheet,
    VocabularyName,
    import_proteus_sheet,
)
from plantgraph.benchmark.generator_dispatch import AnyGeneratorConfig, generate_plant_graph_any
from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.tag_variants import VariantConfig, VariantDraw, apply_tag_variants
from plantgraph.eval.graph_equality import graph_differences, to_original_ids, visible_view
from plantgraph.eval.resolution_scoring import ResolutionScore, score_resolution
from plantgraph.ingest.counts import compute_ingest_counts, compute_layer_counts
from plantgraph.ingest.identity_file import read_identity_links
from plantgraph.ingest.load_step import NO_MEASUREMENT, StoreMeasurement, load_if_requested
from plantgraph.ingest.models import IngestResult
from plantgraph.resolution.identity_links import IdentityLinkSet
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.models import Resolution
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_plan import build_load_plan
from plantgraph.store.neo4j_settings import Neo4jSettings
from plantgraph.store.plant_rows import StoreProfile

# how many unmerged original items the gate spells out; the header line carries the total
_MAX_UNMERGED_EXAMPLES = 5


@dataclass
class SyntheticCorpus:
    """A synthetic corpus, generated and split, but not yet gate-checked or loaded.

    `plant` and `manifest` are the ground truth: the unsplit plant graph and
    the splitter's answer key. `sheets` are the raw, pre-`localize()` sheets
    the question generator reads (design §2.1) — they still carry the
    original node ids, so nothing downstream of `build_synthetic_corpus`
    should read them except gold-side code.
    """

    plant: nx.DiGraph[str]
    sheets: list[SheetGraph]
    manifest: SplitManifest
    localized_sheets: list[SheetGraph]
    occurrence_map: OccurrenceMap
    resolution: Resolution
    stage_seconds: dict[str, float]
    #: gold side: what `apply_tag_variants` drew (empty without variants)
    variant_draws: list[VariantDraw] = field(default_factory=list)


@dataclass
class ProteusCorpus:
    """One imported Proteus drawing, localized and resolved, but not yet loaded.

    There is no `plant`/`manifest` field here: a lone imported file has no
    answer key to compare the resolver against (design §1).
    """

    imported: ImportedSheet
    localized_sheets: list[SheetGraph]
    occurrence_map: OccurrenceMap
    resolution: Resolution
    stage_seconds: dict[str, float]


def build_synthetic_corpus(
    generator_config: AnyGeneratorConfig,
    split_config: SplitConfig,
    variants: VariantConfig | None = None,
    identity_links: IdentityLinkSet | None = None,
) -> SyntheticCorpus:
    """Generate a plant, split it into sheets, and resolve it — the one shared synthetic path.

    `run_synthetic` calls this once per run; `qa/corpus.py` calls it again
    with the same configs to rebuild a corpus deterministically from a saved
    `ingest.json` (design `qa-system.md` §18.1 item 1). Neither the gate
    check nor the Neo4j load happen here: they need a `corpus_id` and are
    each optional, so they stay in `run_synthetic`.

    EXP-0004, both off by default: `variants` re-writes reference tags after the split
    (so the split is unchanged), and `identity_links` lets `resolve` merge them again.
    """
    stage_seconds: dict[str, float] = {}

    plant, stage_seconds["generate"] = _timed(lambda: generate_plant_graph(generator_config))
    (sheets, manifest), stage_seconds["split"] = _timed(lambda: split(plant, split_config))
    draws: list[VariantDraw] = []
    if variants is not None:
        # a "variants" stage key exists only for variant corpora, so default timings keep their keys
        (sheets, manifest, draws), stage_seconds["variants"] = _timed(
            lambda: apply_tag_variants(sheets, manifest, variants)
        )
    (localized_sheets, occurrence_map), stage_seconds["localize"] = _timed(lambda: localize(sheets))
    resolution, stage_seconds["resolve"] = _timed(lambda: resolve(localized_sheets, identity_links))

    return SyntheticCorpus(
        plant=plant,
        sheets=sheets,
        manifest=manifest,
        localized_sheets=localized_sheets,
        occurrence_map=occurrence_map,
        resolution=resolution,
        stage_seconds=stage_seconds,
        variant_draws=draws,
    )


def build_proteus_corpus(path: Path, vocabulary: VocabularyName = "v1") -> ProteusCorpus:
    """Import one Proteus XML drawing and resolve it — the one shared Proteus path.

    `run_proteus` calls this once per run; `qa/corpus.py` calls it again with
    the same source path to rebuild a corpus from a saved `ingest.json`
    (design `qa-system.md` §18.1 item 1). `vocabulary` is the import's class set (`"v1"`/`"v2"`).
    """
    stage_seconds: dict[str, float] = {}

    imported, stage_seconds["import"] = _timed(
        lambda: import_proteus_sheet(path, vocabulary=vocabulary)
    )
    (localized_sheets, occurrence_map), stage_seconds["localize"] = _timed(
        lambda: localize([imported.sheet])
    )
    resolution, stage_seconds["resolve"] = _timed(lambda: resolve(localized_sheets))

    return ProteusCorpus(
        imported=imported,
        localized_sheets=localized_sheets,
        occurrence_map=occurrence_map,
        resolution=resolution,
        stage_seconds=stage_seconds,
    )


def run_synthetic(
    *,
    corpus_id: str,
    generator_config: AnyGeneratorConfig,
    split_config: SplitConfig,
    check: bool,
    settings: Neo4jSettings | None,
    store_profile: StoreProfile = "occurrence",
    measurement: StoreMeasurement = NO_MEASUREMENT,
    variants: VariantConfig | None = None,
    identity_links_path: Path | None = None,
) -> IngestResult:
    """Generate a synthetic plant, split it into sheets, resolve, and (optionally) load it.

    `check` runs gate G1 (design §5.6): does the resolver reproduce the plant
    it was built from? This is only possible here, because only the generator
    hands back the original plant graph and the `SplitManifest` to compare
    against — a `proteus` import has no such answer key (design §1).

    `variants` and `identity_links_path` (EXP-0004) default to off; when set they are recorded
    in `config` under `variants` / `identity`, and only then, so a default record is unchanged.
    """
    config: dict[str, Any] = {
        "generator": generator_config.model_dump(mode="json"),
        "split": split_config.model_dump(mode="json"),
    }
    if variants is not None:
        config["variants"] = variants.model_dump(mode="json")
    identity_links = None
    if identity_links_path is not None:
        identity_links, record = read_identity_links(identity_links_path)
        config["identity"] = record.model_dump(mode="json")
    corpus = build_synthetic_corpus(generator_config, split_config, variants, identity_links)
    stage_seconds = dict(corpus.stage_seconds)

    gate_equal: bool | None = None
    gate_differences: list[str] = []
    resolution_score: ResolutionScore | None = None
    if check:
        check_result, stage_seconds["check"] = _timed(
            lambda: _check_gate(
                corpus.plant, corpus.resolution, corpus.occurrence_map, corpus.manifest
            )
        )
        gate_equal, gate_differences, resolution_score = check_result

    plan, stage_seconds["plan"] = _timed(
        lambda: build_load_plan(
            corpus_id, corpus.localized_sheets, corpus.resolution, profile=store_profile
        )
    )
    outcome = load_if_requested(settings, plan, stage_seconds, measurement)
    load_report = outcome.report

    return IngestResult(
        corpus_id=corpus_id,
        config=config,
        counts=compute_ingest_counts(corpus.localized_sheets, corpus.resolution, plan),
        store_profile=store_profile,
        layer_counts=compute_layer_counts(plan),
        stage_seconds=stage_seconds,
        resolution=corpus.resolution.report,
        load_report=load_report,
        gate_equal=gate_equal,
        gate_differences=gate_differences,
        resolution_score=resolution_score,
        neo4j_version=load_report.neo4j_version if load_report else None,
        environment=outcome.environment,
        store_footprint=outcome.footprint,
    )


def run_proteus(
    *,
    corpus_id: str,
    path: Path,
    settings: Neo4jSettings | None,
    store_profile: StoreProfile = "occurrence",
    measurement: StoreMeasurement = NO_MEASUREMENT,
    vocabulary: VocabularyName = "v1",
) -> IngestResult:
    """Import one Proteus XML drawing as a single-sheet corpus, resolve, and (optionally) load it.

    There is no `check` argument here: a lone imported file has no answer key
    to check the resolver against (design §1) — `import_proteus_sheet`'s own
    `ImportReport` is this path's accuracy report instead, and it is coverage
    against the file's own classes, not a resolver score. The `vocabulary` is written into the
    run's `config` only for `"v2"`, so a v1 record stays byte-identical to what it was.
    """
    corpus = build_proteus_corpus(path, vocabulary)
    stage_seconds = dict(corpus.stage_seconds)

    plan, stage_seconds["plan"] = _timed(
        lambda: build_load_plan(
            corpus_id, corpus.localized_sheets, corpus.resolution, profile=store_profile
        )
    )
    outcome = load_if_requested(settings, plan, stage_seconds, measurement)
    load_report = outcome.report

    return IngestResult(
        corpus_id=corpus_id,
        config=_proteus_config(path, vocabulary),
        counts=compute_ingest_counts(corpus.localized_sheets, corpus.resolution, plan),
        store_profile=store_profile,
        layer_counts=compute_layer_counts(plan),
        stage_seconds=stage_seconds,
        resolution=corpus.resolution.report,
        import_report=corpus.imported.report,
        load_report=load_report,
        neo4j_version=load_report.neo4j_version if load_report else None,
        environment=outcome.environment,
        store_footprint=outcome.footprint,
    )


# --- steps shared by both entry points -----------------------------------------------------


def _proteus_config(path: Path, vocabulary: VocabularyName) -> dict[str, str]:
    """The import record: the source file, plus the vocabulary when it is not the v1 default."""
    config = {"source_file": str(path)}
    if vocabulary != "v1":
        config["vocabulary"] = vocabulary
    return config


def generate_plant_graph(generator_config: AnyGeneratorConfig) -> nx.DiGraph[str]:
    """The generator's full round trip as one stage, for a v1 or a v2 config (see the dispatch).

    Public so `qa/corpus.py` can rebuild the same ground-truth plant from a saved config
    without going through the rest of the pipeline.
    """
    return generate_plant_graph_any(generator_config)


def _check_gate(
    plant: nx.DiGraph[str],
    resolution: Resolution,
    occurrence_map: OccurrenceMap,
    manifest: SplitManifest,
) -> tuple[bool, list[str], ResolutionScore]:
    """Gate G1 (design §5.6): does `resolve(localize(split(plant)))` reproduce `plant`?

    The resolution score is computed first and always returned: it is exactly
    the number an inexact-tags experiment wants, so a failed gate must not hide it.
    """
    score = score_resolution(resolution, manifest, occurrence_map)
    unmerged = _unmerged_identity_differences(resolution.plant, occurrence_map)
    if unmerged:
        # `to_original_ids` would raise here; an unmerged group is a result to report, not a crash
        return False, unmerged, score
    actual = to_original_ids(resolution.plant, occurrence_map)
    differences = graph_differences(actual, visible_view(plant))
    return differences == [], differences, score


def _unmerged_identity_differences(
    resolved: nx.DiGraph[str], occurrence_map: OccurrenceMap, limit: int = _MAX_UNMERGED_EXAMPLES
) -> list[str]:
    """Describe original items that the resolver left as several nodes (empty if none).

    One physical item drawn on several sheets should come out of `resolve` as a
    single node. If two resolved nodes still translate to the same original id,
    the resolver failed to merge that identity group.
    """
    resolved_keys_by_original_id: dict[str, list[str]] = {}
    for local_key in resolved.nodes:
        original_id = occurrence_map.original_node_id(local_key)
        resolved_keys_by_original_id.setdefault(original_id, []).append(local_key)

    unmerged = {oid: keys for oid, keys in resolved_keys_by_original_id.items() if len(keys) > 1}
    if not unmerged:
        return []
    examples = [
        f"original {oid!r} -> resolved nodes {keys}" for oid, keys in sorted(unmerged.items())
    ]
    header = (
        f"identity group left unmerged: {len(unmerged)} original items "
        f"map to several resolved nodes"
    )
    return [header, *examples[:limit]]


def _timed[T](action: Callable[[], T]) -> tuple[T, float]:
    """Run `action`; return its result together with the measured wall-clock time."""
    start = time.perf_counter()
    result = action()
    return result, time.perf_counter() - start
