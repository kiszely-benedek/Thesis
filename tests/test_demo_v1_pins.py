"""Pins the demo drawing of v1 classes: the layout JSON and the PDF bytes must not change.

The pinned sheet uses every v1 symbol family (equipment, valves, all three instrument bubbles,
pipe and signal flags). A change to the glyph rules for generator v2 must leave these hashes alone.
"""

from __future__ import annotations

import hashlib

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.demo.drawing import layout_sheet
from plantgraph.demo.drawing.models import SheetLayout
from plantgraph.demo.drawing.render_pdf import render_drawing_set

PINNED_LAYOUT_SHA256 = "662635aa981b4ac1baf2d70385e3445909cee96c583acb1c5236ab72be342337"
PINNED_PDF_SHA256 = "22125d63a1ebc6a30b5f757519963ce3bd18aebb18a76a961c400e2adb753434"


def v1_sheet() -> SheetGraph:
    """A sheet with one of every v1 node class, wired like a small control loop."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    nodes = [
        ("a", "Tank", {"tag": "T-1"}),
        ("b", "CentrifugalPump", {"tag": "P-1"}),
        ("c", "GlobeValve", {"tag": "FV-1"}),
        ("d", "BallValve", {"tag": "XV-1"}),
        ("e", "CheckValve", {"tag": "CHV-1"}),
        ("f", "PressureVessel", {"tag": "V-1"}),
        ("g", "ProcessColumn", {"tag": "T-2"}),
        ("t", "ProcessSignalGeneratingFunction", {"loop_tag": "FT-1", "measured_variable": "F"}),
        ("i", "ProcessInstrumentationFunction", {"loop_tag": "FIC-1", "measured_variable": "F"}),
        ("x", "ActuatingFunction", {"loop_tag": "FV-1"}),
        ("o", "FlowOutPipeOffPageConnector", {"referenced_drawing_number": "7"}),
        ("n", "FlowInPipeOffPageConnector", {"referenced_drawing_number": "7"}),
        ("s", "FlowOutSignalOffPageConnector", {"referenced_drawing_number": "7"}),
        ("u", "FlowInSignalOffPageConnector", {"referenced_drawing_number": "7"}),
    ]
    for node_id, node_class, attrs in nodes:
        graph.add_node(node_id, node_class=node_class, unit_id="U1", **attrs)
    for source, target in [("n", "a"), ("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]:
        graph.add_edge(source, target, relation="send_to", line_number="L-1")
    graph.add_edge("e", "f", relation="send_to")
    graph.add_edge("f", "g", relation="send_to")
    graph.add_edge("g", "o", relation="send_to")
    graph.add_edge("t", "i", relation="send_signal_to")
    graph.add_edge("i", "x", relation="send_signal_to")
    graph.add_edge("x", "c", relation="control")
    graph.add_edge("s", "t", relation="send_signal_to")
    graph.add_edge("t", "u", relation="send_signal_to")
    return SheetGraph(sheet_id="1", graph=graph)


def _layout() -> SheetLayout:
    return layout_sheet(v1_sheet())


def test_v1_layout_is_unchanged() -> None:
    digest = hashlib.sha256(_layout().model_dump_json().encode()).hexdigest()
    assert digest == PINNED_LAYOUT_SHA256


def test_v1_pdf_is_unchanged() -> None:
    rendered = render_drawing_set("PIN", [_layout()])
    assert hashlib.sha256(rendered.data).hexdigest() == PINNED_PDF_SHA256
