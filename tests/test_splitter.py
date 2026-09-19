"""A szintetikus splitter invariánsai (splitter.md 4. fejezet).

A kerek-út a fő teszt: split() majd rejoin() pontosan visszaadja az eredeti
gráfot — csomópontokat, éleket és minden attribútumot. Ez minden négy
stratégiára és a duplication_rate mindkét ágára (0.0 és >0) lefut, mert a
csomópont-duplikáció miatt a rejoinnak az azonosság-csoportokat is vissza kell
olvasztania, mielőtt a gráfok összehasonlíthatók (splitter.md nyitott 3. kérdés).
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

from plant_fixtures import make_plant_graph
from plantgraph.benchmark.models import ConnectorPair
from plantgraph.benchmark.rejoin import rejoin
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.strategies import STRATEGIES
from plantgraph.graph.validation import validate_sheet_graph


def assert_graphs_equal(rejoined: nx.DiGraph, original: nx.DiGraph) -> None:
    """Csomópont- és élhalmaz, plusz minden attribútum egyezését ellenőrzi.

    Ez maga a round-trip invariáns definíciója.
    """
    assert set(rejoined.nodes) == set(original.nodes)
    for node_id, attrs in original.nodes(data=True):
        assert rejoined.nodes[node_id] == attrs, f"node {node_id} attributes differ"
    assert set(rejoined.edges) == set(original.edges)
    for source, target, attrs in original.edges(data=True):
        actual = rejoined.edges[source, target]
        assert actual == attrs, f"edge ({source}, {target}) attributes differ"


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_round_trip_reproduces_the_original_graph(
    strategy_name: str, duplication_rate: float
) -> None:
    plant = make_plant_graph(chain_length=6, branches=2, utility_fanout=6)
    config = SplitConfig(
        strategy=strategy_name,
        sheet_equipment_budget=2,
        seed=7,
        duplication_rate=duplication_rate,
    )
    sheets, manifest = split(plant, config)
    assert_graphs_equal(rejoin(sheets, manifest), plant)


def test_every_cross_sheet_edge_yields_exactly_one_pair_and_no_orphans() -> None:
    plant = make_plant_graph(chain_length=6, branches=2)
    # duplication_rate=0: minden lapok közötti él OPC-vel oldódik, nincs duplikáció
    config = SplitConfig(sheet_equipment_budget=2, seed=5)
    _, manifest = split(plant, config)

    node_sheet = STRATEGIES["flow_greedy"](plant, config, random.Random(config.seed))
    expected = sum(
        1 for source, target in plant.edges() if node_sheet[source] != node_sheet[target]
    )
    assert len(manifest.connector_pairs) == expected
    assert manifest.accounted_for()


def test_connector_tags_are_unique_within_a_sheet() -> None:
    plant = make_plant_graph(chain_length=6, branches=2)
    config = SplitConfig(sheet_equipment_budget=2, seed=5)
    sheets, _ = split(plant, config)
    for sheet in sheets:
        tags = [connector.tag for connector in sheet.connectors]
        assert len(tags) == len(set(tags)), f"duplicate connector tag on sheet {sheet.sheet_id}"


def test_connector_partner_references_resolve_on_the_other_sheet() -> None:
    plant = make_plant_graph(chain_length=6, branches=2)
    config = SplitConfig(sheet_equipment_budget=2, seed=5)
    sheets, _ = split(plant, config)
    by_sheet_and_tag = {
        (sheet.sheet_id, connector.tag): connector
        for sheet in sheets
        for connector in sheet.connectors
    }
    for sheet in sheets:
        for connector in sheet.connectors:
            partner = by_sheet_and_tag[(connector.partner_sheet_id, connector.partner_tag)]
            assert partner.partner_tag == connector.tag
            assert partner.partner_sheet_id == connector.sheet_id


def test_sheet_equipment_count_respects_the_budget_once_references_are_excluded() -> None:
    # A duplikált berendezések reference-előfordulásai szándékosan NEM számítanak
    # a lapkeretbe (splitter.md nyitott 3. kérdés) — ezért zárjuk ki őket itt.
    plant = make_plant_graph(chain_length=6, branches=2)
    budget = 3
    config = SplitConfig(sheet_equipment_budget=budget, seed=9, duplication_rate=0.3)
    sheets, manifest = split(plant, config)

    for sheet in sheets:
        reference_ids = {
            key.split(":", 1)[1]
            for group in manifest.identity_groups
            for key in group.references
            if key.startswith(f"{sheet.sheet_id}:")
        }
        equipment_count = sum(
            1
            for node_id, attrs in sheet.graph.nodes(data=True)
            if attrs.get("node_class") in config.equipment_classes and node_id not in reference_ids
        )
        assert equipment_count <= budget


def test_no_sheet_is_empty() -> None:
    plant = make_plant_graph()
    for strategy_name in STRATEGIES:
        config = SplitConfig(strategy=strategy_name, sheet_equipment_budget=2, seed=11)
        sheets, _ = split(plant, config)
        assert all(sheet.graph.number_of_nodes() > 0 for sheet in sheets)


def test_same_seed_produces_an_identical_manifest() -> None:
    plant = make_plant_graph(chain_length=6, branches=2)
    config = SplitConfig(sheet_equipment_budget=2, seed=13, duplication_rate=0.3)
    _, first = split(plant, config)
    _, second = split(plant, config)
    # created_at az egyetlen mező, ami mindig eltér (aktuális időbélyeg) — minden
    # más mezőnek pontosan egyeznie kell ugyanazzal a seeddel (splitter.md 2. fejezet).
    assert first.model_dump(exclude={"created_at"}) == second.model_dump(exclude={"created_at"})


def test_unknown_strategy_name_raises() -> None:
    plant = make_plant_graph()
    with pytest.raises(ValueError, match="unknown split strategy"):
        split(plant, SplitConfig(strategy="not-a-real-strategy"))


def test_plant_without_any_equipment_node_raises() -> None:
    plant = nx.DiGraph()
    plant.add_node("inst-1", node_class="instrument", tag="FT-1")
    with pytest.raises(ValueError, match="no node with node_class"):
        split(plant, SplitConfig())


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_every_sheet_graph_is_schema_valid(strategy_name: str) -> None:
    plant = make_plant_graph(chain_length=6, branches=2)
    # 'utility_header' nincs a sémában (plant_fixtures.py) — csak az
    # utility_aware stratégia teszteléséhez létezik, itt nem kell
    plant.remove_node("utility-steam")
    config = SplitConfig(strategy=strategy_name, sheet_equipment_budget=2, seed=15)
    sheets, _ = split(plant, config)
    for sheet in sheets:
        violations = validate_sheet_graph(sheet.graph)
        assert violations == [], f"sheet {sheet.sheet_id}: {violations}"


def test_rejoin_refuses_a_pair_without_an_original_edge() -> None:
    plant = make_plant_graph()
    sheets, manifest = split(plant, SplitConfig(sheet_equipment_budget=2, seed=1))
    broken = manifest.model_copy(
        update={"connector_pairs": [ConnectorPair(from_key="0:opc:0:0", to_key="1:opc:1:0")]}
    )
    with pytest.raises(ValueError, match="no original_edge"):
        rejoin(sheets, broken)
