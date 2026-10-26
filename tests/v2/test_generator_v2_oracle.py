"""The graph oracle builds a hand-written two-unit plan that the schema accepts."""

from __future__ import annotations

import pytest

from graph_plant_builder_v2 import GraphPlantBuilderV2
from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    InstrumentSpec,
    LineItemSpec,
    LineSpec,
    LinkSpec,
    PlantBuilderV2,
)
from plantgraph.benchmark.v2.tags import (
    format_equipment_tag,
    format_instrument_tag,
    format_valve_tag,
)
from plantgraph.graph.schema import Relation
from plantgraph.graph.validation import validate_plant_graph


def _equipment(
    node_id: str, node_class: str, unit: int, tag: str, motor: bool = False
) -> EquipmentSpec:
    return EquipmentSpec(
        node_id=node_id, node_class=node_class, unit_no=unit, tag=tag, has_motor=motor
    )


def _item(node_id: str, node_class: str, tag: str | None) -> LineItemSpec:
    return LineItemSpec(node_id=node_id, node_class=node_class, tag=tag)


def _instrument(
    node_id: str, node_class: str, tag: str | None, loop: str, variable: str
) -> InstrumentSpec:
    return InstrumentSpec(
        node_id=node_id,
        node_class=node_class,
        unit_no=1,
        tag=tag,
        loop_tag=loop,
        measured_variable=variable,
    )


def build_two_unit_plan(builder: PlantBuilderV2) -> None:
    """Unit 1: tank, motor pump, control valve with a flow loop, drain branch, hand switch.

    Unit 2: a reactor with an agitator, fed by the cross-unit line from unit 1.
    """
    builder.add_section(1, "TKF Feed tank")
    builder.add_section(2, "RXN Reactor")
    builder.add_equipment(_equipment("u1-eq1", "Tank", 1, format_equipment_tag("TK", 1, 1)))
    builder.add_equipment(
        _equipment("u1-eq2", "CentrifugalPump", 1, format_equipment_tag("P", 1, 1), motor=True)
    )
    builder.add_equipment(
        _equipment("u2-eq1", "PressureVessel", 2, format_equipment_tag("R", 2, 1))
    )
    builder.add_equipment(_equipment("u2-eq2", "Agitator", 2, format_equipment_tag("M", 2, 1)))

    suction = LineSpec(
        line_number="6-P-10001-A1A-N",
        fluid_code="P",
        unit_no=1,
        src_id="u1-eq1",
        dst_id="u1-eq2",
        items=(_item("u1-va1", "GateValve", format_valve_tag("GTV", 1, 1)),),
    )
    discharge = LineSpec(
        line_number="4-P-10002-A1A-N",
        fluid_code="P",
        unit_no=1,
        src_id="u1-eq2",
        dst_id="u2-eq1",
        items=(
            _item("u1-va2", "CheckValve", format_valve_tag("CHV", 1, 1)),
            _item("u1-fe1", "FlowMeasuringElement", format_instrument_tag("FE", 1, 14)),
            _item("u1-tp1", "PipeTee", None),
            _item("u1-va3", "GlobeValve", format_instrument_tag("FV", 1, 14)),
        ),
    )
    drain = LineSpec(  # a branch from the tee that ends open
        line_number="1-P-10003-A1A-N",
        fluid_code="P",
        unit_no=1,
        src_id="u1-tp1",
        dst_id=None,
        items=(_item("u1-va4", "GateValve", format_valve_tag("GTV", 1, 2)),),
    )
    utility = LineSpec(  # a cooling-water stub that starts open
        line_number="2-CWS-10004-A1A-N",
        fluid_code="CWS",
        unit_no=1,
        src_id=None,
        dst_id="u1-eq1",
        items=(_item("u1-va5", "GateValve", format_valve_tag("GTV", 1, 3)),),
    )
    for line in (suction, discharge, drain, utility):
        builder.add_line(line)

    loop = format_instrument_tag("FIC", 1, 14)
    builder.add_instrument(
        _instrument(
            "u1-in1",
            "ProcessSignalGeneratingFunction",
            format_instrument_tag("FT", 1, 14),
            loop,
            "F",
        )
    )
    builder.add_instrument(_instrument("u1-in2", "ProcessInstrumentationFunction", loop, loop, "F"))
    builder.add_instrument(_instrument("u1-in3", "ActuatingFunction", None, loop, "F"))
    builder.add_instrument(
        _instrument(
            "u1-in4",
            "ProcessInstrumentationFunction",
            format_instrument_tag("HS", 1, 15),
            "HS-1015",
            "H",
        )
    )
    builder.add_instrument(
        _instrument("u1-in5", "ActuatingElectricalFunction", None, "HS-1015", "H")
    )
    for relation, source, target in (
        (Relation.MEASURED_BY, "u1-fe1", "u1-in1"),
        (Relation.SEND_SIGNAL_TO, "u1-in1", "u1-in2"),
        (Relation.SEND_SIGNAL_TO, "u1-in2", "u1-in3"),
        (Relation.CONTROL, "u1-in3", "u1-va3"),
        (Relation.SEND_SIGNAL_TO, "u1-in4", "u1-in5"),
        (Relation.CONTROL, "u1-in5", "u1-eq2"),
        (Relation.HAS_AGITATOR, "u2-eq1", "u2-eq2"),
    ):
        builder.add_link(LinkSpec(relation=relation, source_id=source, target_id=target))


