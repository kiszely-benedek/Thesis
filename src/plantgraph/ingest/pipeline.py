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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from plantgraph.adapters.pydexpi_adapter import (
    abstract_conceptual_graph,
    load_complete_graph,
    map_conceptual_graph,
)
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.adapters.pydexpi_proteus_import import ImportedSheet, import_proteus_sheet
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.eval.graph_equality import graph_differences, to_original_ids, visible_view
from plantgraph.eval.resolution_scoring import ResolutionScore, score_resolution
from plantgraph.ingest.models import IngestCounts, IngestResult
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.models import Resolution
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_loader import LoadReport, load_corpus
from plantgraph.store.neo4j_plan import CypherStatement, LoadPlan, build_load_plan
from plantgraph.store.neo4j_settings import Neo4jSettings


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
    generator_config: GeneratorConfig, split_config: SplitConfig
) -> SyntheticCorpus:
    """Generate a plant, split it into sheets, and resolve it — the one shared synthetic path.

    `run_synthetic` calls this once per run; `qa/corpus.py` calls it again
    with the same configs to rebuild a corpus deterministically from a saved
    `ingest.json` (design `qa-system.md` §18.1 item 1). Neither the gate
    check nor the Neo4j load happen here: they need a `corpus_id` and are
    each optional, so they stay in `run_synthetic`.
    """
    stage_seconds: dict[str, float] = {}

    plant, stage_seconds["generate"] = _timed(lambda: generate_plant_graph(generator_config))
    (sheets, manifest), stage_seconds["split"] = _timed(lambda: split(plant, split_config))
    (localized_sheets, occurrence_map), stage_seconds["localize"] = _timed(lambda: localize(sheets))
    resolution, stage_seconds["resolve"] = _timed(lambda: resolve(localized_sheets))

    return SyntheticCorpus(
        plant=plant,
        sheets=sheets,
        manifest=manifest,
        localized_sheets=localized_sheets,
        occurrence_map=occurrence_map,
        resolution=resolution,
        stage_seconds=stage_seconds,
    )


def build_proteus_corpus(path: Path) -> ProteusCorpus:
    """Import one Proteus XML drawing and resolve it — the one shared Proteus path.

    `run_proteus` calls this once per run; `qa/corpus.py` calls it again with
    the same source path to rebuild a corpus from a saved `ingest.json`
    (design `qa-system.md` §18.1 item 1).
    """
    stage_seconds: dict[str, float] = {}

    imported, stage_seconds["import"] = _timed(lambda: import_proteus_sheet(path))
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
    generator_config: GeneratorConfig,
    split_config: SplitConfig,
    check: bool,
    settings: Neo4jSettings | None,
) -> IngestResult:
    """Generate a synthetic plant, split it into sheets, resolve, and (optionally) load it.

    `check` runs gate G1 (design §5.6): does the resolver reproduce the plant
    it was built from? This is only possible here, because only the generator
    hands back the original plant graph and the `SplitManifest` to compare
    against — a `proteus` import has no such answer key (design §1).
    """
    corpus = build_synthetic_corpus(generator_config, split_config)
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
        lambda: build_load_plan(corpus_id, corpus.localized_sheets, corpus.resolution)
    )
    load_report = _load_if_requested(settings, plan, stage_seconds)

    return IngestResult(
        corpus_id=corpus_id,
        config={
            "generator": generator_config.model_dump(mode="json"),
            "split": split_config.model_dump(mode="json"),
        },
        counts=compute_ingest_counts(corpus.localized_sheets, corpus.resolution, plan),
        stage_seconds=stage_seconds,
        resolution=corpus.resolution.report,
        load_report=load_report,
        gate_equal=gate_equal,
        gate_differences=gate_differences,
        resolution_score=resolution_score,
        neo4j_version=load_report.neo4j_version if load_report else None,
    )


