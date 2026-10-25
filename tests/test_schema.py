"""Invariants of the graph schema: labels_for and the two validate_* functions, hand-built input."""

from __future__ import annotations

import networkx as nx

from plantgraph.graph import schema, validation


def _valid_plant() -> nx.DiGraph[str]:
    """A pump, a valve, and an instrument, each with required fields, two topology relations."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("p1", node_class="CentrifugalPump", tag="P-101", plant_id="p0", unit_id="u1")
    plant.add_node("v1", node_class="GlobeValve", tag="GV-101", plant_id="p0", unit_id="u1")
    plant.add_node(
        "psgf1",
        node_class="ProcessSignalGeneratingFunction",
        tag="FT-101",
        plant_id="p0",
        unit_id="u1",
    )
    plant.add_edge("p1", "v1", relation="send_to")
    plant.add_edge("p1", "psgf1", relation="measured_by")
    return plant


def test_valid_plant_graph_has_no_violations() -> None:
    assert validation.validate_plant_graph(_valid_plant()) == []


def test_plant_graph_rejects_an_unknown_node_class() -> None:
    plant = _valid_plant()
    plant.nodes["p1"]["node_class"] = "Silo"  # a pyDEXPI class outside the allowlist
    violations = validation.validate_plant_graph(plant)
    # the bad node_class flags a violation both on its own node and on the edges
    # touching it (bad_endpoint) — here we only check that p1 itself is reported
    assert any(v.kind == "unknown_class" and v.subject == "p1" for v in violations)


def test_plant_graph_rejects_a_connector_node() -> None:
    # an off-page connector stub is only placed by the splitter — in a full
    # plant graph it is a schema violation, not merely "unknown class"
    plant = _valid_plant()
    plant.add_node(
        "opc1", node_class="FlowOutPipeOffPageConnector", tag="X", plant_id="p0", unit_id="u1"
    )
    violations = validation.validate_plant_graph(plant)
    assert any(v.kind == "unknown_class" and v.subject == "opc1" for v in violations)


def test_plant_graph_reports_missing_required_properties() -> None:
    plant = _valid_plant()
    del plant.nodes["v1"]["unit_id"]
    violations = validation.validate_plant_graph(plant)
    assert violations == [
        validation.SchemaViolation(
            kind="missing_property", subject="v1", detail="missing required property 'unit_id'"
        )
    ]


def test_plant_graph_rejects_a_duplicate_tag() -> None:
    plant = _valid_plant()
    plant.nodes["v1"]["tag"] = "P-101"  # same as p1's tag
    violations = validation.validate_plant_graph(plant)
    assert [v.kind for v in violations] == ["duplicate_tag"]
    assert violations[0].subject == "v1"


def test_plant_graph_rejects_an_edge_with_unknown_relation() -> None:
    plant = _valid_plant()
    plant.edges["p1", "v1"]["relation"] = "flows_to"
    violations = validation.validate_plant_graph(plant)
    assert [v.kind for v in violations] == ["unknown_relation"]
    assert violations[0].subject == "p1->v1"


def test_plant_graph_rejects_a_bad_endpoint() -> None:
    # send_to's target can only be equipment/piping, never an instrument
    plant = _valid_plant()
    plant.add_edge("p1", "psgf1", relation="send_to")
    violations = validation.validate_plant_graph(plant)
    assert any(v.kind == "bad_endpoint" and v.subject == "p1->psgf1" for v in violations)


def test_sheet_graph_allows_a_reference_occurrence_with_only_tag_and_class() -> None:
    # identity-based cross-referencing (splitter.md open question 3): a
    # reference occurrence carries no plant_id/unit_id
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node("p1", node_class="CentrifugalPump", tag="P-101")
    assert validation.validate_sheet_graph(sheet) == []


def test_sheet_graph_allows_a_connector_node_with_its_own_required_properties() -> None:
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node("p1", node_class="CentrifugalPump", tag="P-101")
    sheet.add_node(
        "opc1",
        node_class="FlowOutPipeOffPageConnector",
        connector_number="SHEET-0-OPC-00",
        referenced_drawing_number="1",
    )
    sheet.add_edge("p1", "opc1", relation="send_to")
    assert validation.validate_sheet_graph(sheet) == []


def test_sheet_graph_reports_a_connector_missing_its_own_required_property() -> None:
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node(
        "opc1", node_class="FlowOutPipeOffPageConnector", connector_number="SHEET-0-OPC-00"
    )
    violations = validation.validate_sheet_graph(sheet)
    assert violations == [
        validation.SchemaViolation(
            kind="missing_property",
            subject="opc1",
            detail="missing required property 'referenced_drawing_number'",
        )
    ]


def test_sheet_graph_rejects_a_duplicate_tag_within_the_sheet() -> None:
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node("p1", node_class="CentrifugalPump", tag="P-101")
    sheet.add_node("p2", node_class="CentrifugalPump", tag="P-101")
    violations = validation.validate_sheet_graph(sheet)
    assert [v.kind for v in violations] == ["duplicate_tag"]


def test_labels_for_returns_the_curated_ancestor_chain() -> None:
    assert schema.labels_for("CentrifugalPump") == (
        "CentrifugalPump",
        "Pump",
        "Equipment",
        "TaggedPlantItem",
    )


def test_labels_for_raises_on_an_unknown_class() -> None:
    try:
        schema.labels_for("Silo")
    except ValueError as error:
        assert "Silo" in str(error)
    else:
        raise AssertionError("expected labels_for to raise on an unknown node_class")


def test_plant_graph_allows_an_actuator_with_no_tag_but_not_an_untagged_valve() -> None:
    plant = _valid_plant()
    plant.add_node("af1", node_class="ActuatingFunction", plant_id="p0", unit_id="u1")
    assert validation.validate_plant_graph(plant) == []

    del plant.nodes["v1"]["tag"]
    violations = validation.validate_plant_graph(plant)
    assert [(v.kind, v.subject) for v in violations] == [("missing_property", "v1")]


def test_sheet_graph_allows_an_actuator_with_no_tag_but_not_an_untagged_valve() -> None:
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node("af1", node_class="ActuatingFunction")
    assert validation.validate_sheet_graph(sheet) == []

    sheet.add_node("v1", node_class="GlobeValve")
    violations = validation.validate_sheet_graph(sheet)
    assert [(v.kind, v.subject) for v in violations] == [("missing_property", "v1")]


def test_untagged_classes_are_the_connectors_the_actuators_and_the_plain_pipe_parts() -> None:
    plain_pipe_parts = {
        "PipeTee", "PipeReducer", "BlindFlange", "LineBlind", "Flange", "FlangedConnection",
        "PipeCoupling", "ClampedFlangeCoupling", "Compensator", "Hose", "Funnel", "Penetration",
        "VentilationDevice", "PropertyBreak",
    }  # fmt: skip
    actuators = {"ActuatingFunction", "ActuatingElectricalFunction"}
    assert schema.UNTAGGED_CLASSES == schema.CONNECTOR_CLASSES | actuators | plain_pipe_parts


def _plant_with_machine_and_actuator(actuator_class: str) -> nx.DiGraph[str]:
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("p1", node_class="CentrifugalPump", tag="P-101", plant_id="p0", unit_id="u1")
    plant.add_node("a1", node_class=actuator_class, plant_id="p0", unit_id="u1")
    plant.add_edge("a1", "p1", relation="control")
    return plant


def test_an_electrical_actuator_may_control_a_machine() -> None:
    plant = _plant_with_machine_and_actuator("ActuatingElectricalFunction")
    assert validation.validate_plant_graph(plant) == []


def test_a_valve_actuator_may_not_control_a_machine() -> None:
    plant = _plant_with_machine_and_actuator("ActuatingFunction")
    violations = validation.validate_plant_graph(plant)
    assert [(v.kind, v.subject) for v in violations] == [("bad_endpoint", "a1->p1")]
    assert "ActuatingElectricalFunction" in violations[0].detail


def test_a_signal_connector_may_not_control_a_machine_and_is_reported_once() -> None:
    sheet = _plant_with_machine_and_actuator("FlowInSignalOffPageConnector")
    sheet.nodes["a1"].update(connector_number="C-1", referenced_drawing_number="2")
    violations = validation.validate_sheet_graph(sheet)
    assert [(v.kind, v.subject) for v in violations] == [("bad_endpoint", "a1->p1")]


def test_a_vessel_may_have_an_agitator_but_a_pump_may_not() -> None:
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class in (("t1", "Tank"), ("g1", "Agitator"), ("p1", "CentrifugalPump")):
        plant.add_node(node_id, node_class=node_class, tag=node_id, plant_id="p0", unit_id="u1")
    plant.add_edge("t1", "g1", relation="has_agitator")
    assert validation.validate_plant_graph(plant) == []

    plant.add_edge("p1", "g1", relation="has_agitator")
    violations = validation.validate_plant_graph(plant)
    assert [(v.kind, v.subject) for v in violations] == [("bad_endpoint", "p1->g1")]


def test_a_cascade_controller_chain_and_an_electrical_actuator_are_valid_signal_targets() -> None:
    plant: nx.DiGraph[str] = nx.DiGraph()
    chain = ("ProcessSignalGeneratingFunction", "ProcessControlFunction", "ProcessControlFunction")
    for index, node_class in enumerate((*chain, "ActuatingElectricalFunction")):
        plant.add_node(
            f"n{index}", node_class=node_class, tag=f"n{index}", plant_id="p0", unit_id="u"
        )
    for index in range(3):
        plant.add_edge(f"n{index}", f"n{index + 1}", relation="send_signal_to")
    assert validation.validate_plant_graph(plant) == []
