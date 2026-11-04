"""Blocking on a real small v2 plant with every reference's tag varied (X-T2).

Pipeline under test: split -> tag variants -> localize -> pair connectors -> candidates -> metrics.
The variant operators keep the blocking key by construction, so completeness must be 1.0.
"""

from __future__ import annotations

from plant_v2 import graph_of

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.tag_variants import VariantConfig, apply_tag_variants
from plantgraph.eval.blocking_metrics import gold_links_from_groups, score_blocking
from plantgraph.ingest.headline_v2 import HeadlinePresetV2
from plantgraph.resolution.connector_labels import read_connector_labels
from plantgraph.resolution.identity_candidates import CandidateSet, generate_candidates
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.pairing import pair_connectors


def _localized_variant_plant(
    salt: str = "",
) -> tuple[list[SheetGraph], SplitManifest, OccurrenceMap]:
    plant, _ = graph_of(1, 6)
    sheets, manifest = split(plant, HeadlinePresetV2(duplication_rate=1.0).split_config(seed=11))
    varied, manifest, _ = apply_tag_variants(
        sheets, manifest, VariantConfig(profile="exp0004", seed=5)
    )
    localized, occurrence_map = localize(varied, salt=salt)
    return localized, manifest, occurrence_map


def _candidates(sheets: list[SheetGraph]) -> CandidateSet:
    labels = [label for sheet in sheets for label in read_connector_labels(sheet)[0]]
    pairs, _ = pair_connectors(labels, {sheet.sheet_id for sheet in sheets})
    return generate_candidates(sheets, pairs)


def test_completeness_is_one_on_a_fully_varied_v2_plant() -> None:
    sheets, manifest, occurrence_map = _localized_variant_plant()
    gold = gold_links_from_groups(manifest.identity_groups, occurrence_map, sheets)
    metrics = score_blocking(_candidates(sheets), gold)
    assert metrics.n_gold_links > 0
    assert metrics.pair_completeness == 1.0
    assert metrics.n_candidates >= metrics.n_gold_links
    assert metrics.reduction_ratio is not None and metrics.reduction_ratio > 0.5


def test_a_salted_localize_gives_the_same_candidates_and_cards() -> None:
    plain = _candidates(_localized_variant_plant()[0])
    salted = _candidates(_localized_variant_plant(salt="G2")[0])
    assert plain.model_dump_json() == salted.model_dump_json()
