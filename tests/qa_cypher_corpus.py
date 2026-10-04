"""The 4-unit corpus the CypherRAG tests share, with the G1 gate asserted when it is built."""

from __future__ import annotations

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.eval.graph_equality import graph_differences, to_original_ids, visible_view
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan
from plantgraph.store.plant_rows import StoreProfile


def four_unit_corpus(duplication_rate: float = 0.0) -> SyntheticCorpus:
    """4 units (the generator default), split small so connector pairs exist; seed 7.

    Raises:
        AssertionError: G1 fails, i.e. the resolver's merged plant differs from the ground truth.
    """
    corpus = build_synthetic_corpus(
        GeneratorConfig(n_units=4, seed=7),
        SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=duplication_rate),
    )
    merged = to_original_ids(corpus.resolution.plant, corpus.occurrence_map)
    assert graph_differences(merged, visible_view(corpus.plant)) == [], "G1 must hold first"
    return corpus


def load_plan_of(
    corpus: SyntheticCorpus, corpus_id: str, profile: StoreProfile = "occurrence"
) -> LoadPlan:
    return build_load_plan(corpus_id, corpus.localized_sheets, corpus.resolution, profile=profile)
