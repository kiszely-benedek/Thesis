"""Load a corpus back from a saved `ingest.json`, through the one shared pipeline.

(Design `qa-system.md` §18.1 item 1, QA-T0.)

A few terms, for a reader who knows Python but not the process-engineering
domain this project is about:

- **corpus**: one plant's worth of drawing sheets, generated or imported
  together and given one `corpus_id`.
- **ground truth**: the answer key a synthetic corpus is built with — the
  unsplit plant graph and the splitter's `SplitManifest` — which the
  question generator reads to compute a question's correct answer. A real
  (Proteus) import has no such answer key (design §1), so these fields are
  `None` for it.
- **occurrence**: one appearance of an equipment or piping symbol on one
  sheet. `localize()` renames every occurrence to an opaque per-sheet id
  before any retrieval code sees it; the `OccurrenceMap` is the only thing
  that still knows the original id, so it counts as ground truth too.

Without this module, `qa/graph_view.py` (QA-T3), the question generator
(QA-T6/T7) and the harness (QA-T10) would each have to re-run
`generate/import -> split -> localize -> resolve -> build_load_plan`
themselves, and nothing would then guarantee that their in-memory corpus was
the same one actually loaded into Neo4j. `load_corpus_artifacts` closes that
gap by rebuilding from the *same* configuration `ingest.json` recorded, using
`ingest.pipeline`'s own builder functions — and then checks the rebuilt sizes
against what `ingest.json` recorded, so a stale file or a non-deterministic
pipeline step is caught here rather than passed downstream silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.ingest.models import IngestCounts, IngestResult
from plantgraph.ingest.pipeline import (
    build_proteus_corpus,
    build_synthetic_corpus,
    compute_ingest_counts,
)
from plantgraph.resolution.localize import OccurrenceMap
from plantgraph.resolution.models import Resolution
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan


@dataclass
class GoldCorpusData:
    """The answer-key half of a corpus: read by the question generator and gate checks only.

    Never by a retrieval strategy or `qa/graph_view.py` — that ban is
    enforced at the AST level by `tests/test_qa_graph_view_imports.py`, which
    refuses those modules the right to import this module at all.
    """

    #: The unsplit ground-truth plant graph; `None` for a Proteus import (design §1).
    plant: nx.DiGraph[str] | None
    #: The splitter's answer key; `None` for a Proteus import.
    manifest: SplitManifest | None
    #: Raw, pre-`localize()` sheets — still carry the original node ids.
    sheets: list[SheetGraph]
    #: Opaque local key -> original key, the only place that mapping survives.
    occurrence_map: OccurrenceMap


@dataclass
class CorpusArtifacts:
    """Everything the Q&A side needs about one corpus, built by exactly one pipeline.

    `gold` is kept as its own sub-object so a caller can hand the rest of
    this dataclass to code that must never see the answer key (`qa-system.md`
    §2.1 D8/D9) without also handing over `gold` by accident.
    """

    corpus_id: str
    #: `None` for a Proteus corpus, which has no generator/split configuration.
    generator_config: GeneratorConfig | None
    split_config: SplitConfig | None
    #: The imported file's path, as a string; `None` for a synthetic corpus.
    source_path: str | None
    localized_sheets: list[SheetGraph]
    resolution: Resolution
    load_plan: LoadPlan
    #: The same numbers `ingest.json`'s `counts` field holds, recomputed here.
    load_plan_counts: IngestCounts
    gold: GoldCorpusData
    #: Timings from *this* rebuild (generate/import, split, localize, resolve)
    #: — not the original run's numbers. Read `ingest.json`'s own
    #: `stage_seconds` directly for the timings that are worth reporting
    #: (design §2.1 R6); this field exists only because the builder
    #: functions return it alongside everything else.
    stage_seconds: dict[str, float]


def load_corpus_artifacts(corpus_id: str, ingest_json_path: Path) -> CorpusArtifacts:
    """Rebuild a corpus from a saved `ingest.json`, using the same config it recorded.

    Nothing about the corpus is read from disk except that small config
    file: the sheets, the resolution and the load plan are all recomputed by
    calling `ingest.pipeline.build_synthetic_corpus` / `build_proteus_corpus`
    — the same functions `run_synthetic`/`run_proteus` call — so "loaded from
    disk" and "built in memory" can never silently diverge.

    Args:
        corpus_id: the corpus this caller expects to get back — checked
            against the id recorded in `ingest_json_path`.
        ingest_json_path: the file `python -m plantgraph.ingest ... --out DIR`
            wrote, i.e. `DIR/ingest.json`.

    Raises:
        ValueError: `corpus_id` does not match the file's own `corpus_id`, or
            rebuilding the corpus gives different counts than the file
            recorded (a stale file, or a pipeline step that stopped being
            deterministic).
    """
    result = _read_ingest_result(corpus_id, ingest_json_path)
    artifacts = _rebuild_artifacts(result)
    _check_counts_match(artifacts.load_plan_counts, result.counts, ingest_json_path)
    return artifacts


def _read_ingest_result(corpus_id: str, ingest_json_path: Path) -> IngestResult:
    result = IngestResult.model_validate_json(ingest_json_path.read_text(encoding="utf-8"))
    if result.corpus_id != corpus_id:
        raise ValueError(
            f"expected corpus_id {corpus_id!r} in {ingest_json_path}, "
            f"found {result.corpus_id!r} instead"
        )
    return result


def _rebuild_artifacts(result: IngestResult) -> CorpusArtifacts:
    """Proteus's `config` has `source_file`; a synthetic one has `generator`/`split` instead."""
    if "source_file" in result.config:
        return _rebuild_proteus_artifacts(result)
    return _rebuild_synthetic_artifacts(result)


