"""What one `python -m plantgraph.ingest` run reports (design `kg-construction.md` §8).

`IngestResult` is the single JSON object the CLI prints on stdout —
`pipeline.py` builds one, `__main__.py` only serializes and prints it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from plantgraph.adapters.pydexpi_proteus_import import ImportReport
from plantgraph.eval.resolution_scoring import ResolutionScore
from plantgraph.resolution.models import ResolutionReport
from plantgraph.store.neo4j_loader import LoadReport
from plantgraph.store.plant_rows import StoreProfile


class IngestCounts(BaseModel):
    """Sizes of the corpus this run produced, independent of whether it was loaded into Neo4j.

    Counted from the `LoadPlan` (design §7.4), so these numbers match exactly
    what a real load would write even when `--no-neo4j` skips the database.
    """

    n_sheets: int
    n_nodes: int
    n_relationships: int
    n_connector_pairs_predicted: int
    n_unresolved: int


class LayerCounts(BaseModel):
    """How the stored nodes split into the two layers (ADR-0036); 0 where a profile has none.

    An *occurrence* is one symbol drawn on one sheet; a *plant item* is the merged
    node for one physical thing; `drawn_as` links an item to each of its occurrences.
    """

    n_occurrences: int
    n_plant_items: int
    n_structure_nodes: int
    n_drawn_as: int
    n_invariants: int


class IngestResult(BaseModel):
    """Everything one `synthetic` or `proteus` run produced: config, sizes, timings, gate outcome.

    `gate_equal` is `None` when `--check` was not requested (or is not
    available at all, as for `proteus` — design §1: only the generator hands
    back an answer key to check the resolver against).
    """

    corpus_id: str
    config: dict[str, Any]
    counts: IngestCounts
    #: which layers were stored; an `ingest.json` written before ADR-0036 reads back as `occurrence`
    store_profile: StoreProfile = "occurrence"
    layer_counts: LayerCounts | None = None
    stage_seconds: dict[str, float]
    resolution: ResolutionReport
    import_report: ImportReport | None = None
    load_report: LoadReport | None = None
    gate_equal: bool | None = None
    gate_differences: list[str] = Field(default_factory=list)
    resolution_score: ResolutionScore | None = None
    neo4j_version: str | None = None
