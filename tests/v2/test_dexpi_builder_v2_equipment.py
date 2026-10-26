"""Motors, agitators, electrical actuators and property breaks: the measured pyDEXPI probe.

Design generator-v2-pid-vocabulary.md section 2 (the probe), invariants S19 and S21, and every
refusal the builder makes for these constructs.
"""

from __future__ import annotations

import networkx as nx
import pydexpi.dexpi_classes.pydantic_classes as dexpi
import pytest
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from plantgraph.adapters.pydexpi_adapter import (
    abstract_conceptual_graph,
    load_complete_graph,
    map_conceptual_graph,
)
from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.adapters.pydexpi_builder_v2_equipment import can_have_motor, motor_tag
from plantgraph.adapters.pydexpi_rules_v2 import uses_v2_rules, v2_relation_of
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, GenerationRecordV2
from plantgraph.graph import schema, validation
from plantgraph.graph.schema import Relation
from v2_micro_plans import (
    CONSTRUCT_PLANS,
    instrument,
    item,
    line,
    link,
    motor_pump,
    plan_base,
)

_RECORD = GenerationRecordV2(plant_id="plant0", seed=0, generator_config="{}", pydexpi_version="t")
_MACHINE_PLANS = ("motor_start", "speed_control", "agitator")
_AEF = "ActuatingElectricalFunction"


def _built(*plan_names: str) -> tuple[DexpiModel, nx.DiGraph[str]]:
    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    for name in plan_names:
        CONSTRUCT_PLANS[name](builder)
    model = builder.build()
    return model, plant_graph_v2(model, _RECORD)[0]


def _base() -> DexpiPlantBuilderV2:
    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    return builder


def _edges(graph: nx.DiGraph[str], relation: Relation) -> set[tuple[str, str]]:
    return {(s, t) for s, t, d in graph.edges(data=True) if d["relation"] == relation.value}


# ---- the probe: what pyDEXPI keeps and drops ----------------------------------------------------


def test_motor_start_is_hand_switch_to_actuator_to_pump() -> None:
    _, graph = _built("motor_start")
    assert _edges(graph, Relation.SEND_SIGNAL_TO) == {("ms-hs", "ms-aef")}
    assert _edges(graph, Relation.CONTROL) == {("ms-aef", "ms-p")}
    assert _edges(graph, Relation.MEASURED_BY) == {("ms-p", "ms-yi")}
    assert graph.nodes["ms-aef"]["loop_tag"] == "HS-1040"  # joins the loop of its hand switch
    assert "tag" not in graph.nodes["ms-aef"]


def test_speed_control_runs_through_a_controller_class() -> None:
    _, graph = _built("speed_control")
    assert graph.nodes["sc-pic"]["node_class"] == "ProcessControlFunction"
    assert _edges(graph, Relation.SEND_SIGNAL_TO) == {("sc-pt", "sc-pic"), ("sc-pic", "sc-aef")}
    assert _edges(graph, Relation.CONTROL) == {("sc-aef", "sc-p")}


def test_agitator_is_a_node_with_a_has_agitator_edge_from_its_vessel() -> None:
    _, graph = _built("agitator")
    assert _edges(graph, Relation.HAS_AGITATOR) == {("eq4", "ag-m")}
    assert graph.nodes["ag-m"]["node_class"] == "Agitator"
    assert graph.degree("ag-m") == 1  # type: ignore[operator]


def test_property_break_is_an_inline_node_on_the_flow_path() -> None:
    _, graph = _built("property_break")
    assert _edges(graph, Relation.SEND_TO) >= {("pb-v1", "pb-br"), ("pb-br", "pb-v2")}
    assert graph.nodes["pb-br"]["node_class"] == "PropertyBreak"
    assert "tag" not in graph.nodes["pb-br"]


def test_motor_components_stay_in_the_file_and_leave_the_graph() -> None:
    model, graph = _built(*_MACHINE_PLANS)
    complete_labels = {a["label"] for _, a in load_complete_graph(model).nodes(data=True)}
    conceptual_labels = {
        a["label"]
        for _, a in abstract_conceptual_graph(load_complete_graph(model)).nodes(data=True)
    }
    assert {"AlternatingCurrentMotorAsComponent", "GearBox"} <= complete_labels
    assert not {"AlternatingCurrentMotorAsComponent", "GearBox"} & conceptual_labels
    assert {"ms-p-motor", "ms-p-nz1"}.isdisjoint(graph.nodes)


