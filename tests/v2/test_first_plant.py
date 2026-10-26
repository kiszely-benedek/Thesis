"""The first v2 plant end to end: grammar -> patterns -> sheets -> DEXPI -> schema graph."""

from __future__ import annotations

import networkx as nx
from instrument_invariants import check_s4, check_s7, check_s8, check_s9
from pattern_checks import assert_line_numbers_unique_and_valid
from plant_v2 import generated, graph_of
from trim_harness import TeeBuilder, project

from graph_plant_builder_v2 import GraphPlantBuilderV2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.benchmark.v2.flowsheet import Slot
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.graph import validation
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation

SEED, UNITS = 3, 20


def test_nothing_is_dropped_and_the_graph_validates() -> None:
    graph, report = graph_of(SEED, UNITS)
    assert set(report.nodes_dropped_per_class) <= {"ProcessPlant", "PlantSection"}
    assert report.edges_dropped_per_label == {}
    assert validation.validate_plant_graph(graph) == []


def test_the_plant_is_weakly_connected() -> None:
    graph, _ = graph_of(SEED, UNITS)
    assert nx.is_weakly_connected(graph)


def test_the_dexpi_graph_equals_the_oracle_graph() -> None:
    """The same plan written to the test oracle gives the same nodes and edges."""
    plan = generated(SEED, UNITS).plan
    oracle, dexpi = GraphPlantBuilderV2("plant0"), DexpiPlantBuilderV2("plant0")
    plan.write(TeeBuilder(oracle, dexpi))
    graph, _ = graph_of(SEED, UNITS)
    expected_nodes, expected_edges = project(oracle.graph)
    nodes, edges = project(graph)
    assert nodes == expected_nodes and edges == expected_edges


def test_every_joined_pair_of_units_has_its_cross_unit_edge() -> None:
    plant = generated(SEED, UNITS)
    graph, _ = graph_of(SEED, UNITS)
    crossing = [
        (s, t)
        for s, t, d in graph.edges(data=True)
        if d["relation"] == Relation.SEND_TO.value
        and graph.nodes[s]["unit_id"] != graph.nodes[t]["unit_id"]
    ]
    kinds = plant.record.stream_kind
    cross_lines = [n for n, kind in kinds.items() if kind is StreamKindV2.CROSS_UNIT]
    assert len(crossing) == len(cross_lines) == UNITS - 1  # a chain: one join per later unit
    for _, target in crossing:  # the target is the first part of the in-port line
        assert graph.nodes[target]["unit_id"] != ""


def test_gas_never_feeds_a_liquid_inlet() -> None:
    """S12: a cross-unit stream leaves a liquid out-port (vapour outlets stay open stubs)."""
    plant = generated(SEED, UNITS)
    joined = {
        port.node_id
        for unit in plant.plan.units
        for port in unit.instance.ports
        if port.name == "vapour"
    }
    graph, _ = graph_of(SEED, UNITS)
    for source in joined:
        downstream = [t for _, t in graph.out_edges(source)]
        assert all(graph.nodes[t]["unit_id"] == graph.nodes[source]["unit_id"] for t in downstream)


def test_line_numbers_are_unique_over_the_whole_plant() -> None:
    plan = generated(SEED, UNITS).plan
    assert_line_numbers_unique_and_valid(
        tuple(line for unit in plan.units for line in unit.instance.plan.lines)
    )


def test_the_instrument_invariants_hold_over_the_plant() -> None:
    graph, _ = graph_of(SEED, UNITS)
    model = generated(SEED, UNITS).model
    solenoid_of = {
        system.operatedValveReference.valve.id: (
            system.controlledActuator.subTagName if system.controlledActuator else None
        )
        for system in model.conceptualModel.actuatingSystems
    }
    assert check_s4(graph) > 20 and check_s7(graph, solenoid_of) > 5
    assert check_s8(graph) > 100 and check_s9(graph) > 500


def test_every_node_has_role_group_and_sheet_and_the_gold_keys_are_the_nodes() -> None:
    plant = generated(SEED, UNITS)
    graph, _ = graph_of(SEED, UNITS)
    assert set(plant.record.node_gold) == set(graph.nodes)
    for node_id, attrs in graph.nodes(data=True):
        assert attrs["role"] and attrs["drawing_group"] and attrs["sheet_group"], node_id
        assert attrs["sheet_group"].split(":")[0] == attrs["unit_id"], node_id  # one unit a sheet


def test_the_record_describes_the_plan() -> None:
    plant = generated(SEED, UNITS)
    record = plant.record
    assert [u.pattern for u in record.units] == [u.instance.pattern for u in plant.plan.units]
    assert record.open_stub_count == plant.plan.open_stub_count > 0
    assert record.feed_farm_fill_count == 0
    assert len(record.trains) == plant.plan.units[-1].slot.train_no
    assert plant.plan.units[0].slot.slot is Slot.FEED_FARM
    equipment_tags = {tag for tag, kind in record.item_kind.items() if kind.value == "equipment"}
    graph, _ = graph_of(SEED, UNITS)
    assert equipment_tags == {
        d["tag"] for _, d in graph.nodes(data=True) if d["node_class"] in EQUIPMENT_CLASSES
    }
