"""One micro model per construct, through the v2 adapter: no dropped node, the expected edges."""

from __future__ import annotations

from collections.abc import Callable

import networkx as nx
import pytest
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from plantgraph.adapters.pydexpi_adapter import ConversionReport
from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, GenerationRecordV2, PlantBuilderV2
from plantgraph.graph import schema, validation
from plantgraph.graph.schema import Relation
from v2_micro_plans import CONSTRUCT_PLANS, item, line, plan_base, plan_trip

_STRUCTURE = {"ProcessPlant", "PlantSection"}
Plan = Callable[[PlantBuilderV2], None]


def build(*plans: Plan) -> tuple[DexpiModel, nx.DiGraph[str], ConversionReport]:
    """Build `plan_base` plus `plans` on the DEXPI backend and map the model to the graph."""
    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    for plan in plans:
        plan(builder)
    model = builder.build()
    record = GenerationRecordV2(
        plant_id="plant0", seed=0, generator_config="{}", pydexpi_version="test"
    )
    graph, report = plant_graph_v2(model, record)
    return model, graph, report


def edges(graph: nx.DiGraph[str], relation: Relation) -> set[tuple[str, str]]:
    """The (source, target) pairs of one relation."""
    return {(s, t) for s, t, d in graph.edges(data=True) if d["relation"] == relation.value}


def assert_nothing_lost(graph: nx.DiGraph[str], report: ConversionReport) -> None:
    """Only the structural layer is dropped, every edge maps, the graph validates."""
    assert set(report.nodes_dropped_per_class) <= _STRUCTURE
    assert report.edges_dropped_per_label == {}
    assert validation.validate_plant_graph(graph) == []


@pytest.mark.parametrize("name", sorted(CONSTRUCT_PLANS))
def test_every_construct_loses_nothing(name: str) -> None:
    _, graph, report = build(CONSTRUCT_PLANS[name])
    assert_nothing_lost(graph, report)


def test_straight_line() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["straight"])
    assert edges(graph, Relation.SEND_TO) == {("eq1", "st-v1"), ("st-v1", "eq2")}


def test_branch_from_a_tee_keeps_the_split() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["branch"])
    assert edges(graph, Relation.SEND_TO) == {
        ("eq2", "br-v1"), ("br-v1", "br-t1"), ("br-t1", "br-v2"), ("br-v2", "eq3"),
        ("br-t1", "br-v3"),
    }  # fmt: skip
    assert graph.out_degree("br-v3") == 0  # the open end adds no edge and no node


def test_merge_into_a_tee_keeps_both_feeds() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["merge"])
    assert edges(graph, Relation.SEND_TO) == {
        ("mg-v1", "mg-t1"), ("mg-v2", "mg-t1"), ("mg-t1", "mg-v3"), ("mg-v3", "eq3"),
        ("eq1", "mg-v1"), ("eq2", "mg-v2"),
    }  # fmt: skip


def test_open_end_keeps_the_relief_valve_as_a_leaf() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["open_end"])
    assert edges(graph, Relation.SEND_TO) == {("eq4", "oe-v1"), ("oe-v1", "oe-psv")}
    assert graph.out_degree("oe-psv") == 0


def test_relief_valve_tag_is_read_from_position_number() -> None:
    model, graph, _ = build(CONSTRUCT_PLANS["open_end"])
    assert graph.nodes["oe-psv"]["tag"] == "PSV-1040"
    systems = model.conceptualModel.pipingNetworkSystems  # type: ignore[union-attr]
    relief = next(i for s in systems for g in s.segments for i in g.items if i.id == "oe-psv")
    assert relief.positionNumber == "PSV-1040"  # type: ignore[attr-defined]


def test_open_start_builds_and_keeps_the_edge_into_the_equipment() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["open_start"])
    assert edges(graph, Relation.SEND_TO) == {("os-v1", "eq1")}
    assert graph.in_degree("os-v1") == 0


def test_control_loop_edges() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["control_loop"])
    assert edges(graph, Relation.MEASURED_BY) == {("cl-fe", "cl-ft")}
    assert edges(graph, Relation.SEND_SIGNAL_TO) == {("cl-ft", "cl-fic"), ("cl-fic", "cl-af")}
    assert edges(graph, Relation.CONTROL) == {("cl-af", "cl-fv")}
    assert graph.nodes["cl-fv"]["tag"] == "FV-1014"
    assert "tag" not in graph.nodes["cl-af"]
    assert graph.nodes["cl-af"]["loop_tag"] == "FIC-1014"


def test_control_valve_gets_a_plain_actuator_and_no_positioner() -> None:
    model, _, _ = build(CONSTRUCT_PLANS["control_loop"])
    system = next(s for s in model.conceptualModel.actuatingSystems if s.id == "cl-af-as")  # type: ignore[union-attr]
    assert system.positioner is None
    assert system.controlledActuator is not None
    assert system.controlledActuator.subTagName is None


def test_sensor_on_an_equipment_nozzle() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["nozzle_sensing"])
    assert edges(graph, Relation.MEASURED_BY) == {("eq4", "ns-lt")}


