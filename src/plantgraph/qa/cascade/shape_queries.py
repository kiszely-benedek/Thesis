"""Generic query shapes for the shape bench: the ways a Cypher query can walk the flow graph.

Flow in a plant graph is a chain of `send_to` relationships between items ("this item sends its
fluid to that one"). A question like "which valves are upstream of pump P-1" needs the *set* of
items reachable by following the chain backwards. How the query is written decides whether the
database enumerates every path (exponential on a plant with loops and parallel routes) or just
visits every item once. Each shape below is the same question written one way; the bench times
them. They carry no family wording: only an anchor tag, or a pair of tags for the route shapes.
"""

from __future__ import annotations

from plantgraph.qa.cascade.shape_bench import BenchQuery

_GROUP = "shape"


def _tag(value: str) -> str:
    """A tag as a Cypher string literal; refuses a quote, which would break out of it."""
    if "'" in value or "\\" in value:
        raise ValueError(f"expected a plain tag without quote or backslash, found {value!r}")
    return f"'{value}'"


def set_shapes(anchor: str) -> list[BenchQuery]:
    """Upstream / downstream sets of one anchor, as distinct end items (no path is returned)."""
    a = _tag(anchor)
    shapes = {
        "upstream_distinct": f"MATCH (u:PlantItem)-[:send_to*1..]->(a:PlantItem {{tag: {a}}}) "
        "RETURN DISTINCT u.tag AS tag ORDER BY tag",
        "downstream_distinct": f"MATCH (a:PlantItem {{tag: {a}}})-[:send_to*1..]->(d:PlantItem) "
        "RETURN DISTINCT d.tag AS tag ORDER BY tag",
        "upstream_qpp": f"MATCH (a:PlantItem {{tag: {a}}})<-[:send_to]-+(u:PlantItem) "
        "RETURN DISTINCT u.tag AS tag ORDER BY tag",
        # the shape the dev check timed out on: the path is bound, then flattened
        "upstream_bound_path_unwind": f"MATCH p = (u:PlantItem)-[:send_to*1..]->"
        f"(a:PlantItem {{tag: {a}}}) UNWIND nodes(p) AS v "
        "WITH DISTINCT v RETURN v.tag AS tag ORDER BY tag",
    }
    return [
        BenchQuery(query_id=f"{name}:{anchor}", group=_GROUP, query=q) for name, q in shapes.items()
    ]


def route_shapes(start: str, end: str) -> list[BenchQuery]:
    """Reachability and one shortest route between two tags."""
    s, e = _tag(start), _tag(end)
    ends = f"(a:PlantItem {{tag: {s}}}), (b:PlantItem {{tag: {e}}})"
    shapes = {
        "reach_exists": f"MATCH {ends} RETURN EXISTS {{ (a)-[:send_to*1..]->(b) }} AS reachable",
        "route_shortestpath": f"MATCH {ends} MATCH p = shortestPath((a)-[:send_to*]->(b)) "
        "RETURN [n IN nodes(p) | n.tag] AS tags",
        "route_shortest_1": f"MATCH p = SHORTEST 1 (a:PlantItem {{tag: {s}}})-[:send_to]->+"
        f"(b:PlantItem {{tag: {e}}}) RETURN [n IN nodes(p) | n.tag] AS tags",
        "route_all_paths_count": f"MATCH p = (a:PlantItem {{tag: {s}}})-[:send_to*1..]->"
        f"(b:PlantItem {{tag: {e}}}) RETURN count(p) AS n_paths",
    }
    return [
        BenchQuery(query_id=f"{name}:{start}->{end}", group=_GROUP, query=q)
        for name, q in shapes.items()
    ]


def generic_shapes(anchors: list[str], routes: list[tuple[str, str]]) -> list[BenchQuery]:
    """All shapes for every anchor and every route pair."""
    queries = [shape for anchor in anchors for shape in set_shapes(anchor)]
    return queries + [shape for start, end in routes for shape in route_shapes(start, end)]
