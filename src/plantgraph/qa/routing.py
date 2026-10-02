"""Routing between anchors: which sheets lie between two named items? (design §3.2-§3.3).

Terms: a **sheet** is one page of the engineering drawing; an **off-page
connector** (a stub symbol where a pipe runs off the page edge) is paired
with a stub on another sheet by the resolver (`continues_as`); an **identity
link** (`same_tagged_item_as`) says a repeated drawing of one item on another
sheet is the same item as its main drawing, its *home* occurrence.

Two routes are built, because which is better is decided by measurement
(ADR-0030):

- **sheet route**: breadth-first search over an undirected graph of sheets.
  Identity links are edges too: a duplicated item replaces a cut, so without
  them some sheets are unreachable (the probe, design §2 F1).
- **flow route**: a weighted search over the occurrence graph that follows
  the pipe direction. A flow path can leave a sheet and come back, which a
  shortest sheet path would skip (F2).

Only what the resolver produced and what is visible is read (`GraphView`);
never the manifest or a gold id.
"""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.graph import schema
from plantgraph.qa.anchors import TagAnchor
from plantgraph.qa.graph_view import EdgeRecord, GraphView

_CONTINUES_AS = schema.Relation.CONTINUES_AS.value
_SAME_ITEM = schema.Relation.SAME_TAGGED_ITEM_AS.value
_SEND_TO = schema.Relation.SEND_TO.value
_INCOMING_STUBS = frozenset(
    {
        schema.NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value,
        schema.NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value,
    }
)


# --- sheet route (a) ---------------------------------------------------------


@dataclass
class SheetRouteGraph:
    """Undirected sheet graph; each edge keeps the occurrence pairs that justify it."""

    #: Nodes are sheet ids; edge attribute `links` is a list of `(key_a, key_b)` occurrence pairs.
    graph: nx.Graph[str]
    sheet_of: dict[str, str]


def build_sheet_route_graph(
    view: GraphView, *, with_identity_links: bool = True
) -> SheetRouteGraph:
    """Connect sheets by `continues_as` pairs and, unless disabled, by identity links.

    `with_identity_links=False` reproduces the design's original sheet graph;
    it exists so the measurement can show how many components it leaves.
    """
    relations = {_CONTINUES_AS, _SAME_ITEM} if with_identity_links else {_CONTINUES_AS}
    sheet_of = {item.local_key: item.sheet_id for item in view.items()}
    graph: nx.Graph[str] = nx.Graph()
    graph.add_nodes_from(view.sheets())
    for edge in view.edges():
        if edge.relation in relations:
            _add_sheet_link(graph, sheet_of, edge)
    return SheetRouteGraph(graph=graph, sheet_of=sheet_of)


def _add_sheet_link(graph: nx.Graph[str], sheet_of: dict[str, str], edge: EdgeRecord) -> None:
    sheet_a, sheet_b = sheet_of[edge.source], sheet_of[edge.target]
    if sheet_a == sheet_b:
        return
    if not graph.has_edge(sheet_a, sheet_b):
        graph.add_edge(sheet_a, sheet_b, links=[])
    graph[sheet_a][sheet_b]["links"].append((edge.source, edge.target))


def sheet_route(
    sheets: SheetRouteGraph, source_sheets: Collection[str], target_sheets: Collection[str]
) -> tuple[str, ...] | None:
    """Shortest sheet path from any source sheet to the nearest target sheet; `None` if none.

    Ties are broken by sorted sheet id, so the same input gives the same route.
    """
    return _bfs_path(sheets.graph, source_sheets, target_sheets)


def _bfs_path(
    graph: nx.Graph[str], sources: Collection[str], targets: Collection[str]
) -> tuple[str, ...] | None:
    """Multi-source breadth-first search; neighbours visited in sorted order for determinism."""
    _require_nodes(graph, sources, "source")
    _require_nodes(graph, targets, "target")
    parent: dict[str, str | None] = {node: None for node in sorted(sources)}
    queue = deque(parent)
    while queue:
        node = queue.popleft()
        if node in targets:
            return _walk_back(parent, node)
        for neighbour in sorted(graph.neighbors(node)):
            if neighbour not in parent:
                parent[neighbour] = node
                queue.append(neighbour)
    return None


def _require_nodes(graph: nx.Graph[str], nodes: Iterable[str], role: str) -> None:
    missing = sorted(node for node in nodes if node not in graph)
    if missing:
        raise ValueError(f"routing {role} nodes not in the graph: {missing[:5]}")