def test_sensor_on_a_tap_keeps_the_branch_and_the_sensing_edge() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["taps"])
    assert ("tp-t1", "tp-bv") in edges(graph, Relation.SEND_TO)
    assert ("tp-bv", "tp-bf1") in edges(graph, Relation.SEND_TO)
    assert ("tp-t2", "tp-bf2") in edges(graph, Relation.SEND_TO)
    assert edges(graph, Relation.MEASURED_BY) == {("tp-bf1", "tp-pt"), ("tp-bf2", "tp-tt")}


def test_trip_solenoid_and_position_switch_on_the_valve() -> None:
    model, graph, _ = build(CONSTRUCT_PLANS["trip"])
    assert ("tr-xv", "tr-zso") in edges(graph, Relation.MEASURED_BY)
    assert ("tr-af", "tr-xv") in edges(graph, Relation.CONTROL)
    system = next(s for s in model.conceptualModel.actuatingSystems if s.id == "tr-af-as")  # type: ignore[union-attr]
    assert system.controlledActuator.subTagName == "XY-1030"  # type: ignore[union-attr]
    assert system.positioner is None


def test_a_y_train_gets_a_yy_solenoid() -> None:
    model, graph, _ = build(lambda b: plan_trip(b, "Y"))
    assert graph.nodes["tr-xv"]["tag"] == "YV-1030"
    system = next(s for s in model.conceptualModel.actuatingSystems if s.id == "tr-af-as")  # type: ignore[union-attr]
    assert system.controlledActuator.subTagName == "YY-1030"  # type: ignore[union-attr]


def test_hand_switch_drives_an_on_off_valve() -> None:
    _, graph, _ = build(CONSTRUCT_PLANS["hand_switch"])
    assert edges(graph, Relation.SEND_SIGNAL_TO) == {("hs-hs", "hs-af")}
    assert edges(graph, Relation.CONTROL) == {("hs-af", "hs-xv")}
    assert graph.nodes["hs-hs"]["tag"] == "HS-1031"


def test_local_instrument_is_one_node_and_its_own_loop() -> None:
    model, graph, report = build(CONSTRUCT_PLANS["local_instrument"])
    assert report.carrier_functions_folded == 1
    assert edges(graph, Relation.MEASURED_BY) == {("eq4", "li-pi")}
    assert graph.degree("li-pi") == 1  # type: ignore[operator]
    assert graph.nodes["li-pi"]["loop_tag"] == "PI-1021"
    assert graph.nodes["li-pi"]["measured_variable"] == "P"
    assert "li-pi-carrier" in {p.id for p in model.conceptualModel.processInstrumentationFunctions}  # type: ignore[union-attr]


def test_line_list_fields_are_on_the_piping_network_system() -> None:
    model, _, _ = build(CONSTRUCT_PLANS["straight"])
    system = model.conceptualModel.pipingNetworkSystems[0]  # type: ignore[union-attr]
    assert system.lineNumber == "4-P-10001-A1A-N"
    assert (system.fluidCode, system.pipingClassCode) == ("P", "A1A")
    assert (system.nominalDiameterRepresentation, system.insulationType) == ("4", "N")


def test_inline_parts_take_the_unit_of_their_line() -> None:
    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    builder.add_section(2, "RXN Reactor")
    valve = item("u2-v1", "GateValve", "GTV-2001")
    builder.add_line(line(1, "eq1", (valve,), "eq2", unit=2))
    record = GenerationRecordV2(plant_id="p", seed=0, generator_config="{}", pydexpi_version="t")
    graph, _ = plant_graph_v2(builder.build(), record)
    assert graph.nodes["u2-v1"]["unit_id"] == "2"
    assert graph.nodes["eq1"]["unit_id"] == "1"


def _vocabulary_cases() -> list[tuple[str, str]]:
    equipment = [(name, "equipment") for name in sorted(schema.EQUIPMENT_CLASSES)]
    # PropertyBreak (kind "break") is refused until V2-T5
    piping = [(name, "piping") for name in sorted(schema.PIPING_CLASSES - schema.BREAK_CLASSES)]
    return equipment + piping


@pytest.mark.parametrize(("node_class", "category"), _vocabulary_cases())
def test_every_schema_class_builds_and_maps_to_itself(node_class: str, category: str) -> None:
    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    tag = None if node_class in schema.UNTAGGED_CLASSES else "TAG-1001"
    if category == "equipment":
        spec = EquipmentSpec(node_id="x", node_class=node_class, unit_no=1, tag="X-101")
        builder.add_equipment(spec)
        tag = "X-101"
    else:
        builder.add_line(line(1, "eq1", (item("x", node_class, tag),), "eq2"))
    record = GenerationRecordV2(plant_id="p", seed=0, generator_config="{}", pydexpi_version="t")
    graph, report = plant_graph_v2(builder.build(), record)
    assert set(report.nodes_dropped_per_class) <= _STRUCTURE
    assert graph.nodes["x"]["node_class"] == node_class
    assert graph.nodes["x"].get("tag") == tag