def run_proteus(*, corpus_id: str, path: Path, settings: Neo4jSettings | None) -> IngestResult:
    """Import one Proteus XML drawing as a single-sheet corpus, resolve, and (optionally) load it.

    There is no `check` argument here: a lone imported file has no answer key
    to check the resolver against (design §1) — `import_proteus_sheet`'s own
    `ImportReport` is this path's accuracy report instead, and it is coverage
    against the file's own classes, not a resolver score.
    """
    corpus = build_proteus_corpus(path)
    stage_seconds = dict(corpus.stage_seconds)

    plan, stage_seconds["plan"] = _timed(
        lambda: build_load_plan(corpus_id, corpus.localized_sheets, corpus.resolution)
    )
    load_report = _load_if_requested(settings, plan, stage_seconds)

    return IngestResult(
        corpus_id=corpus_id,
        config={"source_file": str(path)},
        counts=compute_ingest_counts(corpus.localized_sheets, corpus.resolution, plan),
        stage_seconds=stage_seconds,
        resolution=corpus.resolution.report,
        import_report=corpus.imported.report,
        load_report=load_report,
        neo4j_version=load_report.neo4j_version if load_report else None,
    )


# --- steps shared by both entry points -----------------------------------------------------


def generate_plant_graph(generator_config: GeneratorConfig) -> nx.DiGraph[str]:
    """The generator's full round trip (build -> load -> abstract -> map), as one stage.

    `benchmark/scale_smoke.py` times these four steps separately for the
    generator's own design note; the ingest CLI only needs the resulting
    plant graph, so they are folded into the single "generate" stage here.
    Public so `qa/corpus.py` can rebuild the same ground-truth plant from a
    saved `GeneratorConfig` without going through the rest of the pipeline.
    """
    generated = generate_plant(generator_config)
    complete = load_complete_graph(generated.model)
    conceptual = abstract_conceptual_graph(complete)
    plant, _conversion = map_conceptual_graph(
        conceptual, generated.record.plant_id, generated.record.stream_kind
    )
    return plant


def _check_gate(
    plant: nx.DiGraph[str],
    resolution: Resolution,
    occurrence_map: OccurrenceMap,
    manifest: SplitManifest,
) -> tuple[bool, list[str], ResolutionScore]:
    """Gate G1 (design §5.6): does `resolve(localize(split(plant)))` reproduce `plant`?"""
    actual = to_original_ids(resolution.plant, occurrence_map)
    expected = visible_view(plant)
    differences = graph_differences(actual, expected)
    score = score_resolution(resolution, manifest, occurrence_map)
    return differences == [], differences, score


def _load_if_requested(
    settings: Neo4jSettings | None, plan: LoadPlan, stage_seconds: dict[str, float]
) -> LoadReport | None:
    """Load the plan if Neo4j settings were given; fold `LoadReport`'s own stage timings in.

    `load_corpus` already times its five sub-steps individually with
    `perf_counter` (`neo4j_loader.py`) — reusing those numbers here avoids
    timing the same wall-clock interval a second time.
    """
    if settings is None:
        return None
    report = load_corpus(settings, plan)
    stage_seconds["load_wipe"] = report.wipe_s
    stage_seconds["load_schema"] = report.schema_s
    stage_seconds["load_nodes"] = report.nodes_s
    stage_seconds["load_relationships"] = report.relationships_s
    stage_seconds["load_verify"] = report.verify_s
    stage_seconds["load_total"] = report.total_s
    return report


def compute_ingest_counts(
    sheets: Sequence[SheetGraph], resolution: Resolution, plan: LoadPlan
) -> IngestCounts:
    """Corpus sizes, tallied from a `LoadPlan` (design §7.4, R6).

    Public so `qa/corpus.py` can recompute the same numbers from a rebuilt
    corpus and compare them against a saved `ingest.json`'s `counts`
    (§18.1 item 1: the rebuilt corpus must match the one that was loaded).
    """
    return IngestCounts(
        n_sheets=len(sheets),
        n_nodes=_row_count(plan.node_statements),
        n_relationships=_row_count(plan.relationship_statements),
        n_connector_pairs_predicted=len(resolution.connector_pairs),
        n_unresolved=len(resolution.unresolved),
    )


def _row_count(statements: Sequence[CypherStatement]) -> int:
    """Every row across every batch of `statements` — the same tally `LoadReport` reports."""
    total = 0
    for statement in statements:
        rows = statement.parameters["rows"]
        if not isinstance(rows, list):
            raise TypeError(f"expected a list of rows in statement parameters, got {type(rows)!r}")
        total += len(rows)
    return total


def _timed[T](action: Callable[[], T]) -> tuple[T, float]:
    """Run `action`; return its result together with the measured wall-clock time."""
    start = time.perf_counter()
    result = action()
    return result, time.perf_counter() - start
