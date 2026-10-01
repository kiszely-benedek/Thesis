"""Invariants of connectors.py: connector kind derived from the relation, visible stub labels.

These test through `split()`, not the private helper functions directly: the
splitter itself never validates the schema (it takes the `relation` string
literally), so a two-node synthetic graph is enough to observe the behaviour
(`plant-generator.md` §5, findings 2a-2c).
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import OffPageConnector
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.splitter import split


def _two_equipment_plant(relation: str, **edge_attrs: str) -> nx.DiGraph[str]:
    """Two pieces of equipment meant to be split apart, joined by a single edge."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class="CentrifugalPump", tag="P-1")
    plant.add_node("b", node_class="CentrifugalPump", tag="P-2")
    plant.add_edge("a", "b", relation=relation, **edge_attrs)
    return plant


def _stub_attrs(sheet: SheetGraph) -> dict[str, object]:
    """Attributes of the sheet's single connector-stub node.

    The test fixtures place exactly one stub per sheet.
    """
    connector = sheet.connectors[0]
    return dict(sheet.graph.nodes[connector.attached_node_id])


def _split_two_equipment(
    plant: nx.DiGraph[str], **config_kwargs: object
) -> tuple[SheetGraph, SheetGraph]:
    sheets, _ = split(
        plant,
        SplitConfig(
            sheet_equipment_budget=1, equipment_classes={"CentrifugalPump"}, **config_kwargs
        ),
    )
    by_id = {sheet.sheet_id: sheet for sheet in sheets}
    return by_id["0"], by_id["1"]


def test_a_cut_send_to_edge_becomes_a_pipe_connector() -> None:
    plant = _two_equipment_plant("send_to")
    sheet_a, sheet_b = _split_two_equipment(plant)
    assert _stub_attrs(sheet_a)["node_class"] == "FlowOutPipeOffPageConnector"
    assert _stub_attrs(sheet_b)["node_class"] == "FlowInPipeOffPageConnector"


def test_a_cut_non_send_to_edge_becomes_a_signal_connector() -> None:
    plant = _two_equipment_plant("measured_by")
    sheet_a, sheet_b = _split_two_equipment(plant)
    assert _stub_attrs(sheet_a)["node_class"] == "FlowOutSignalOffPageConnector"
    assert _stub_attrs(sheet_b)["node_class"] == "FlowInSignalOffPageConnector"


def test_stub_node_carries_its_own_and_the_partners_visible_labels() -> None:
    plant = _two_equipment_plant("send_to", line_number="PL-100", fluid_code="PL")
    sheet_a, sheet_b = _split_two_equipment(plant)

    attrs_a = _stub_attrs(sheet_a)
    connector_a = sheet_a.connectors[0]
    assert attrs_a["connector_number"] == connector_a.tag
    assert attrs_a["referenced_drawing_number"] == connector_a.partner_sheet_id
    assert attrs_a["referenced_connector_number"] == connector_a.partner_tag
    assert attrs_a["line_number"] == "PL-100"
    assert attrs_a["fluid_code"] == "PL"


def test_drawing_only_detail_omits_the_referenced_connector_number() -> None:
    plant = _two_equipment_plant("send_to")
    sheet_a, _ = _split_two_equipment(
        plant, connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY
    )
    assert "referenced_connector_number" not in _stub_attrs(sheet_a)


def test_signal_stubs_and_connectors_carry_the_source_loop_tag() -> None:
    plant = _two_equipment_plant("measured_by")
    plant.nodes["a"]["loop_tag"] = "FIC-101"
    sheet_a, sheet_b = _split_two_equipment(plant)

    assert _stub_attrs(sheet_a)["loop_tag"] == "FIC-101"
    assert _stub_attrs(sheet_b)["loop_tag"] == "FIC-101"
    assert sheet_a.connectors[0].loop_tag == "FIC-101"
    assert sheet_b.connectors[0].loop_tag == "FIC-101"


def test_signal_loop_tag_falls_back_to_the_target_node() -> None:
    plant = _two_equipment_plant("measured_by")
    plant.nodes["b"]["loop_tag"] = "TIC-202"
    sheet_a, _ = _split_two_equipment(plant)

    assert _stub_attrs(sheet_a)["loop_tag"] == "TIC-202"


def test_pipe_stubs_carry_no_loop_tag_even_if_the_nodes_have_one() -> None:
    plant = _two_equipment_plant("send_to", line_number="PL-100")
    plant.nodes["a"]["loop_tag"] = "FIC-101"
    sheet_a, sheet_b = _split_two_equipment(plant)

    assert "loop_tag" not in _stub_attrs(sheet_a)
    assert sheet_a.connectors[0].loop_tag is None
    assert sheet_b.connectors[0].loop_tag is None


def test_off_page_connector_with_a_loop_tag_round_trips_through_json() -> None:
    plant = _two_equipment_plant("measured_by")
    plant.nodes["a"]["loop_tag"] = "FIC-101"
    sheet_a, _ = _split_two_equipment(plant)

    connector = sheet_a.connectors[0]
    restored = OffPageConnector.model_validate_json(connector.model_dump_json())
    assert restored == connector