@pytest.fixture
def oracle() -> GraphPlantBuilderV2:
    builder = GraphPlantBuilderV2("plant0")
    build_two_unit_plan(builder)
    return builder


def _edges(oracle: GraphPlantBuilderV2, relation: Relation) -> set[tuple[str, str]]:
    graph = oracle.graph
    return {(s, t) for s, t, data in graph.edges(data=True) if data["relation"] == relation.value}


def test_the_plan_validates_against_the_schema(oracle: GraphPlantBuilderV2) -> None:
    assert validate_plant_graph(oracle.graph) == []


def test_node_count_and_units(oracle: GraphPlantBuilderV2) -> None:
    graph = oracle.graph
    assert graph.number_of_nodes() == 4 + 7 + 5  # equipment + line items + instruments
    assert {graph.nodes[n]["unit_id"] for n in graph.nodes if n.startswith("u2-")} == {"2"}
    assert graph.nodes["u1-va1"]["unit_id"] == "1"  # an inline item takes its line's unit
    assert oracle.section_names == {1: "TKF Feed tank", 2: "RXN Reactor"}


def test_send_to_chain_and_tee_branch(oracle: GraphPlantBuilderV2) -> None:
    assert _edges(oracle, Relation.SEND_TO) == {
        ("u1-eq1", "u1-va1"), ("u1-va1", "u1-eq2"),
        ("u1-eq2", "u1-va2"), ("u1-va2", "u1-fe1"), ("u1-fe1", "u1-tp1"),
        ("u1-tp1", "u1-va3"), ("u1-va3", "u2-eq1"),
        ("u1-tp1", "u1-va4"),  # branch; its open end adds no edge
        ("u1-va5", "u1-eq1"),  # open start adds no edge
    }  # fmt: skip
    edge = oracle.graph.edges["u1-va3", "u2-eq1"]
    assert (edge["line_number"], edge["fluid_code"]) == ("4-P-10002-A1A-N", "P")


def test_signal_actuation_and_agitator_edges(oracle: GraphPlantBuilderV2) -> None:
    assert _edges(oracle, Relation.MEASURED_BY) == {("u1-fe1", "u1-in1")}
    assert _edges(oracle, Relation.SEND_SIGNAL_TO) == {
        ("u1-in1", "u1-in2"), ("u1-in2", "u1-in3"), ("u1-in4", "u1-in5"),
    }  # fmt: skip
    assert _edges(oracle, Relation.CONTROL) == {("u1-in3", "u1-va3"), ("u1-in5", "u1-eq2")}
    assert _edges(oracle, Relation.HAS_AGITATOR) == {("u2-eq1", "u2-eq2")}


def test_untagged_parts_leave_the_tag_key_out(oracle: GraphPlantBuilderV2) -> None:
    assert "tag" not in oracle.graph.nodes["u1-tp1"]
    assert "tag" not in oracle.graph.nodes["u1-in3"]
    assert oracle.graph.nodes["u1-va3"]["tag"] == "FV-1014"


def test_duplicate_node_and_unknown_reference_raise() -> None:
    builder = GraphPlantBuilderV2("plant0")
    builder.add_equipment(_equipment("eq1", "Tank", 1, "TK-101"))
    with pytest.raises(ValueError, match="added twice"):
        builder.add_equipment(_equipment("eq1", "Tank", 1, "TK-102"))
    line = LineSpec(line_number="L", fluid_code="P", unit_no=1, src_id="eq1", dst_id="missing")
    with pytest.raises(ValueError, match="'missing', which was not added yet"):
        builder.add_line(line)
    with pytest.raises(ValueError, match="which was not added yet"):
        builder.add_link(LinkSpec(relation=Relation.CONTROL, source_id="eq1", target_id="nope"))
    assert builder.graph.number_of_nodes() == 1  # the failed line added nothing