@pytest.mark.parametrize("name", [*_MACHINE_PLANS, "property_break"])
def test_nothing_is_lost_or_invalid(name: str) -> None:
    builder = _base()
    CONSTRUCT_PLANS[name](builder)
    graph, report = plant_graph_v2(builder.build(), _RECORD)
    assert set(report.nodes_dropped_per_class) <= {"ProcessPlant", "PlantSection"}
    assert report.edges_dropped_per_label == {}
    assert validation.validate_plant_graph(graph) == []


# ---- S19: control into equipment comes from an AEF -----------------------------------------------


def test_s19_every_machine_control_comes_from_an_actuator_with_a_signal_source() -> None:
    _, graph = _built(*_MACHINE_PLANS)
    into_equipment = [
        (s, t)
        for s, t in _edges(graph, Relation.CONTROL)
        if graph.nodes[t]["node_class"] in schema.EQUIPMENT_CLASSES
    ]
    assert into_equipment
    assert all(graph.nodes[s]["node_class"] == _AEF for s, _ in into_equipment)
    actuators = [n for n, d in graph.nodes(data=True) if d["node_class"] == _AEF]
    for actuator in actuators:
        controls = [
            t for _, t, d in graph.out_edges(actuator, data=True) if d["relation"] == "control"
        ]
        feeds = [
            s
            for s, _, d in graph.in_edges(actuator, data=True)
            if d["relation"] == "send_signal_to"
        ]
        assert len(controls) == 1
        assert len(feeds) >= 1


# ---- S21: one sub-tagged motor per motor-driven machine ------------------------------------------


def test_s21_each_motor_driven_machine_has_one_motor_with_its_number() -> None:
    model, _ = _built(*_MACHINE_PLANS)
    machines = {m.id: m for m in model.conceptualModel.taggedPlantItems}  # type: ignore[union-attr]
    for node_id in ("ms-p", "sc-p", "ag-m"):
        (motor,) = machines[node_id].motors
        assert motor.subTagName == motor_tag(machines[node_id].tagName)  # type: ignore[arg-type]
        assert isinstance(motor, dexpi.AlternatingCurrentMotorAsComponent)
    assert machines["eq2"].motors == []  # a pump with no has_motor gets none


def test_motor_tag_inserts_an_m_after_the_equipment_letters() -> None:
    assert motor_tag("P-1203A") == "PM-1203A"
    assert motor_tag("K-2101") == "KM-2101"
    with pytest.raises(ValueError, match="equipment tag"):
        motor_tag("P1203")


def test_agitator_and_rotary_mixer_motors_come_with_a_gear_box() -> None:
    model, _ = _built("agitator", "motor_start")
    machines = {m.id: m for m in model.conceptualModel.taggedPlantItems}  # type: ignore[union-attr]
    assert len(machines["ag-m"].gearBoxes) == 1
    assert machines["ms-p"].gearBoxes == []


def test_only_machines_a_motor_drives_can_have_one() -> None:
    assert [can_have_motor(c) for c in ("CentrifugalPump", "RotaryCompressor", "Agitator")] == [
        True
    ] * 3
    assert not any(can_have_motor(c) for c in ("EjectorPump", "AirEjector", "Tank", "Furnace"))


# ---- the electrical actuator points at a dedicated nozzle of its machine -------------------------


def test_the_actuator_acts_on_a_nozzle_of_its_machine() -> None:
    model, _ = _built("motor_start")
    machine = next(m for m in model.conceptualModel.taggedPlantItems if m.id == "ms-p")  # type: ignore[union-attr]
    actuator = next(
        p
        for p in model.conceptualModel.processInstrumentationFunctions  # type: ignore[union-attr]
        if p.id == "ms-hs"
    ).actuatingElectricalFunctions[0]
    assert actuator.actuatingElectricalLocation in machine.nozzles


# ---- adapter rules, gated by the vocabulary ------------------------------------------------


def test_the_v2_rules_apply_only_to_a_vocabulary_wider_than_v1() -> None:
    assert not uses_v2_rules(schema.V1_IMPORTABLE_CLASSES)
    assert uses_v2_rules(schema.V2_IMPORTABLE_CLASSES)


