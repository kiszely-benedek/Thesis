"""A generátor és a splitter együtt (`plant-generator.md` §3.4 invariáns 7, 8)."""

from __future__ import annotations

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.rejoin import rejoin
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.strategies import STRATEGIES
from plantgraph.graph.validation import validate_sheet_graph


def _generated_plant(seed: int) -> nx.DiGraph[str]:
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


# ---- invariáns 7: kerek-út minden stratégiával -------------------------------------------------


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_split_then_rejoin_reproduces_the_generated_plant(strategy_name: str) -> None:
    plant = _generated_plant(seed=8)
    split_config = SplitConfig(strategy=strategy_name, sheet_equipment_budget=3, seed=0)
    sheets, manifest = split(plant, split_config)
    rejoined = rejoin(sheets, manifest)

    assert set(rejoined.nodes) == set(plant.nodes)
    for node_id, attrs in plant.nodes(data=True):
        assert rejoined.nodes[node_id] == attrs, f"node {node_id} attributes differ"
    assert set(rejoined.edges) == set(plant.edges)
    for source, target, attrs in plant.edges(data=True):
        assert rejoined.edges[source, target] == attrs, f"edge ({source}, {target}) differs"


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_every_sheet_of_a_generated_plant_is_schema_valid(strategy_name: str) -> None:
    plant = _generated_plant(seed=8)
    split_config = SplitConfig(strategy=strategy_name, sheet_equipment_budget=3, seed=0)
    sheets, _ = split(plant, split_config)
    for sheet in sheets:
        violations = validate_sheet_graph(sheet.graph)
        assert violations == [], f"sheet {sheet.sheet_id}: {violations}"


# ---- invariáns 8: a stratégiák valóban eltérnek -----------------------------------------------


def test_flow_greedy_and_modularity_partition_differently_on_at_least_one_seed() -> None:
    # ez magát a generátort teszteli, nem a splittert: ha ez elbukik, a
    # generátor topológiája túl szabályos ahhoz, hogy a két stratégia
    # szétváljon — meg kell állni és jelenteni, a generátort TILOS emiatt
    # hangolni (plant-generator.md §3.4 invariáns 8)
    found_a_difference = False
    for seed in range(5):
        plant = _generated_plant(seed=seed)
        flow_sheets, _ = split(
            plant, SplitConfig(strategy="flow_greedy", sheet_equipment_budget=2, seed=0)
        )
        modularity_sheets, _ = split(
            plant, SplitConfig(strategy="modularity", sheet_equipment_budget=2, seed=0)
        )
        if _partition(flow_sheets) != _partition(modularity_sheets):
            found_a_difference = True
            break
    assert found_a_difference, (
        "flow_greedy and modularity produced the same partition on seeds 0-4; "
        "the design says stop and report this, not tune the generator"
    )


def _partition(sheets: list[SheetGraph]) -> set[frozenset[str]]:
    """Egy particionálás sheet-sorszámtól független alakja: mely csomópontok kerültek egy lapra."""
    return {frozenset(sheet.graph.nodes) for sheet in sheets}
