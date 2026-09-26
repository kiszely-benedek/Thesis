"""`eval/resolution_scoring.py` — pair/identity precision and recall (`kg-construction.md` §6).

Two kinds of test: hand-built cases that pin down the exact TP/FP/FN/precision/
recall arithmetic (including the "None means undefined, not zero" rule), and
design §10 T5's acceptance condition run through the full pipeline — G3
expressed as `score_resolution(...) == 1.0` at splitter defaults, and pair
precision staying 1.0 at the harder `DRAWING_ONLY` dial.
"""

from __future__ import annotations

import networkx as nx

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import ConnectorPair, IdentityGroup, MatchRule
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.eval.resolution_scoring import (
    PairScore,
    ResolutionScore,
    groups_to_original,
    pairs_to_original,
    score_connector_pairs,
    score_identity_groups,
    score_resolution,
)
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.resolver import resolve

# --- score_connector_pairs: TP/FP/FN and the None-means-undefined rule ---


def _pair(from_key: str, to_key: str) -> ConnectorPair:
    return ConnectorPair(from_key=from_key, to_key=to_key)


def test_matching_pair_is_a_true_positive_even_when_reversed() -> None:
    """Pairs are unordered: OPEN100 pairs carry no inherent from/to direction (§6)."""
    predicted = [_pair("a", "b")]
    gold = [_pair("b", "a")]

    score = score_connector_pairs(predicted, gold)

    assert score == PairScore(
        true_positives=1, false_positives=0, false_negatives=0, precision=1.0, recall=1.0, f1=1.0
    )


def test_wrong_pair_is_a_false_positive_and_missing_pair_a_false_negative() -> None:
    predicted = [_pair("a", "b"), _pair("c", "d")]  # "c-d" is not in the gold set
    gold = [_pair("a", "b"), _pair("e", "f")]  # "e-f" was missed

    score = score_connector_pairs(predicted, gold)

    assert score.true_positives == 1
    assert score.false_positives == 1
    assert score.false_negatives == 1
    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.f1 == 0.5


def test_no_predicted_pairs_gives_undefined_precision_but_zero_recall() -> None:
    """An empty numerator+denominator is undefined (`None`), not silently 0.0 or 1.0."""
    score = score_connector_pairs([], [_pair("a", "b")])

    assert score.precision is None, "precision has no denominator when nothing was predicted"
    assert score.recall == 0.0
    assert score.f1 is None


def test_empty_gold_and_empty_prediction_score_as_fully_undefined() -> None:
    score = score_connector_pairs([], [])

    assert score == PairScore(
        true_positives=0, false_positives=0, false_negatives=0, precision=None, recall=None, f1=None
    )


# --- score_identity_groups: the pairwise reduction ---


def _group(tag: str, home: str, *references: str) -> IdentityGroup:
    return IdentityGroup(tag=tag, home=home, references=list(references))


def test_a_three_member_group_is_scored_as_its_three_pairwise_links() -> None:
    """A group of k occurrences asserts k(k-1)/2 links; here k=3 gives 3 links, all correct."""
    predicted = [_group("P-1", "0:a", "1:b", "2:c")]
    gold = [_group("P-1", "0:a", "1:b", "2:c")]

    score = score_identity_groups(predicted, gold)

    assert score == PairScore(
        true_positives=3, false_positives=0, false_negatives=0, precision=1.0, recall=1.0, f1=1.0
    )


def test_a_missed_group_member_costs_only_the_links_that_involve_it() -> None:
    """Predicting {a,b} instead of the true {a,b,c} finds 1 of the 3 true links, none wrong."""
    predicted = [_group("P-1", "0:a", "1:b")]
    gold = [_group("P-1", "0:a", "1:b", "2:c")]

    score = score_identity_groups(predicted, gold)

    assert score.true_positives == 1
    assert score.false_positives == 0
    assert score.false_negatives == 2
    assert score.precision == 1.0
    assert score.recall == 1.0 / 3


def test_merging_two_unrelated_groups_is_penalized_as_a_false_positive() -> None:
    """Predicting one group over two true, unrelated ones invents the cross-group links."""
    predicted = [_group("merged", "0:a", "1:b", "0:c", "1:d")]
    gold = [_group("P-1", "0:a", "1:b"), _group("P-2", "0:c", "1:d")]

    score = score_identity_groups(predicted, gold)

    assert score.true_positives == 2  # {a,b} and {c,d} are still asserted
    assert score.false_positives == 4  # a-c, a-d, b-c, b-d are all invented
    assert score.false_negatives == 0


# --- pairs_to_original / groups_to_original: translating local keys back to the manifest's ---


