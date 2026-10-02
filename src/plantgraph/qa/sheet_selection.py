"""Which sheets does Hierarchical want, before any size limit? (design §3.1 steps 3-5).

Vocabulary: a **sheet** is one page of the engineering drawing; an **anchor**
is an item or unit the question names (`anchors.py`). The *core* is every
sheet of every anchor. With two or more tag anchors, a *route* joins the
first anchor to each other one (`routing.py`) and its sheets join the core.
*Rings* are the sheets one, two, ... hops away from the anchor sheets.

This module only chooses; `context_budget.py` decides what to cut when the
choice is too big. Nothing here reads a gold field.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Literal

import networkx as nx

from plantgraph.qa.anchors import TagAnchor
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.routing import (
    FlowGraph,
    PairRoute,
    SheetRouteGraph,
    build_flow_graph,
    build_sheet_route_graph,
    flow_through_line,
    route_pair_by_flow,
    route_pair_by_sheets,
    sheet_through_line,
)

RouteMode = Literal["sheet_graph", "flow_path"]
ROUTE_MODES: tuple[RouteMode, ...] = ("sheet_graph", "flow_path")


class RoutingGraphs:
    """The two search graphs of a corpus, each built on first use and then kept."""

    def __init__(self, view: GraphView) -> None:
        self._view = view

    @cached_property
    def sheets(self) -> SheetRouteGraph:
        """Undirected sheet graph with identity links."""
        return build_sheet_route_graph(self._view)

    @cached_property
    def flow(self) -> FlowGraph:
        """Directed occurrence graph; also used for the within-sheet paths of a sheet route."""
        return build_flow_graph(self._view)


@dataclass(frozen=True)
class SheetSelection:
    """The unbudgeted choice of sheets, with what the budget needs to cut it down."""

    #: Sheets of every tag-anchor occurrence; never cut.
    tag_sheets: frozenset[str]
    #: Sheets of the anchor units; cut only if they are neither tag nor route sheets.
    unit_sheets: frozenset[str]
    #: Every sheet a route passes, tag sheets included; never cut.
    route_sheets: frozenset[str]
    #: Per route sheet outside the core, the occurrences its route uses (the through-line).
    through_lines: dict[str, tuple[str, ...]]
    #: Rings 1..h, nearest first; a ring with no sheet is left out.
    rings: tuple[frozenset[str], ...]
    #: Hops from the nearest anchor sheet, for ordering what to compress.
    distance_from_anchors: dict[str, int]
    #: `None` with fewer than two tag anchors, else whether every pair got a route.
    route_found: bool | None
    #: `"sheet_graph"` when flow mode had to use the sheet route for some pair.
    route_fallback: str | None


def select_sheets(
    view: GraphView,
    graphs: RoutingGraphs,
    tags: Sequence[TagAnchor],
    unit_ids: Sequence[str],
    *,
    route_mode: RouteMode,
    sheet_hops: int,
) -> SheetSelection:
    """Core, routes and rings for these anchors."""
    tag_sheets = frozenset(sheet for tag in tags for sheet in tag.sheet_ids)
    unit_sheets = frozenset(sheet for unit in unit_ids for sheet in view.sheets_of_unit(unit))
    core = tag_sheets | unit_sheets
    routes = _routes_between(graphs, tags, route_mode)
    route_sheets = frozenset(sheet for route in routes for sheet in route.sheets) | tag_sheets
    distances = _distances_from(graphs.sheets, core)
    return SheetSelection(
        tag_sheets=tag_sheets,
        unit_sheets=unit_sheets,
        route_sheets=route_sheets,
        through_lines=_merged_through_lines(graphs, routes, core),
        rings=_rings(distances, core | route_sheets, sheet_hops),
        distance_from_anchors=distances,
        route_found=_all_found(routes) if len(tags) >= 2 else None,
        route_fallback="sheet_graph" if any(r.fell_back_to_sheet_graph for r in routes) else None,
    )


def _routes_between(
    graphs: RoutingGraphs, tags: Sequence[TagAnchor], route_mode: RouteMode
) -> list[PairRoute]:
    """From the first anchor in the text to each other anchor; none with a single anchor."""
    if len(tags) < 2:
        return []
    first = tags[0]
    if route_mode == "flow_path":
        return [route_pair_by_flow(graphs.flow, graphs.sheets, first, other) for other in tags[1:]]
    return [route_pair_by_sheets(graphs.sheets, first, other) for other in tags[1:]]


def _all_found(routes: Collection[PairRoute]) -> bool:
    return all(route.found for route in routes)


def _merged_through_lines(
    graphs: RoutingGraphs, routes: Sequence[PairRoute], core: frozenset[str]
) -> dict[str, tuple[str, ...]]:
    """Through-lines of all routes; a sheet on two routes keeps the union, first-seen order."""
    merged: dict[str, tuple[str, ...]] = {}
    for route in routes:
        if not route.found:
            continue
        for sheet, keys in _through_line_of(graphs, route, core).items():
            merged[sheet] = tuple(dict.fromkeys([*merged.get(sheet, ()), *keys]))
    return merged


def _through_line_of(
    graphs: RoutingGraphs, route: PairRoute, core: frozenset[str]
) -> dict[str, tuple[str, ...]]:
    if route.path:  # a flow route knows its occurrences
        return flow_through_line(graphs.flow, route.path, core)
    return sheet_through_line(graphs.flow, graphs.sheets, route.sheets, core)


def _distances_from(sheets: SheetRouteGraph, sources: Collection[str]) -> dict[str, int]:
    """Hops from the nearest source sheet to every sheet it can reach (breadth-first)."""
    if not sources:
        return {}
    lengths = nx.multi_source_dijkstra_path_length(sheets.graph, set(sources))
    return {sheet: int(length) for sheet, length in lengths.items()}


def _rings(
    distances: dict[str, int], already_selected: Collection[str], sheet_hops: int
) -> tuple[frozenset[str], ...]:
    """Sheets exactly 1..`sheet_hops` hops out, minus those selected; empty rings are skipped."""
    selected = frozenset(already_selected)
    rings = [
        frozenset(sheet for sheet, distance in distances.items() if distance == hops) - selected
        for hops in range(1, sheet_hops + 1)
    ]
    return tuple(ring for ring in rings if ring)