def _walk_back(parent: dict[str, str | None], end: str) -> tuple[str, ...]:
    path = [end]
    while (previous := parent[path[-1]]) is not None:
        path.append(previous)
    return tuple(reversed(path))


# --- flow route (b) ----------------------------------------------------------


@dataclass
class FlowGraph:
    """Weighted directed graph over occurrences; a cut costs one plant hop, as the edge did."""

    #: Every edge has an integer `weight` (0 or 1).
    graph: nx.DiGraph[str]
    sheet_of: dict[str, str]
    keys_by_sheet: dict[str, list[str]] = field(default_factory=dict)


def build_flow_graph(view: GraphView) -> FlowGraph:
    """Build the flow graph once per corpus (design §3.3 table).

    Weights make a path's cost equal its number of plant `send_to` hops, the
    metric FLOW_PATH's gold uses: crossing a cut (`X -> out-stub -> in-stub -> Y`)
    costs 1 in total, exactly like the plant edge `X -> Y`. Signal relations
    are not followed.
    """
    items = view.items()
    incoming = {item.local_key for item in items if item.node_class in _INCOMING_STUBS}
    flow = FlowGraph(graph=nx.DiGraph(), sheet_of={})
    for item in items:
        flow.graph.add_node(item.local_key)
        flow.sheet_of[item.local_key] = item.sheet_id
        flow.keys_by_sheet.setdefault(item.sheet_id, []).append(item.local_key)
    for edge in view.edges():
        _add_flow_edge(flow.graph, edge, incoming)
    return flow


def _add_flow_edge(graph: nx.DiGraph[str], edge: EdgeRecord, incoming: set[str]) -> None:
    if edge.relation == _SEND_TO:
        # Leaving an incoming stub is free: the hop was already paid entering the outgoing stub.
        graph.add_edge(edge.source, edge.target, weight=0 if edge.source in incoming else 1)
    elif edge.relation == _CONTINUES_AS:
        graph.add_edge(edge.source, edge.target, weight=0)
    elif edge.relation == _SAME_ITEM:
        # A reference and its home are one item, so moving between them is free both ways.
        graph.add_edge(edge.source, edge.target, weight=0)
        graph.add_edge(edge.target, edge.source, weight=0)


class FlowRoute(BaseModel):
    """A shortest flow path: its occurrences in order, its cost and the sheets it touches."""

    model_config = ConfigDict(frozen=True)

    path: tuple[str, ...]
    #: Plant `send_to` hops along the path.
    distance: int
    #: True when only the target-to-source direction had a path (`path` then runs target first).
    reversed: bool
    #: Distinct sheets of the path occurrences, in order of first visit.
    sheets: tuple[str, ...]


def flow_route(
    flow: FlowGraph, source_keys: Collection[str], target_keys: Collection[str]
) -> FlowRoute | None:
    """Cheapest directed path from any source to any target; tries target-to-source if none.

    The reverse is tried because the question may name the downstream item
    first ("what is between V-3 and P-1?"). Returns `None` when neither
    direction has a path.
    """
    forward = _dijkstra(flow.graph, source_keys, target_keys)
    if forward is not None:
        return _flow_route(flow, forward, reversed_=False)
    backward = _dijkstra(flow.graph, target_keys, source_keys)
    if backward is not None:
        return _flow_route(flow, backward, reversed_=True)
    return None


def _flow_route(flow: FlowGraph, found: tuple[tuple[str, ...], int], reversed_: bool) -> FlowRoute:
    path, distance = found
    sheets = tuple(dict.fromkeys(flow.sheet_of[key] for key in path))
    return FlowRoute(path=path, distance=distance, reversed=reversed_, sheets=sheets)


def _dijkstra(
    graph: nx.DiGraph[str], sources: Collection[str], targets: Collection[str]
) -> tuple[tuple[str, ...], int] | None:
    """Multi-source Dijkstra; heap order (cost, key) and sorted successors fix every tie."""
    _require_nodes(graph, sources, "source")
    _require_nodes(graph, targets, "target")
    best: dict[str, int] = {key: 0 for key in sources}
    parent: dict[str, str | None] = {key: None for key in sources}
    heap = [(0, key) for key in sorted(sources)]
    done: set[str] = set()
    while heap:
        cost, key = heapq.heappop(heap)
        if key in done:
            continue
        done.add(key)
        if key in targets:
            return _walk_back(parent, key), cost
        for successor in sorted(graph.successors(key)):
            new_cost = cost + graph[key][successor]["weight"]
            if successor not in best or new_cost < best[successor]:
                best[successor] = new_cost
                parent[successor] = key
                heapq.heappush(heap, (new_cost, successor))
    return None


