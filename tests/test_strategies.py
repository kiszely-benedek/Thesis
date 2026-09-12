"""A négy particionáló stratégia invariánsai: csomópont-lefedés, lapkeret, együtt utazó műszerek."""

from __future__ import annotations

import random

import pytest

from plant_fixtures import make_plant_graph
from plantgraph.benchmark.models import SplitConfig
from plantgraph.benchmark.strategies import STRATEGIES


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
    # Design-döntés (splitter.md nyitott 2. kérdés): a műszer nem számít a
    # lapkeretbe, de a lapja meg kell egyezzen azzal a berendezéssel, amelyikre kötve van.
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
    # Az utility fejvezeték csak akkor kap saját hub-lapot, ha maga is
    # "berendezésnek" számít — ezért itt bővítjük az equipment_classes-t.
    plant = make_plant_graph(chain_length=3, branches=3, utility_fanout=6)
    config = SplitConfig(
        strategy="utility_aware",
        sheet_equipment_budget=2,
        seed=3,
        equipment_classes={"vessel", "pump", "exchanger", "column", "tank", "utility_header"},
    )
    node_sheet = STRATEGIES["utility_aware"](plant, config, random.Random(config.seed))

    hub_sheet = node_sheet["utility-steam"]
    hub_sheet_members = {
        node_id for node_id, sheet_id in node_sheet.items() if sheet_id == hub_sheet
    }
    # a hub-lap csak az utility fejvezetéket (és a rá kötött, nem-berendezés
    # csomópontokat, ha lenne) tartalmazza, a folyamatláncot nem
    assert "eq-0-0" not in hub_sheet_members
