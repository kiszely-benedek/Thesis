"""The v2 headline preset, its size search, and the by_sheet_group strategy's numbering."""

from __future__ import annotations

import json
import random

import networkx as nx
import pytest
from plant_v2 import graph_of

from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.split_by_sheet_group import by_sheet_group
from plantgraph.ingest.headline import check_realized_sheets
from plantgraph.ingest.headline_v2 import (
    TEST_SEED_RANGE,
    TEST_SEEDS_V2,
    TUNING_SEEDS,
    HeadlinePresetV2,
    first_single_sheet_seed,
    headline_corpus_id_v2,
    smallest_n_units_v2,
)

_TARGETS = [1, 3, 10, 25, 60]


def test_the_preset_defaults_to_the_adr_0028_duplication_rate_and_it_is_configurable() -> None:
    assert HeadlinePresetV2().duplication_rate == 0.25
    assert HeadlinePresetV2(duplication_rate=0.5).split_config(1).duplication_rate == 0.5
    assert HeadlinePresetV2(duplication_rate=0.0).split_config(1).duplication_rate == 0.0
    with pytest.raises(ValueError):
        HeadlinePresetV2(duplication_rate=1.5)


def test_the_preset_split_config_is_v2_shaped_and_reads_back_as_a_plain_split_config() -> None:
    split = HeadlinePresetV2().split_config(7)
    dumped = split.model_dump(mode="json")
    assert dumped["strategy"] == "by_sheet_group"
    assert dumped["equipment_classes"] == sorted(dumped["equipment_classes"])
    assert "Tank" in dumped["equipment_classes"] and "LiquidFilter" in dumped["equipment_classes"]
    assert SplitConfig.model_validate(json.loads(json.dumps(dumped))).seed == 7


@pytest.mark.parametrize("target", _TARGETS)
def test_the_size_search_reaches_the_target_with_the_fewest_units(target: int) -> None:
    preset = HeadlinePresetV2()
    result = smallest_n_units_v2(target, preset, seed=1)
    assert result.predicted_sheets >= target > result.predicted_sheets_one_unit_fewer
    # the plan of exactly n units has the predicted sheets; one unit fewer falls short
    config = preset.generator_config(result.n_units, 1)
    assert plan_plant(config).sheet_count == result.predicted_sheets
    if result.n_units > 1:
        fewer = preset.generator_config(result.n_units - 1, 1)
        assert plan_plant(fewer).sheet_count == result.predicted_sheets_one_unit_fewer
    check_realized_sheets(result, result.predicted_sheets)


def test_the_size_search_is_deterministic_and_depends_on_the_seed() -> None:
    preset = HeadlinePresetV2()
    assert smallest_n_units_v2(40, preset, 3) == smallest_n_units_v2(40, preset, 3)
    assert {smallest_n_units_v2(40, preset, seed).n_units for seed in range(4)} != {0}


def test_the_size_search_rejects_a_target_below_one() -> None:
    with pytest.raises(ValueError, match="target_sheets >= 1"):
        smallest_n_units_v2(0, HeadlinePresetV2(), 1)


def test_corpus_ids_name_the_dev_corpus_the_registered_test_corpus_and_any_other_tuning_plant() -> (
    None
):
    assert headline_corpus_id_v2(100, seed=1) == "D100g2"
    assert headline_corpus_id_v2(1000, seed=5003) == "H1000g2"
    assert headline_corpus_id_v2(100, seed=5002) == "H100g2"
    # a tuning plant of a registered size is never named like the test corpus
    assert headline_corpus_id_v2(100, seed=2) == "X100g2s2"
    assert headline_corpus_id_v2(1000, seed=0) == "X1000g2s0"


def test_a_duplication_rate_other_than_the_preset_adds_a_suffix() -> None:
    assert headline_corpus_id_v2(100, 5002, duplication_rate=0.25) == "H100g2"
    assert headline_corpus_id_v2(100, 5002, duplication_rate=0.0) == "H100g2d0"
    assert headline_corpus_id_v2(100, 5002, duplication_rate=0.5) == "H100g2d50"


def test_the_test_seeds_are_inside_the_test_range_and_apart_from_every_tuning_seed() -> None:
    assert set(TEST_SEEDS_V2.values()) <= set(TEST_SEED_RANGE)
    assert not set(TEST_SEEDS_V2.values()) & set(TUNING_SEEDS)
    # H3, H10 and H30 are nested prefixes of one plant; H100 and H1000 are two further plants
    assert TEST_SEEDS_V2[3] == TEST_SEEDS_V2[10] == TEST_SEEDS_V2[30]
    assert len({TEST_SEEDS_V2[n] for n in (30, 100, 1000)}) == 3


def test_the_one_sheet_test_seed_is_the_first_one_sheet_plan_from_5100() -> None:
    assert first_single_sheet_seed(5100, 5399) == TEST_SEEDS_V2[1]
    assert smallest_n_units_v2(1, HeadlinePresetV2(), TEST_SEEDS_V2[1]).n_units == 1


def test_a_range_without_a_one_sheet_plan_is_refused() -> None:
    with pytest.raises(ValueError, match="one-sheet one-unit plant"):
        first_single_sheet_seed(5, 4)


def test_by_sheet_group_numbers_sheets_in_drawing_order_and_matches_the_plan() -> None:
    graph, _ = graph_of(1, 12)
    node_sheet = by_sheet_group(graph, SplitConfig(), random.Random(0))
    assert set(node_sheet) == set(graph.nodes)
    planned = plan_plant(HeadlinePresetV2().generator_config(12, 1)).sheet_count
    assert len(set(node_sheet.values())) == planned
    # numeric order: every node of unit 2 is on an earlier sheet than any node of unit 10
    sheets_of_unit: dict[str, list[int]] = {}
    for node, attrs in graph.nodes(data=True):
        unit = attrs["sheet_group"].split(":")[0]
        sheets_of_unit.setdefault(unit, []).append(int(node_sheet[node]))
    assert max(sheets_of_unit["2"]) < min(sheets_of_unit["10"])


def test_by_sheet_group_names_the_node_that_has_no_sheet_group() -> None:
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("n1", node_class="Tank")
    with pytest.raises(ValueError, match="n1.*sheet_group"):
        by_sheet_group(plant, SplitConfig(), random.Random(0))