# --- one anchor pair, either mode -------------------------------------------


class PairRoute(BaseModel):
    """The route between two tag anchors, whichever search produced it."""

    model_config = ConfigDict(frozen=True)

    found: bool
    #: Route sheets (flow mode: in order of first visit; sheet mode: along the sheet path).
    sheets: tuple[str, ...]
    #: Occurrence path; empty for a sheet route.
    path: tuple[str, ...] = ()
    #: True when flow mode found no directed path and the sheet route was used instead.
    fell_back_to_sheet_graph: bool = False


def route_pair_by_sheets(
    sheets: SheetRouteGraph, source: TagAnchor, target: TagAnchor
) -> PairRoute:
    """Route mode `sheet_graph` between two anchors."""
    sheet_path = sheet_route(sheets, source.sheet_ids, target.sheet_ids)
    if sheet_path is None:
        return PairRoute(found=False, sheets=())
    return PairRoute(found=True, sheets=sheet_path)


def route_pair_by_flow(
    flow: FlowGraph, sheets: SheetRouteGraph, source: TagAnchor, target: TagAnchor
) -> PairRoute:
    """Route mode `flow_path`; with no directed path either way, use the flagged sheet route.

    Expected for questions whose two items do not lie on one flow path, e.g.
    two branches that meet only upstream.
    """
    route = flow_route(flow, source.local_keys, target.local_keys)
    if route is not None:
        return PairRoute(found=True, sheets=route.sheets, path=route.path)
    fallback = route_pair_by_sheets(sheets, source, target)
    return fallback.model_copy(update={"fell_back_to_sheet_graph": True})


# --- through-line ------------------------------------------------------------


def flow_through_line(
    flow: FlowGraph, path: tuple[str, ...], core_sheets: Collection[str]
) -> dict[str, tuple[str, ...]]:
    """On each route sheet outside `core_sheets`, the path's own occurrences, in path order.

    A *through-line* is the thin slice of a sheet the route actually uses:
    the entry stub or reference, the items passed through, the exit stub or
    reference. Everything else on the sheet is left out of the prompt.
    """
    kept: dict[str, list[str]] = {}
    for key in path:
        sheet = flow.sheet_of[key]
        if sheet not in core_sheets:
            kept.setdefault(sheet, []).append(key)
    return {sheet: tuple(keys) for sheet, keys in kept.items()}


def sheet_through_line(
    flow: FlowGraph,
    sheets: SheetRouteGraph,
    sheet_path: tuple[str, ...],
    core_sheets: Collection[str],
) -> dict[str, tuple[str, ...]]:
    """Through-line for a sheet route: per intermediate sheet, a shortest undirected path inside it.

    The path joins the occurrences linking the sheet to its predecessor and
    to its successor on the route. If no such path exists inside the sheet,
    the whole sheet is kept: never lose evidence to save characters.
    """
    kept: dict[str, tuple[str, ...]] = {}
    for before, sheet, after in zip(sheet_path, sheet_path[1:], sheet_path[2:], strict=False):
        if sheet in core_sheets:
            continue
        entries = _link_ends(sheets, sheet, before)
        exits = _link_ends(sheets, sheet, after)
        inside = _path_inside_sheet(flow, sheet, entries, exits)
        kept[sheet] = inside if inside is not None else tuple(flow.keys_by_sheet[sheet])
    return kept


def _link_ends(sheets: SheetRouteGraph, sheet: str, other: str) -> set[str]:
    """Occurrences on `sheet` that link it to the neighbouring sheet `other`."""
    ends = (key for pair in sheets.graph[sheet][other]["links"] for key in pair)
    return {key for key in ends if sheets.sheet_of[key] == sheet}


def _path_inside_sheet(
    flow: FlowGraph, sheet: str, entries: set[str], exits: set[str]
) -> tuple[str, ...] | None:
    # Within one sheet only: cross-sheet edges drop out of the induced subgraph.
    inside = flow.graph.subgraph(flow.keys_by_sheet[sheet]).to_undirected()
    return _bfs_path(inside, entries, exits)
