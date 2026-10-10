"""Lays out one sheet: boxes in a layered pipe-flow drawing, instruments in a band above.

`layout_sheet` is a pure function of the sheet graph and the config - same input, same output.
Work happens in a virtual canvas; if the sheet is too crowded for the page at normal symbol
size, the canvas grows and everything is scaled down by one factor at the end (`scale`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.demo.drawing.band import (
    BandCounts,
    band_width_needed,
    desired_x,
    place_band,
)
from plantgraph.demo.drawing.families import (
    NodeInfo,
    classify_nodes,
    symbol_labels,
    symbol_size,
    target_sheet,
)
from plantgraph.demo.drawing.flow_placement import (
    FlowGeometry,
    column_widths,
    place_flow,
    rows_needed,
    width_needed,
)
from plantgraph.demo.drawing.geometry import Box, Point
from plantgraph.demo.drawing.layering import LayeredFlow, layer_flow_graph
from plantgraph.demo.drawing.models import (
    LayoutConfig,
    PlacedSymbol,
    RoutedLine,
    SheetLayout,
)
from plantgraph.demo.drawing.routing import (
    BusLanes,
    Terminal,
    route_flow_chain,
    route_via_gutters,
)


@dataclass(frozen=True)
class _Canvas:
    """The virtual canvas: the drawing area divided into band, gap and flow drawing."""

    scale: float
    width: float
    band_height: float
    flow_top: float
    flow_height: float


@dataclass(frozen=True)
class _BandMembers:
    instruments: list[str]
    in_flags: list[str]
    out_flags: list[str]

    @property
    def counts(self) -> BandCounts:
        return BandCounts(len(self.instruments), len(self.in_flags), len(self.out_flags))


def layout_sheet(sheet: SheetGraph, config: LayoutConfig | None = None) -> SheetLayout:
    """Place every symbol of a sheet and route every edge as a polyline."""
    cfg = config or LayoutConfig()
    _check_config(cfg)
    nodes = classify_nodes(sheet.graph)
    units = _units(nodes)
    if not nodes:
        return SheetLayout(sheet_id=sheet.sheet_id, units=units, scale=1.0, symbols=(), lines=())

    flow_ids = sorted(
        (i for i, n in nodes.items() if n.is_flow), key=lambda i: _order_key(nodes[i])
    )
    band = _band_members(nodes)
    layered = layer_flow_graph(
        _flow_graph(sheet.graph, flow_ids),
        flow_ids,
        push_to_end=[i for i in flow_ids if _is_outgoing_pipe_flag(nodes[i])],
        sweeps=cfg.sweeps,
    )
    widths = {i: symbol_size(nodes[i].family, cfg)[0] for i in flow_ids}
    canvas = _make_canvas(_fit_scale(layered, widths, band.counts, cfg), cfg)

    geometry = place_flow(layered, widths, cfg, canvas.width, canvas.flow_top, canvas.flow_height)
    terminals = _flow_terminals(flow_ids, nodes, geometry, cfg)
    terminals.update(_band_terminals(sheet.graph, band, geometry, canvas, cfg))
    symbols = [_symbol(nodes[i], terminals[i].box) for i in nodes]
    lines = _route_edges(sheet.graph, layered, geometry, terminals, canvas)
    return _to_page(sheet.sheet_id, units, symbols, lines, canvas.scale, cfg)


def _check_config(cfg: LayoutConfig) -> None:
    band_needed = cfg.band_rows * cfg.min_row_pitch
    band_available = cfg.band_fraction * cfg.region_height
    if band_needed > band_available:
        raise ValueError(
            f"{cfg.band_rows} band rows need {band_needed} pt but the band has {band_available} pt"
        )


def _units(nodes: dict[str, NodeInfo]) -> tuple[str, ...]:
    """The plant units (areas of the plant, e.g. a distillation section) drawn on the sheet."""
    unit_ids = {str(info.attrs["unit_id"]) for info in nodes.values() if info.attrs.get("unit_id")}
    return tuple(sorted(unit_ids))


def _is_outgoing_pipe_flag(info: NodeInfo) -> bool:
    return info.family == "pipe_flag" and info.flag_direction == "out"


def _order_key(info: NodeInfo) -> tuple[tuple[tuple[int, int, str], ...], str]:
    """Natural tag order ("P2" before "P10"); the node id breaks ties."""
    tag = str(info.attrs.get("tag") or info.attrs.get("loop_tag") or "")
    parts = re.split(r"(\d+)", tag)
    return tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in parts), info.node_id


def _flow_graph(graph: nx.DiGraph[str], flow_ids: list[str]) -> nx.DiGraph[str]:
    """The part laid out in columns: flow symbols and the edges between them."""
    flow: nx.DiGraph[str] = nx.DiGraph()
    flow.add_nodes_from(flow_ids)
    members = set(flow_ids)
    flow.add_edges_from(sorted(e for e in graph.edges if e[0] in members and e[1] in members))
    return flow


def _band_members(nodes: dict[str, NodeInfo]) -> _BandMembers:
    in_band = sorted((n for n in nodes.values() if not n.is_flow), key=_order_key)
    return _BandMembers(
        instruments=[n.node_id for n in in_band if n.family == "instrument"],
        in_flags=[n.node_id for n in in_band if n.flag_direction == "in"],
        out_flags=[n.node_id for n in in_band if n.flag_direction == "out"],
    )


def _fit_scale(
    layered: LayeredFlow, widths: dict[str, float], counts: BandCounts, cfg: LayoutConfig
) -> float:
    """The factor (at most 1) by which the drawing must shrink to fit the page."""
    flow_widths = column_widths(layered.columns, widths, cfg)
    need_width = max(width_needed(flow_widths, cfg), band_width_needed(counts, cfg))
    fits = [1.0, cfg.region_width / need_width]
    need_height = rows_needed(layered.columns) * cfg.min_row_pitch
    if need_height:
        fits.append(cfg.flow_fraction * cfg.region_height / need_height)
    return min(fits)


def _make_canvas(scale: float, cfg: LayoutConfig) -> _Canvas:
    height = cfg.region_height / scale
    return _Canvas(
        scale=scale,
        width=cfg.region_width / scale,
        band_height=cfg.band_fraction * height,
        flow_top=(1 - cfg.flow_fraction) * height,
        flow_height=cfg.flow_fraction * height,
    )


def _flow_terminals(
    flow_ids: list[str], nodes: dict[str, NodeInfo], geometry: FlowGeometry, cfg: LayoutConfig
) -> dict[str, Terminal]:
    terminals: dict[str, Terminal] = {}
    for node_id in flow_ids:
        x, y = geometry.positions[node_id]
        width, height = symbol_size(nodes[node_id].family, cfg)
        layer = geometry.layer_of[node_id]
        terminals[node_id] = Terminal(
            Box(x, y, width, height), geometry.left_gutter(layer), geometry.right_gutter(layer), y
        )
    return terminals


def _band_terminals(
    graph: nx.DiGraph[str],
    band: _BandMembers,
    geometry: FlowGeometry,
    canvas: _Canvas,
    cfg: LayoutConfig,
) -> dict[str, Terminal]:
    neighbours = {
        node: set(graph.predecessors(node)) | set(graph.successors(node))
        for node in band.instruments
    }
    flow_x = {node: position[0] for node, position in geometry.positions.items()}
    preferred = desired_x(band.instruments, neighbours, flow_x, canvas.width / 2)
    return place_band(
        band.instruments,
        band.in_flags,
        band.out_flags,
        preferred,
        canvas.width,
        canvas.band_height,
        cfg,
    )


def _symbol(info: NodeInfo, box: Box) -> PlacedSymbol:
    return PlacedSymbol(
        node_id=info.node_id,
        family=info.family,
        node_class=info.node_class,
        x=box.x,
        y=box.y,
        width=box.width,
        height=box.height,
        labels=symbol_labels(info),
        target_sheet=target_sheet(info),
    )


def _route_edges(
    graph: nx.DiGraph[str],
    layered: LayeredFlow,
    geometry: FlowGeometry,
    terminals: dict[str, Terminal],
    canvas: _Canvas,
) -> list[RoutedLine]:
    """Every edge exactly once, in sorted order (so the output is deterministic)."""
    gap = canvas.flow_top - canvas.band_height
    bus = BusLanes(top=canvas.band_height + 3, height=gap - 6)
    boxes = {node: terminal.box for node, terminal in terminals.items()}
    lines: list[RoutedLine] = []
    for source, target in sorted(graph.edges):
        chain = layered.chains.get((source, target))
        if chain is not None:
            points = route_flow_chain(chain, geometry, boxes)
        else:
            both_in_band = source not in geometry.positions and target not in geometry.positions
            lane = terminals[source].lane_y if both_in_band else bus.next_lane()
            points = route_via_gutters(terminals[source], terminals[target], lane)
        attrs = graph.edges[source, target]
        line_number = attrs.get("line_number")
        lines.append(
            RoutedLine(
                source=source,
                target=target,
                relation=_relation(attrs, source, target),
                points=tuple(points),
                line_number=None if line_number is None else str(line_number),
                is_back_edge=chain is not None and chain.is_back_edge,
            )
        )
    return lines


def _relation(attrs: dict[str, object], source: str, target: str) -> str:
    relation = attrs.get("relation")
    if not isinstance(relation, str):
        raise ValueError(f"edge {source}->{target} has no relation; found {relation!r}")
    return relation


def _to_page(
    sheet_id: str,
    units: tuple[str, ...],
    symbols: list[PlacedSymbol],
    lines: list[RoutedLine],
    scale: float,
    cfg: LayoutConfig,
) -> SheetLayout:
    """Shrink by `scale` and move from canvas coordinates to page coordinates."""

    def to_page(point: Point) -> Point:
        return (cfg.margin + point[0] * scale, cfg.margin + point[1] * scale)

    def scaled(symbol: PlacedSymbol) -> PlacedSymbol:
        x, y = to_page((symbol.x, symbol.y))
        size = {"width": symbol.width * scale, "height": symbol.height * scale}
        return symbol.model_copy(update={"x": x, "y": y, **size})

    def moved(line: RoutedLine) -> RoutedLine:
        return line.model_copy(update={"points": tuple(to_page(p) for p in line.points)})

    return SheetLayout(
        sheet_id=sheet_id,
        units=units,
        scale=scale,
        symbols=tuple(scaled(s) for s in symbols),
        lines=tuple(moved(line) for line in lines),
    )