@pytest.mark.parametrize(
    ("attr_name", "relation"),
    [("agitator", Relation.HAS_AGITATOR), ("actuatingElectricalLocation", Relation.CONTROL)],
)
def test_reference_edges_map_to_their_relation(attr_name: str, relation: Relation) -> None:
    assert v2_relation_of({"label": "reference", "attr_name": attr_name}) == (relation, False)


def test_other_edges_are_not_a_v2_rule() -> None:
    assert v2_relation_of({"label": "reference", "attr_name": "sensingLocation"}) is None
    assert (
        v2_relation_of({"label": "composition", "attr_name": "actuatingElectricalFunctions"})
        is None
    )


def test_the_v1_vocabulary_keeps_agitator_and_actuator_out_of_the_graph() -> None:
    model, _ = _built(*_MACHINE_PLANS)
    conceptual = abstract_conceptual_graph(load_complete_graph(model))
    graph, report = map_conceptual_graph(conceptual, "plant0", {})
    assert Relation.HAS_AGITATOR.value not in report.edges_mapped_per_relation
    assert _AEF not in {d["node_class"] for _, d in graph.nodes(data=True)}


# ---- refusals ------------------------------------------------------------------------------------


def test_has_motor_on_a_class_no_motor_drives_raises() -> None:
    spec = EquipmentSpec(node_id="x", node_class="Tank", unit_no=1, tag="TK-109", has_motor=True)
    with pytest.raises(ValueError, match="expected a pump, compressor, agitator"):
        _base().add_equipment(spec)


def test_electrical_actuator_refusals() -> None:
    builder = _base()
    with pytest.raises(ValueError, match="carries no tag"):
        builder.add_instrument(instrument("bad", _AEF, "HS-1001", "HS-1001"))
    motor_pump(builder, "p", 50)
    builder.add_instrument(instrument("hs", "ProcessInstrumentationFunction", "HS-1002", "HS-1002"))
    builder.add_instrument(instrument("aef", _AEF, None, "HS-1002"))
    with pytest.raises(ValueError, match="motor-driven machine"):
        link(builder, Relation.CONTROL, "aef", "eq2")  # eq2 has no motor
    with pytest.raises(ValueError, match="acts on no machine"):
        builder.build()
    link(builder, Relation.CONTROL, "aef", "p")
    with pytest.raises(ValueError, match="no signal source"):
        builder.build()
    link(builder, Relation.SEND_SIGNAL_TO, "hs", "aef")
    builder.build()  # now complete
    with pytest.raises(ValueError, match="already acts on a machine"):
        link(builder, Relation.CONTROL, "aef", "p")


def test_a_valve_actuator_may_not_drive_a_machine() -> None:
    builder = _base()
    motor_pump(builder, "p", 50)
    builder.add_instrument(instrument("af", "ActuatingFunction", None, "FIC-1001"))
    with pytest.raises(ValueError, match="control valve body"):
        link(builder, Relation.CONTROL, "af", "p")


def test_agitator_link_refusals() -> None:
    builder = _base()
    builder.add_equipment(
        EquipmentSpec(node_id="ag", node_class="Agitator", unit_no=1, tag="M-101")
    )
    with pytest.raises(ValueError, match="vessel or heat exchanger"):
        link(builder, Relation.HAS_AGITATOR, "eq2", "ag")  # a pump owns no agitator
    with pytest.raises(ValueError, match="expected an Agitator"):
        link(builder, Relation.HAS_AGITATOR, "eq4", "eq3")
    with pytest.raises(ValueError, match="expected added equipment"):
        link(builder, Relation.HAS_AGITATOR, "eq4", "nope")
    link(builder, Relation.HAS_AGITATOR, "eq4", "ag")
    with pytest.raises(ValueError, match="already stirs another vessel"):
        link(builder, Relation.HAS_AGITATOR, "eq1", "ag")


def test_a_property_break_cannot_be_sensed() -> None:
    builder = _base()
    builder.add_line(line(1, "eq1", (item("br", "PropertyBreak"),), "eq2"))
    builder.add_instrument(instrument("t", "ProcessSignalGeneratingFunction", "PI-1001", "PI-1001"))
    with pytest.raises(ValueError, match="cannot sense"):
        link(builder, Relation.MEASURED_BY, "br", "t")
