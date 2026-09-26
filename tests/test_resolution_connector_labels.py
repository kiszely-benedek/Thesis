"""`read_connector_labels` — a csatlakozó-csomópontok kiolvasása (design `kg-construction.md` §5.1).

Csak a csomópont-attribútumokból és a hozzá kötött egyetlen élből dolgozik,
sosem a splitter `OffPageConnector`-modelljéből — az a válaszkulcs, amit
`localize()` már kiürített.
"""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.benchmark.models import ConnectorKind, Direction
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.connector_labels import read_connector_labels


def _sheet_with_one_stub(node_class: str, edge_direction: str, **extra: str) -> SheetGraph:
    """Egy laphoz egy csatlakozó-csomópontot és a hozzá kötött egyetlen élet ad.

    edge_direction "in" -> valaki a csonkba küld (FlowOut jellegű vágás), "out"
    -> a csonk küld tovább valakinek (FlowIn jellegű vágás) — pontosan úgy, ahogy
    `connectors.py:_cut_one_edge` felépíti a két oldalt.
    """
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node(
        "stub",
        node_class=node_class,
        connector_number="SHEET-0-OPC-00",
        referenced_drawing_number="1",
        line_number="PL-1",
        **extra,
    )
    graph.add_node("other", node_class="CentrifugalPump", tag="P-1")
    if edge_direction == "in":
        graph.add_edge("other", "stub", relation="send_to", line_number="PL-1")
    else:
        graph.add_edge("stub", "other", relation="send_to", line_number="PL-1")
    return SheetGraph(sheet_id="0", graph=graph)


@pytest.mark.parametrize(
    ("node_class", "edge_direction", "expected_direction", "expected_kind"),
    [
        ("FlowOutPipeOffPageConnector", "in", Direction.OUTGOING, ConnectorKind.PIPE),
        ("FlowInPipeOffPageConnector", "out", Direction.INCOMING, ConnectorKind.PIPE),
        ("FlowOutSignalOffPageConnector", "in", Direction.OUTGOING, ConnectorKind.SIGNAL),
        ("FlowInSignalOffPageConnector", "out", Direction.INCOMING, ConnectorKind.SIGNAL),
    ],
)
def test_direction_and_kind_come_from_the_node_class(
    node_class: str,
    edge_direction: str,
    expected_direction: Direction,
    expected_kind: ConnectorKind,
) -> None:
    sheet = _sheet_with_one_stub(node_class, edge_direction)
    (label,) = read_connector_labels(sheet)
    assert label.direction is expected_direction
    assert label.kind is expected_kind
    assert label.key == "0:stub"


def test_relation_comes_from_the_stub_edge_not_the_node() -> None:
    sheet = _sheet_with_one_stub("FlowOutPipeOffPageConnector", "in")
    (label,) = read_connector_labels(sheet)
    assert label.relation == "send_to"
    assert label.line_number == "PL-1"


def test_non_connector_nodes_are_ignored() -> None:
    sheet = _sheet_with_one_stub("FlowOutPipeOffPageConnector", "in")
    labels = read_connector_labels(sheet)
    assert {label.key for label in labels} == {"0:stub"}, "a 'other' berendezés nem csatlakozó"


def test_missing_referenced_connector_number_stays_none() -> None:
    """A `DRAWING_ONLY` dial nem ír fel partner-számot — a mező None marad, nem hiányzik."""
    sheet = _sheet_with_one_stub("FlowOutPipeOffPageConnector", "in")
    (label,) = read_connector_labels(sheet)
    assert label.referenced_connector_number is None


def test_referenced_connector_number_is_read_when_present() -> None:
    sheet = _sheet_with_one_stub(
        "FlowOutPipeOffPageConnector", "in", referenced_connector_number="SHEET-1-OPC-00"
    )
    (label,) = read_connector_labels(sheet)
    assert label.referenced_connector_number == "SHEET-1-OPC-00"


def test_connector_node_without_any_edge_raises() -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node(
        "stub",
        node_class="FlowOutPipeOffPageConnector",
        connector_number="A",
        referenced_drawing_number="1",
    )
    sheet = SheetGraph(sheet_id="0", graph=graph)
    with pytest.raises(ValueError, match="has 0 incident edges"):
        read_connector_labels(sheet)


def test_connector_node_with_two_edges_raises() -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node(
        "stub",
        node_class="FlowOutPipeOffPageConnector",
        connector_number="A",
        referenced_drawing_number="1",
    )
    graph.add_node("a", node_class="CentrifugalPump", tag="P-1")
    graph.add_node("b", node_class="CentrifugalPump", tag="P-2")
    graph.add_edge("a", "stub", relation="send_to")
    graph.add_edge("stub", "b", relation="send_to")
    sheet = SheetGraph(sheet_id="0", graph=graph)
    with pytest.raises(ValueError, match="has 2 incident edges"):
        read_connector_labels(sheet)
