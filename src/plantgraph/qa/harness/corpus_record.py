"""Fill a `CorpusRecord` from a corpus's `ingest.json` (design `qa-system.md` §4, R6).

Sizes and stage timings are copied from the ingest run's own report, not
re-measured: the report is what the headline table cites. The two node counts
stay apart because they count different graphs (see `CorpusRecord`).
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.ingest.models import IngestResult
from plantgraph.qa.corpus import CorpusArtifacts
from plantgraph.qa.models import CorpusRecord


def build_corpus_record(
    artifacts: CorpusArtifacts, ingest_json_path: Path, role: str
) -> CorpusRecord:
    """Combine the saved ingest report with the rebuilt ground truth into one record.

    Raises:
        ValueError: the corpus has no generator configuration or ground-truth
            plant, i.e. it is a real (Proteus) import, which has no answer key.
    """
    ingest = IngestResult.model_validate_json(ingest_json_path.read_text(encoding="utf-8"))
    plant, manifest = artifacts.gold.plant, artifacts.gold.manifest
    generator_config, split_config = artifacts.generator_config, artifacts.split_config
    if plant is None or manifest is None or generator_config is None or split_config is None:
        raise ValueError(
            f"expected a synthetic corpus with a ground-truth plant, but {ingest.corpus_id!r} "
            "has none (a Proteus import has no answer key, design §1)"
        )
    if manifest.source_graph_hash is None:
        raise ValueError(f"split manifest of {ingest.corpus_id!r} carries no source_graph_hash")
    return CorpusRecord(
        corpus_id=ingest.corpus_id,
        role=role,
        generator_config=generator_config,
        split_config=split_config,
        n_sheets=ingest.counts.n_sheets,
        n_store_nodes=ingest.counts.n_nodes,
        n_connector_pairs_predicted=ingest.counts.n_connector_pairs_predicted,
        n_plant_nodes=plant.number_of_nodes(),
        n_plant_edges=plant.number_of_edges(),
        source_graph_hash=manifest.source_graph_hash,
        stage_seconds=dict(ingest.stage_seconds),
    )
