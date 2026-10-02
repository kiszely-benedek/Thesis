"""Breadth-first closure and shortest path over an `ItemGraph` (design §3.3).

Pure functions: predicates arrive as precomputed id sets, so nothing here
knows the filter language. Every neighbour list is already sorted
(`ItemGraph.steps`), which makes each result deterministic.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import Direction, ItemEdge, RelationGroup


@dataclass(frozen=True)
class Closure:
    """What a closure reached, excluding the start items."""

    #: Reached item id -> hop distance from the nearest start item.
    hops: dict[str, int]
    #: Reached items that matched the stop filter; nothing beyond them was entered.
    stops: frozenset[str]
    #: Every edge walked to an item in the result or a start item, sorted.
    edges: list[ItemEdge]


def closure(
    graph: ItemGraph,
    starts: Sequence[str],
    direction: Direction,
    relations: RelationGroup,
    stop_ids: Collection[str] | None = None,
    walk_ids: Collection[str] | None = None,
    max_hops: int | None = None,
) -> Closure:
    """Everything reachable from `starts`, entering only `walk_ids` and halting at `stop_ids`.

    A stop item is included, then not expanded. An item outside `walk_ids` is
    never entered, so it cannot be a stop either.
    """
    seen: dict[str, int] = {start: 0 for start in starts}
    stops: set[str] = set()
    edges: dict[tuple[str, str, str], ItemEdge] = {}
    frontier = sorted(seen, key=graph.sort_key)
    depth = 0
    while frontier and (max_hops is None or depth < max_hops):
        depth += 1
        next_frontier: list[str] = []
        for node in frontier:
            for neighbour, edge in graph.steps(node, direction, relations):
                if neighbour not in seen:
                    if walk_ids is not None and neighbour not in walk_ids:
                        continue
                    seen[neighbour] = depth
                    _expand_or_stop(neighbour, stop_ids, stops, next_frontier)
                edges[(edge.source, edge.target, edge.relation)] = edge
        frontier = next_frontier
    start_set = set(starts)
    hops = {item: hop for item, hop in seen.items() if item not in start_set}
    return Closure(hops=hops, stops=frozenset(stops), edges=sorted(edges.values(), key=_edge_key))


def _expand_or_stop(
    item: str, stop_ids: Collection[str] | None, stops: set[str], next_frontier: list[str]
) -> None:
    if stop_ids is not None and item in stop_ids:
        stops.add(item)
    else:
        next_frontier.append(item)


def _edge_key(edge: ItemEdge) -> tuple[str, str, str]:
    return (edge.source, edge.target, edge.relation)


def shortest_path(
    graph: ItemGraph,
    sources: Sequence[str],
    targets: Collection[str],
    relations: RelationGroup,
    directed: bool,
) -> tuple[list[str], list[ItemEdge]] | None:
    """Fewest-hop path from any source to any target, as (item ids, edges); `None` if none.

    Breadth-first with sorted neighbours and first-found parents, which picks
    the path whose tag sequence is smallest among equally short ones (the tie
    rule the `FLOW_PATH` reference uses).
    """
    direction: Direction = "downstream" if directed else "both"
    parent: dict[str, tuple[str, ItemEdge] | None] = {
        source: None for source in sorted(sources, key=graph.sort_key)
    }
    queue = deque(parent)
    while queue:
        node = queue.popleft()
        if node in targets:
            return _walk_back(parent, node)
        for neighbour, edge in graph.steps(node, direction, relations):
            if neighbour not in parent:
                parent[neighbour] = (node, edge)
                queue.append(neighbour)
    return None


def _walk_back(
    parent: dict[str, tuple[str, ItemEdge] | None], end: str
) -> tuple[list[str], list[ItemEdge]]:
    items = [end]
    edges: list[ItemEdge] = []
    while (link := parent[items[-1]]) is not None:
        items.append(link[0])
        edges.append(link[1])
    return items[::-1], edges[::-1]
