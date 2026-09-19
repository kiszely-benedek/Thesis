"""A gráf séma invariánsai: labels_for és a két validate_* függvény kézzel épített gráfokon."""

from __future__ import annotations

import networkx as nx

from plantgraph.graph import schema, validation


def _valid_plant() -> nx.DiGraph[str]:
    """Egy pumpa, egy szelep és egy műszer, mindegyik kötelező mezővel, két topológia-relációval."""
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
    plant.nodes["p1"]["node_class"] = "SteamTrap"
    violations = validation.validate_plant_graph(plant)
    # a rossz node_class a saját csomópontján és a rá illeszkedő éleken is
    # hibát jelez (bad_endpoint) — itt csak azt nézzük, hogy p1 maga jelentve van
    assert any(v.kind == "unknown_class" and v.subject == "p1" for v in violations)


def test_plant_graph_rejects_a_connector_node() -> None:
    # off-page connector csonkot csak a splitter tesz lapra — egy teljes
    # üzemgráfban ez séma-hiba, nem csak "ismeretlen osztály"
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
    plant.nodes["v1"]["tag"] = "P-101"  # ugyanaz, mint p1 tag-je
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
    # send_to célja csak berendezés/csővezeték lehet, egy műszer nem
    plant = _valid_plant()
    plant.add_edge("p1", "psgf1", relation="send_to")
    violations = validation.validate_plant_graph(plant)
    assert any(v.kind == "bad_endpoint" and v.subject == "p1->psgf1" for v in violations)


def test_sheet_graph_allows_a_reference_occurrence_with_only_tag_and_class() -> None:
    # azonosság-alapú kereszthivatkozás (splitter.md nyitott 3. kérdés): a
    # reference-előfordulás nem hordoz plant_id-t/unit_id-t
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
        schema.labels_for("SteamTrap")
    except ValueError as error:
        assert "SteamTrap" in str(error)
    else:
        raise AssertionError("expected labels_for to raise on an unknown node_class")
