"""A specimen drawing set: every schema class drawn once, for checking the symbols by eye.

`python -m plantgraph.demo.drawing.specimen --out DIR` writes `DIR/SPECIMEN/drawings.pdf`. Each
sheet is one pipe with a handful of items on it, so a symbol is easy to find and judge; the last
sheet holds the instrument bubbles. Nothing here reads a corpus.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.demo.drawing.layout import layout_sheet
from plantgraph.demo.drawing.models import LayoutConfig
from plantgraph.demo.drawing.render_pdf import render_drawing_set
from plantgraph.graph.schema import CLASS_SPECS, NodeCategory, NodeClass

ITEMS_PER_SHEET = 12
_INSTRUMENT_CHAIN = (
    "ProcessSignalGeneratingFunction",
    "ProcessInstrumentationFunction",
    "ProcessControlFunction",
    "ActuatingFunction",
    "ActuatingElectricalFunction",
)


def _piped_classes() -> list[str]:
    """Every class that sits on the pipe-flow drawing, in schema order."""
    return [
        node_class.value
        for node_class, spec in CLASS_SPECS.items()
        if spec.category in (NodeCategory.EQUIPMENT, NodeCategory.PIPING, NodeCategory.OTHER)
    ]


def _tag(node_class: str, number: int) -> str | None:
    prefix = CLASS_SPECS[NodeClass(node_class)].tag_prefix
    return None if prefix is None else f"{prefix}-{number}"


def _flow_sheet(sheet_id: str, classes: list[str], first_number: int) -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for offset, node_class in enumerate(classes):
        attrs: dict[str, object] = {"node_class": node_class, "unit_id": "SPECIMEN"}
        tag = _tag(node_class, first_number + offset)
        if tag is not None:
            attrs["tag"] = tag
        graph.add_node(f"n{offset}", **attrs)
        if offset:
            graph.add_edge(f"n{offset - 1}", f"n{offset}", relation="send_to")
    return SheetGraph(sheet_id=sheet_id, graph=graph)


def _instrument_sheet(sheet_id: str) -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("pump", node_class="CentrifugalPump", tag="P-1", unit_id="SPECIMEN")
    graph.add_node("valve", node_class="GlobeValve", tag="FV-1", unit_id="SPECIMEN")
    graph.add_edge("pump", "valve", relation="send_to")
    for index, node_class in enumerate(_INSTRUMENT_CHAIN):
        graph.add_node(
            f"i{index}",
            node_class=node_class,
            loop_tag=f"FIC-{index + 1}",
            measured_variable="F",
            unit_id="SPECIMEN",
        )
        if index:
            graph.add_edge(f"i{index - 1}", f"i{index}", relation="send_signal_to")
    graph.add_edge("i4", "valve", relation="control")
    return SheetGraph(sheet_id=sheet_id, graph=graph)


def specimen_sheets() -> list[SheetGraph]:
    """One sheet per `ITEMS_PER_SHEET` classes, then the instrument sheet."""
    classes = _piped_classes()
    sheets = [
        _flow_sheet(str(number + 1), classes[start : start + ITEMS_PER_SHEET], start + 1)
        for number, start in enumerate(range(0, len(classes), ITEMS_PER_SHEET))
    ]
    sheets.append(_instrument_sheet(str(len(sheets) + 1)))
    return sheets


def main(argv: list[str] | None = None) -> None:
    """Write the specimen PDF and print where it is."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.demo.drawing.specimen")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    config = LayoutConfig(glyph_style="iso")
    layouts = [layout_sheet(sheet, config) for sheet in specimen_sheets()]
    rendered = render_drawing_set("SPECIMEN", layouts, config)
    target = args.out / "SPECIMEN" / "drawings.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(rendered.data)
    print(f"{target}: {len(rendered.pages)} sheets, {rendered.symbols} symbols")


if __name__ == "__main__":
    main()