def _rebuild_synthetic_artifacts(result: IngestResult) -> CorpusArtifacts:
    generator_config = GeneratorConfig.model_validate(result.config["generator"])
    split_config = SplitConfig.model_validate(result.config["split"])
    corpus = build_synthetic_corpus(generator_config, split_config)
    load_plan = build_load_plan(result.corpus_id, corpus.localized_sheets, corpus.resolution)
    return CorpusArtifacts(
        corpus_id=result.corpus_id,
        generator_config=generator_config,
        split_config=split_config,
        source_path=None,
        localized_sheets=corpus.localized_sheets,
        resolution=corpus.resolution,
        load_plan=load_plan,
        load_plan_counts=compute_ingest_counts(
            corpus.localized_sheets, corpus.resolution, load_plan
        ),
        gold=GoldCorpusData(
            plant=corpus.plant,
            manifest=corpus.manifest,
            sheets=corpus.sheets,
            occurrence_map=corpus.occurrence_map,
        ),
        stage_seconds=dict(corpus.stage_seconds),
    )


def _rebuild_proteus_artifacts(result: IngestResult) -> CorpusArtifacts:
    path = Path(result.config["source_file"])
    corpus = build_proteus_corpus(path)
    load_plan = build_load_plan(result.corpus_id, corpus.localized_sheets, corpus.resolution)
    return CorpusArtifacts(
        corpus_id=result.corpus_id,
        generator_config=None,
        split_config=None,
        source_path=str(path),
        localized_sheets=corpus.localized_sheets,
        resolution=corpus.resolution,
        load_plan=load_plan,
        load_plan_counts=compute_ingest_counts(
            corpus.localized_sheets, corpus.resolution, load_plan
        ),
        gold=GoldCorpusData(
            plant=None,
            manifest=None,
            sheets=[corpus.imported.sheet],
            occurrence_map=corpus.occurrence_map,
        ),
        stage_seconds=dict(corpus.stage_seconds),
    )


def _check_counts_match(
    rebuilt: IngestCounts, recorded: IngestCounts, ingest_json_path: Path
) -> None:
    if rebuilt != recorded:
        raise ValueError(
            f"rebuilding the corpus from {ingest_json_path} gave counts {rebuilt!r}, "
            f"but the file recorded {recorded!r}: either the file is stale, or the "
            "pipeline is no longer deterministic"
        )
