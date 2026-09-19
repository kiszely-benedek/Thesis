"""A connectors.py invariánsai: connector-fajta a relációból, látható csonk-feliratok.

Ezek a `split()`-en át tesztelnek, nem a privát segédfüggvényeken közvetlenül:
a splitter maga sosem ellenőrzi a sémát (az `relation` sztringet szó szerint
veszi), ezért egy kétcsomópontos, mesterséges gráf is elég a viselkedés
megfigyeléséhez (`plant-generator.md` §5, findings 2a-2c).
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.splitter import split


def _two_equipment_plant(relation: str, **edge_attrs: str) -> nx.DiGraph[str]:
    """Két, egymástól elvágandó berendezés, egyetlen köztük futó éllel."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class="CentrifugalPump", tag="P-1")
    plant.add_node("b", node_class="CentrifugalPump", tag="P-2")
    plant.add_edge("a", "b", relation=relation, **edge_attrs)
    return plant


def _stub_attrs(sheet: SheetGraph) -> dict[str, object]:
    """A lap egyetlen csonk-csomópontjának attribútumai.

    A teszt-fixture-ök egy csonkot tesznek le laponként.
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
