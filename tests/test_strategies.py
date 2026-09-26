"""Invariants of the 4 partitioning strategies: node coverage, sheet budget, instrument travel."""

from __future__ import annotations

import random

import networkx as nx
import pytest

from plant_fixtures import make_plant_graph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.strategies import STRATEGIES, _flow_order
from plantgraph.graph import schema


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_every_node_gets_a_sheet(strategy_name: str) -> None:
    plant = make_plant_graph()
    config = SplitConfig(strategy=strategy_name, sheet_equipment_budget=3, seed=0)
    node_sheet = STRATEGIES[strategy_name](plant, config, random.Random(config.seed))
    assert set(node_sheet) == set(plant.nodes)


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_equipment_count_per_sheet_respects_the_budget(strategy_name: str) -> None:
    plant = make_plant_graph(chain_length=6, branches=2)
    budget = 3
    config = SplitConfig(strategy=strategy_name, sheet_equipment_budget=budget, seed=1)
    node_sheet = STRATEGIES[strategy_name](plant, config, random.Random(config.seed))

    equipment_per_sheet: dict[str, int] = {}
    for node_id, sheet_id in node_sheet.items():
        if plant.nodes[node_id]["node_class"] in config.equipment_classes:
            equipment_per_sheet[sheet_id] = equipment_per_sheet.get(sheet_id, 0) + 1
    assert all(count <= budget for count in equipment_per_sheet.values())


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_instruments_ride_along_with_their_equipment(strategy_name: str) -> None:
    # Design decision (splitter.md open question 2): an instrument does not count
    # against the sheet budget, but its sheet must match the equipment it's attached to.
    plant = make_plant_graph()
    config = SplitConfig(strategy=strategy_name, seed=2)
    node_sheet = STRATEGIES[strategy_name](plant, config, random.Random(config.seed))

    for instrument_id, equipment_id in [("inst-0-0", "eq-0-0"), ("inst-1-1", "eq-1-1")]:
        assert node_sheet[instrument_id] == node_sheet[equipment_id]


def test_random_partition_ignores_topology_but_stays_seed_stable() -> None:
    plant = make_plant_graph()
    config = SplitConfig(strategy="random", seed=42)
    first = STRATEGIES["random"](plant, config, random.Random(config.seed))
    second = STRATEGIES["random"](plant, config, random.Random(config.seed))
    assert first == second


def test_utility_aware_moves_the_high_degree_header_to_its_own_hub_sheet() -> None:
    # A utility header only gets its own hub sheet if it counts as "equipment"
    # itself — so equipment_classes is extended here.
    plant = make_plant_graph(chain_length=3, branches=3, utility_fanout=6)
    config = SplitConfig(
        strategy="utility_aware",
        sheet_equipment_budget=2,
        seed=3,
        equipment_classes=set(schema.EQUIPMENT_CLASSES) | {"utility_header"},
    )
    node_sheet = STRATEGIES["utility_aware"](plant, config, random.Random(config.seed))

    hub_sheet = node_sheet["utility-steam"]
    hub_sheet_members = {
        node_id for node_id, sheet_id in node_sheet.items() if sheet_id == hub_sheet
    }
    # the hub sheet contains only the utility header (and any non-equipment
    # nodes attached to it, if there were any), not the process chain
    assert "eq-0-0" not in hub_sheet_members


def test_by_unit_never_mixes_units_on_a_sheet() -> None:
    plant = make_plant_graph(chain_length=4, branches=3)
    config = SplitConfig(strategy="by_unit", sheet_equipment_budget=2, seed=4)
    node_sheet = STRATEGIES["by_unit"](plant, config, random.Random(config.seed))

    units_per_sheet: dict[str, set[str]] = {}
    for node_id, sheet_id in node_sheet.items():
        unit_id = plant.nodes[node_id].get("unit_id")
        if unit_id is None:  # instruments inherit unit_id from their equipment, no own value
            continue
        units_per_sheet.setdefault(sheet_id, set()).add(unit_id)
    assert all(len(units) == 1 for units in units_per_sheet.values())


def _count_cross_sheet_edges(plant: nx.DiGraph, node_sheet: dict[str, str]) -> int:
    return sum(1 for source, target in plant.edges() if node_sheet[source] != node_sheet[target])


def test_flow_greedy_cuts_fewer_edges_than_random_at_equal_budget() -> None:
    # ADR-0017 regression test: flow_greedy should keep a process chain together
    # under a sheet budget, so it should cut markedly fewer edges than the
    # random control at the same budget. This alone does not prove the fix is
    # depth-first rather than breadth-first (kg-construction.md open question
    # 9) -- see test_flow_order_is_depth_first_not_breadth_first for that.
    plant = make_plant_graph(chain_length=10, branches=6)
    budget = 3
    flow_config = SplitConfig(strategy="flow_greedy", sheet_equipment_budget=budget, seed=0)
    random_config = SplitConfig(strategy="random", sheet_equipment_budget=budget, seed=0)

    flow_sheet = STRATEGIES["flow_greedy"](plant, flow_config, random.Random(flow_config.seed))
    random_sheet = STRATEGIES["random"](plant, random_config, random.Random(random_config.seed))

    assert _count_cross_sheet_edges(plant, flow_sheet) < _count_cross_sheet_edges(
        plant, random_sheet
    )


def test_flow_order_is_depth_first_not_breadth_first() -> None:
    # Hand-built owner graph where breadth-first and depth-first orders
    # differ: breadth-first would visit level by level (feed, a, b, a1, b1);
    # depth-first walks chain "a" to its end before starting chain "b".
    owner_graph: nx.DiGraph[str] = nx.DiGraph()
    owner_graph.add_edges_from([("feed", "a"), ("feed", "b"), ("a", "a1"), ("b", "b1")])
    order = _flow_order(owner_graph, {"feed", "a", "b", "a1", "b1"})
    assert order == ["feed", "a", "a1", "b", "b1"]


def test_by_unit_raises_without_unit_id() -> None:
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class="CentrifugalPump", tag="P-1")
    plant.add_node("b", node_class="CentrifugalPump", tag="P-2")
    plant.add_edge("a", "b", relation="send_to")
    config = SplitConfig(strategy="by_unit", equipment_classes={"CentrifugalPump"})
    with pytest.raises(ValueError, match="by_unit needs unit_id"):
        STRATEGIES["by_unit"](plant, config, random.Random(config.seed))
