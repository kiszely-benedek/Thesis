"""Corpus size tallies of an ingest run, from a `LoadPlan` (design `kg-construction.md` §7.4).

Split out of `pipeline.py`; `qa/corpus.py` recomputes the same numbers on a rebuilt corpus.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema
from plantgraph.ingest.models import IngestCounts, LayerCounts
from plantgraph.resolution.models import Resolution
from plantgraph.store.neo4j_plan import CypherStatement, LoadPlan


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


def compute_layer_counts(plan: LoadPlan) -> LayerCounts:
    """Split a plan's nodes into occurrences, plant items and structure (design §A.5)."""
    labels = plan.expected_node_labels
    n_items = labels.get(schema.PLANT_ITEM_LABEL, 0)
    structure_labels = (
        schema.NodeClass.DRAWING_SET,
        schema.NodeClass.SHEET,
        schema.NodeClass.PROCESS_PLANT,
        schema.NodeClass.PLANT_SECTION,
    )
    n_structure = sum(labels.get(label.value, 0) for label in structure_labels)
    n_nodes = labels["CorpusNode"]  # every node carries it, so it is the node total
    return LayerCounts(
        n_occurrences=n_nodes - n_items - n_structure,
        n_plant_items=n_items,
        n_structure_nodes=n_structure,
        n_drawn_as=plan.expected_relationship_types.get(schema.Relation.DRAWN_AS.value, 0),
        n_invariants=len(plan.invariant_statements),
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
