"""Pure orchestration for `python -m plantgraph.ingest` (design `kg-construction.md` §8).

Two entry points, one per CLI subcommand: `run_synthetic` builds a corpus with
the generator and the splitter; `run_proteus` imports one real DEXPI drawing.
Both funnel through the same `localize -> resolve -> build_load_plan` steps
(ADR-0009's rationale: EXP-0001 and EXP-0002 must run the same downstream
code), and both time every stage with `time.perf_counter` — never
`tracemalloc`, which distorts exactly the allocation-heavy stages this timing
cares about most (see `benchmark/scale_smoke.py`'s docstring).

Neither function touches argv, environment variables, `sys.exit`, or `print`:
`__main__.py` owns the command line, this module only orchestrates and
returns an `IngestResult`. A caller who wants no Neo4j at all passes
`settings=None` — the `--no-neo4j` case is therefore not a special path here,
just an absent argument.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from pathlib import Path

import networkx as nx

from plantgraph.adapters.pydexpi_adapter import (
    abstract_conceptual_graph,
    load_complete_graph,
    map_conceptual_graph,
)
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
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
    stage_seconds: dict[str, float] = {}

    plant, stage_seconds["generate"] = _timed(lambda: _generate_plant_graph(generator_config))
    (sheets, manifest), stage_seconds["split"] = _timed(lambda: split(plant, split_config))
    (localized_sheets, occurrence_map), stage_seconds["localize"] = _timed(lambda: localize(sheets))
    resolution, stage_seconds["resolve"] = _timed(lambda: resolve(localized_sheets))

    gate_equal: bool | None = None
    gate_differences: list[str] = []
    resolution_score: ResolutionScore | None = None
    if check:
        check_result, stage_seconds["check"] = _timed(
            lambda: _check_gate(plant, resolution, occurrence_map, manifest)
        )
        gate_equal, gate_differences, resolution_score = check_result

    plan, stage_seconds["plan"] = _timed(
        lambda: build_load_plan(corpus_id, localized_sheets, resolution)
    )
    load_report = _load_if_requested(settings, plan, stage_seconds)

    return IngestResult(
        corpus_id=corpus_id,
        config={
            "generator": generator_config.model_dump(mode="json"),
            "split": split_config.model_dump(mode="json"),
        },
        counts=_counts(localized_sheets, resolution, plan),
        stage_seconds=stage_seconds,
        resolution=resolution.report,
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
    stage_seconds: dict[str, float] = {}

    imported, stage_seconds["import"] = _timed(lambda: import_proteus_sheet(path))
    (localized_sheets, _occurrence_map), stage_seconds["localize"] = _timed(
        lambda: localize([imported.sheet])
    )
    resolution, stage_seconds["resolve"] = _timed(lambda: resolve(localized_sheets))
    plan, stage_seconds["plan"] = _timed(
        lambda: build_load_plan(corpus_id, localized_sheets, resolution)
    )
    load_report = _load_if_requested(settings, plan, stage_seconds)

    return IngestResult(
        corpus_id=corpus_id,
        config={"source_file": str(path)},
        counts=_counts(localized_sheets, resolution, plan),
        stage_seconds=stage_seconds,
        resolution=resolution.report,
        import_report=imported.report,
        load_report=load_report,
        neo4j_version=load_report.neo4j_version if load_report else None,
    )


# --- steps shared by both entry points -----------------------------------------------------


def _generate_plant_graph(generator_config: GeneratorConfig) -> nx.DiGraph[str]:
    """The generator's full round trip (build -> load -> abstract -> map), as one stage.

    `benchmark/scale_smoke.py` times these four steps separately for the
    generator's own design note; the ingest CLI only needs the resulting
    plant graph, so they are folded into the single "generate" stage here.
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


def _counts(sheets: list[SheetGraph], resolution: Resolution, plan: LoadPlan) -> IngestCounts:
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
