"""`read_connector_labels` — reading connector nodes (design `kg-construction.md` §5.1).

Works only from the node attributes and the single edge attached to it, never
from the splitter's `OffPageConnector` model — that is the answer key, already
emptied out by `localize()`.
"""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.benchmark.models import ConnectorKind, Direction
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.connector_labels import read_connector_labels


def _sheet_with_one_stub(node_class: str, edge_direction: str, **extra: str) -> SheetGraph:
    """Give a sheet one connector node plus the single edge attached to it.

    edge_direction "in" -> someone sends into the stub (a FlowOut-style cut),
    "out" -> the stub sends on to someone (a FlowIn-style cut) — exactly how
    `connectors.py:_cut_one_edge` builds the two sides.
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
    labels, unresolved = read_connector_labels(sheet)
    assert unresolved == []
    (label,) = labels
    assert label.direction is expected_direction
    assert label.kind is expected_kind
    assert label.key == "0:stub"


def test_relation_comes_from_the_stub_edge_not_the_node() -> None:
    sheet = _sheet_with_one_stub("FlowOutPipeOffPageConnector", "in")
    labels, _unresolved = read_connector_labels(sheet)
    (label,) = labels
    assert label.relation == "send_to"
    assert label.line_number == "PL-1"


def test_non_connector_nodes_are_ignored() -> None:
    sheet = _sheet_with_one_stub("FlowOutPipeOffPageConnector", "in")
    labels, _unresolved = read_connector_labels(sheet)
    assert {label.key for label in labels} == {"0:stub"}, "the 'other' equipment is not a connector"


def test_missing_referenced_connector_number_stays_none() -> None:
    """The `DRAWING_ONLY` dial doesn't print a partner number — stays None, not missing."""
    sheet = _sheet_with_one_stub("FlowOutPipeOffPageConnector", "in")
    labels, _unresolved = read_connector_labels(sheet)
    (label,) = labels
    assert label.referenced_connector_number is None


def test_referenced_connector_number_is_read_when_present() -> None:
    sheet = _sheet_with_one_stub(
        "FlowOutPipeOffPageConnector", "in", referenced_connector_number="SHEET-1-OPC-00"
    )
    labels, _unresolved = read_connector_labels(sheet)
    (label,) = labels
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


# ---- ADR-0016 §11 OQ1b: a stub has neither its own number nor a referenced drawing number ----


def test_connector_with_no_reference_label_is_reported_unresolved_not_raised() -> None:
    """A connector from an imported file whose DEXPI-reference mapping isn't done yet
    (`kg-construction.md` §11 OQ1b) — neither `connector_number` nor `referenced_drawing_number`."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("stub", node_class="FlowOutPipeOffPageConnector")
    graph.add_node("other", node_class="CentrifugalPump", tag="P-1")
    graph.add_edge("other", "stub", relation="send_to")
    sheet = SheetGraph(sheet_id="0", graph=graph)

    labels, unresolved = read_connector_labels(sheet)

    assert labels == []
    (entry,) = unresolved
    assert entry.from_key == "0:stub"
    assert entry.reason == "no reference label"