def _occurrence_map() -> OccurrenceMap:
    return OccurrenceMap(
        local_to_original={
            "0:occ1": "0:P-1",
            "0:occ2": "0:V-1",
            "1:occ3": "1:P-1",
        }
    )


def test_pairs_to_original_rewrites_keys_and_keeps_the_match_rule() -> None:
    occurrence_map = _occurrence_map()
    pair = ConnectorPair(from_key="0:occ1", to_key="1:occ3", match_rule=MatchRule.CONNECTOR_NUMBER)

    (translated,) = pairs_to_original([pair], occurrence_map)

    assert translated.from_key == "0:P-1"
    assert translated.to_key == "1:P-1"
    assert translated.match_rule is MatchRule.CONNECTOR_NUMBER


def test_groups_to_original_rewrites_home_and_references() -> None:
    occurrence_map = _occurrence_map()
    group = IdentityGroup(tag="P-1", home="0:occ1", references=["1:occ3"])

    (translated,) = groups_to_original([group], occurrence_map)

    assert translated.home == "0:P-1"
    assert translated.references == ["1:P-1"]


# --- score_resolution end to end: T5 acceptance ---


def _generated_plant(seed: int = 8) -> nx.DiGraph[str]:
    """A 4-unit synthetic plant — the default of n_units (`GeneratorConfig`)."""
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


def _score(config: SplitConfig) -> ResolutionScore:
    plant = _generated_plant()
    sheets, manifest = split(plant, config)
    localized, occurrence_map = localize(sheets)
    resolution = resolve(localized)
    return score_resolution(resolution, manifest, occurrence_map)


def test_g3_score_is_perfect_at_splitter_defaults() -> None:
    """Design §10 T5 acceptance: 1.0 precision and recall at splitter defaults.

    duplication_rate=0.5 is needed to have any identity groups to score at all
    (the default 0.0 duplicates nothing) — every other dial (labelling,
    numbering, matching) stays at `SplitConfig`'s default.
    """
    config = SplitConfig(sheet_equipment_budget=3, seed=0, duplication_rate=0.5)

    score = _score(config)

    assert score.connector_pairs.precision == 1.0
    assert score.connector_pairs.recall == 1.0
    assert score.identity.precision == 1.0
    assert score.identity.recall == 1.0


def test_pair_precision_is_1_at_drawing_only_detail() -> None:
    """Design §10 T5 acceptance: pair precision 1.0 at `DRAWING_ONLY` (recall may be < 1.0).

    On this small generated plant recall was observed at 1.0 too — the weaker
    labelling still left every connector distinguishable by line_number/fluid_code
    (design §5.2's proven property only promises precision, not recall).
    """
    config = SplitConfig(
        sheet_equipment_budget=3, seed=0, connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY
    )

    score = _score(config)

    assert score.connector_pairs.precision == 1.0
    assert score.connector_pairs.recall == 1.0  # observed; not guaranteed by the design


def test_identity_recall_drops_when_tags_are_not_matched_exactly() -> None:
    """`exact_match_tags=False` perturbs a reference's own tag (`splitter.py:_tag_variant`).

    The resolver only ever does exact matching (design §5.3), so it cannot
    find these references — reported here rather than hard-coded, per design
    §10 T5.
    """
    config = SplitConfig(
        sheet_equipment_budget=3, seed=0, duplication_rate=0.5, exact_match_tags=False
    )

    score = _score(config)

    assert score.connector_pairs.precision == 1.0, (
        "the connector labels are unaffected by this dial"
    )
    assert score.identity.recall is not None
    assert score.identity.recall < 1.0, (
        f"observed identity recall {score.identity.recall} under exact_match_tags=False "
        "(perturbed tags should cost at least one true link)"
    )


def test_score_resolution_accepts_a_none_occurrence_map_for_manifest_space_input() -> None:
    """The OPEN100 seam (§6): predicted keys already in manifest space, no renaming to undo.

    OPEN100's own adapter (Phase 5, not built yet) will hand `score_resolution`
    keys that are already original — this test stands in for that by
    translating the synthetic resolver's output up front, then passing
    `occurrence_map=None` so `score_resolution` does no further translation.
    """
    plant = _generated_plant()
    sheets, manifest = split(plant, SplitConfig(sheet_equipment_budget=3, seed=0))
    localized, occurrence_map = localize(sheets)
    resolution = resolve(localized)
    resolution.connector_pairs = pairs_to_original(resolution.connector_pairs, occurrence_map)
    resolution.identity_groups = groups_to_original(resolution.identity_groups, occurrence_map)

    score = score_resolution(resolution, manifest, occurrence_map=None)

    assert score.connector_pairs.precision == 1.0
    assert score.connector_pairs.recall == 1.0
