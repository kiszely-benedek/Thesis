"""A three-sheet toy corpus for the drawing-set tests (renderer and export).

Sheet "2": pump -> valve -> out flag to sheet "10" (in the corpus), a transmitter and a signal
flag. Sheet "10": in flag from "2" -> tank -> out flag to sheet "99" (not in the corpus: the
dangling flag). Sheet "A": one tank, to prove non-numeric ids sort after the numeric ones.
Numeric ids "2" < "10" prove the natural (not alphabetical) page order.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.models import Resolution, ResolutionReport

IN_FLAG = "FlowInPipeOffPageConnector"
OUT_FLAG = "FlowOutPipeOffPageConnector"
OUT_SIGNAL = "FlowOutSignalOffPageConnector"


def _node(graph: nx.DiGraph[str], node_id: str, node_class: str, **attrs: object) -> None:
    graph.add_node(node_id, node_class=node_class, unit_id="U1", **attrs)


def _sheet_two() -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    _node(graph, "n1", "CentrifugalPump", tag="P-201")
    _node(graph, "n2", "GlobeValve", tag="XV-201")
    _node(
        graph,
        "n3",
        OUT_FLAG,
        referenced_drawing_number="10",
        line_number="PG-7001",
        fluid_code="PG",
        connector_number="C-2-1",
    )
    _node(graph, "n4", "ProcessSignalGeneratingFunction", loop_tag="TT-201", measured_variable="T")
    _node(graph, "n5", OUT_SIGNAL, referenced_drawing_number="10", loop_tag="TT-201")
    graph.add_edge("n1", "n2", relation="send_to", line_number="PG-7000")
    graph.add_edge("n2", "n3", relation="send_to", line_number="PG-7001")
    graph.add_edge("n4", "n5", relation="send_signal_to")
    return SheetGraph(sheet_id="2", graph=graph)


def _sheet_ten() -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    _node(
        graph,
        "m1",
        IN_FLAG,
        referenced_drawing_number="2",
        line_number="PG-7001",
        fluid_code="PG",
        connector_number="C-10-1",
    )
    _node(graph, "m2", "Tank", tag="T-1001")
    _node(
        graph,
        "m3",
        OUT_FLAG,
        referenced_drawing_number="99",
        line_number="PG-7002",
        fluid_code="PG",
        connector_number="C-10-2",
    )
    graph.add_edge("m1", "m2", relation="send_to", line_number="PG-7001")
    graph.add_edge("m2", "m3", relation="send_to", line_number="PG-7002")
    return SheetGraph(sheet_id="10", graph=graph)


def _sheet_a() -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    _node(graph, "k1", "Tank", tag="T-9")
    return SheetGraph(sheet_id="A", graph=graph)


def toy_sheets() -> list[SheetGraph]:
    """The toy sheets, deliberately not in page order."""
    return [_sheet_a(), _sheet_ten(), _sheet_two()]


def toy_resolution(sheets: list[SheetGraph]) -> Resolution:
    """A `Resolution` carrying only the counts the export checks (symbols and connectors)."""
    n_symbols = sum(sheet.graph.number_of_nodes() for sheet in sheets)
    report = ResolutionReport(
        n_sheets=len(sheets),
        n_occurrences=n_symbols,
        n_connectors=4,  # n3, n5, m1, m3
        pairs_by_rule={},
        unresolved_by_reason={},
        n_identity_groups=0,
        ambiguous_tag_keys=0,
        edge_attribute_conflicts=0,
    )
    return Resolution(
        plant=nx.DiGraph(), connector_pairs=[], identity_groups=[], unresolved=[], report=report
    )
