"""Cut the plant around each question's gold evidence into plain JSON, for the scorer audit.

Usage (on any checkout that can rebuild the corpus, e.g. a `git archive` copy of the commit that
made the plants; set PYTHONPATH to that copy's `src`):

    python audit_export_subgraphs.py --corpus-id H100g2 --ingest-json CORPUS/ingest.json \
        --questions QUESTIONS/H100g2/questions.jsonl --question-ids ids.txt --out subgraphs.json

The only plantgraph names used are `plantgraph.qa.corpus.load_corpus_artifacts(corpus_id,
ingest_json_path)` and the class sets `EQUIPMENT_CLASSES` and `VALVE_CLASSES` of
`plantgraph.graph.schema`; all three are the same at the E8 commit (4dfad69) and in v2.1. Questions
are read as plain JSON (`question_id`, `family`, `evidence_tags`, `anchors`), so no model class is
imported either. The output is read by `plantgraph.qa.audit.excerpt.SubgraphFile`.

A question that asks for a count along the route between two parts also gets that route written
out (`routes`). A long route cannot be traced from an excerpt cut to the size of a prompt: in the
first judge pilot (2026-11-11) the judge could not follow 20 of 21 such routes.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

import networkx as nx

#: Properties left out of a node's property map: they are already fields of the exported node.
_NODE_FIELDS = ("node_class", "tag", "unit_id")
#: Generator bookkeeping that is not drawn on a P&ID (and would show how a family was built).
_GENERATOR_INTERNALS = frozenset(
    {"plant_id", "role", "drawing_group", "sheet_group", "stream_kind"}
)
#: The relation along which material flows; routes between evidence parts follow it only.
_FLOW_RELATION = "send_to"
#: Evidence beyond this many parts is not paired up for routes (pairs grow quadratically).
_MAX_ROUTE_ENDPOINTS = 12
#: Routes kept per ordered pair of evidence parts (several shortest routes can tie).
_MAX_ROUTES_PER_PAIR = 20
#: Families whose answer is a count along the route from the first anchor to the second.
_ROUTE_FAMILIES = frozenset({"VALVES_ON_PATH"})
#: Cost of passing one item (equipment or valve) on a route; a valve costs one more or one less,
#: so the cheapest route has the fewest items and, among those, the fewest or the most valves.
_ITEM_COST = 1_000_000

_FEWEST_PARTS = "the route with the fewest parts of any kind"
_FEWEST_ITEMS = "the route with the fewest equipment items and valves, pipe fittings not counted"


def evidence_node_ids(plant: nx.DiGraph[str], evidence_tags: list[str]) -> list[str]:
    """Node ids carrying the given tags, sorted.

    Raises:
        ValueError: a tag is on no node of the plant.
    """
    by_tag: dict[str, list[str]] = {}
    for node_id, data in plant.nodes(data=True):
        if "tag" in data:
            by_tag.setdefault(str(data["tag"]), []).append(node_id)
    missing = [tag for tag in evidence_tags if tag not in by_tag]
    if missing:
        raise ValueError(f"expected every evidence tag in the plant, found none for {missing[:5]}")
    return sorted(node_id for tag in evidence_tags for node_id in by_tag[tag])


def route_node_ids(plant: nx.DiGraph[str], evidence_ids: list[str]) -> set[str]:
    """Nodes on a shortest flow route from one evidence part to another, ends included."""
    flow = nx.DiGraph(
        (u, v) for u, v, data in plant.edges(data=True) if data.get("relation") == _FLOW_RELATION
    )
    flow.add_nodes_from(evidence_ids)
    routes: set[str] = set()
    pairs = itertools.permutations(evidence_ids[:_MAX_ROUTE_ENDPOINTS], 2)
    for source, target in pairs:
        if nx.has_path(flow, source, target):
            found = nx.all_shortest_paths(flow, source, target)
            for path in itertools.islice(found, _MAX_ROUTES_PER_PAIR):
                routes.update(path)
    return routes


def _flow_graph(plant: nx.DiGraph[str]) -> nx.DiGraph[str]:
    return nx.DiGraph(
        (u, v) for u, v, data in plant.edges(data=True) if data.get("relation") == _FLOW_RELATION
    )


def _anchor_node(plant: nx.DiGraph[str], tag: str, item_classes: frozenset[str]) -> str | None:
    """The one equipment item or valve that carries `tag`; `None` when there is not exactly one."""
    found = [
        node_id
        for node_id, data in plant.nodes(data=True)
        if str(data.get("tag")) == tag and str(data.get("node_class")) in item_classes
    ]
    return found[0] if len(found) == 1 else None


def _fewest_items_route(
    plant: nx.DiGraph[str],
    flow: nx.DiGraph[str],
    ends: tuple[str, str],
    classes: tuple[frozenset[str], frozenset[str]],
    valve_step: int,
) -> list[str]:
    """Cheapest route when a fitting is free and a valve costs `valve_step` more than an item."""
    item_classes, valve_classes = classes

    def cost(_source: str, target: str, _data: dict[str, Any]) -> int:
        node_class = str(plant.nodes[target].get("node_class"))
        if node_class in valve_classes:
            return _ITEM_COST + valve_step
        return _ITEM_COST if node_class in item_classes else 0

    route: list[str] = nx.dijkstra_path(flow, ends[0], ends[1], weight=cost)
    return route


def valves_between(plant: nx.DiGraph[str], route: list[str], valves: frozenset[str]) -> int:
    """Valves strictly inside the route (its two ends are not counted)."""
    return sum(1 for node_id in route[1:-1] if str(plant.nodes[node_id]["node_class"]) in valves)


def anchor_routes(
    plant: nx.DiGraph[str],
    question: dict[str, Any],
    item_classes: frozenset[str],
    valve_classes: frozenset[str],
) -> list[dict[str, Any]]:
    """The routes a count question can mean, each as node ids in flow order.

    "Between A and B" has more than one reading when routes run in parallel: the route with the
    fewest parts of any kind, or the one with the fewest items when fittings are not counted; and
    several routes can tie on items yet differ in valves. Every reading with its own route is
    exported, so the judge can see whether the question is ambiguous. No route is exported for
    another family, an anchor that is not exactly one item, or a pair with no flow path.
    """
    if question.get("family") not in _ROUTE_FAMILIES or len(question.get("anchors", [])) != 2:
        return []
    source = _anchor_node(plant, question["anchors"][0], item_classes)
    target = _anchor_node(plant, question["anchors"][1], item_classes)
    flow = _flow_graph(plant)
    if source is None or target is None or source not in flow or target not in flow:
        return []
    if not nx.has_path(flow, source, target):
        return []
    classes = (item_classes, valve_classes)
    fewest_parts: list[str] = nx.shortest_path(flow, source, target)
    low = _fewest_items_route(plant, flow, (source, target), classes, valve_step=1)
    high = _fewest_items_route(plant, flow, (source, target), classes, valve_step=-1)
    routes = [(_FEWEST_PARTS, fewest_parts)]
    if valves_between(plant, low, valve_classes) == valves_between(plant, high, valve_classes):
        routes.append((_FEWEST_ITEMS, low))
    else:
        routes.append((f"{_FEWEST_ITEMS}; of several such routes, the one with fewest valves", low))
        routes.append((f"{_FEWEST_ITEMS}; of several such routes, the one with most valves", high))
    return _merge_equal_routes(routes)


def _merge_equal_routes(routes: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    """One entry per distinct route; a route found under two readings names both."""
    merged: list[dict[str, Any]] = []
    for basis, node_ids in routes:
        same = [entry for entry in merged if entry["node_ids"] == node_ids]
        if same:
            same[0]["basis"] += "; also " + basis
        else:
            merged.append({"basis": basis, "node_ids": node_ids})
    return merged


def distances_from(plant: nx.DiGraph[str], start: set[str], radius: int) -> dict[str, int]:
    """Hops (edges taken in either direction) from `start` to every node within `radius`."""
    distance = dict.fromkeys(start, 0)
    queue = deque(start)
    while queue:
        node = queue.popleft()
        if distance[node] == radius:
            continue
        for neighbour in itertools.chain(plant.successors(node), plant.predecessors(node)):
            if neighbour not in distance:
                distance[neighbour] = distance[node] + 1
                queue.append(neighbour)
    return distance


def _export_node(plant: nx.DiGraph[str], node_id: str, distance: int) -> dict[str, Any]:
    data = plant.nodes[node_id]
    properties = {
        str(name): str(value)
        for name, value in data.items()
        if name not in _NODE_FIELDS and name not in _GENERATOR_INTERNALS and value is not None
    }
    return {
        "id": node_id,
        "node_class": str(data.get("node_class", "")),
        "tag": str(data["tag"]) if "tag" in data else None,
        "unit_id": str(data["unit_id"]) if "unit_id" in data else None,
        "properties": properties,
        "distance": distance,
    }


def _export_edges(plant: nx.DiGraph[str], kept: set[str]) -> list[dict[str, Any]]:
    edges = []
    for source, target, data in plant.edges(kept, data=True):
        if target not in kept:
            continue
        properties = {
            str(k): str(v)
            for k, v in data.items()
            if k != "relation" and k not in _GENERATOR_INTERNALS and v is not None
        }
        edges.append(
            {
                "source": source,
                "target": target,
                "relation": str(data.get("relation", "")),
                "properties": properties,
            }
        )
    return sorted(edges, key=lambda e: (e["source"], e["target"], e["relation"]))


def subgraph_for_question(
    plant: nx.DiGraph[str],
    question: dict[str, Any],
    radius: int = 1,
    routes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The plant around one question's evidence: evidence, routes between it, `radius` rings.

    `routes` (from `anchor_routes`) are exported as they are, and their parts belong to the core.
    """
    routes = routes or []
    evidence_ids = evidence_node_ids(plant, list(question["evidence_tags"]))
    core = set(evidence_ids) | route_node_ids(plant, evidence_ids)
    core.update(node_id for route in routes for node_id in route["node_ids"])
    distance = distances_from(plant, core, radius)
    return {
        "question_id": question["question_id"],
        "corpus_id": question["corpus_id"],
        "evidence_ids": evidence_ids,
        "nodes": [_export_node(plant, n, d) for n, d in sorted(distance.items())],
        "edges": _export_edges(plant, set(distance)),
        "routes": routes,
    }


def select_questions(lines: list[str], wanted: list[str] | None) -> list[dict[str, Any]]:
    """The questions with the wanted ids (all of them when `wanted` is None).

    Raises:
        ValueError: a wanted id is not in the file.
    """
    questions = [json.loads(line) for line in lines if line.strip()]
    if wanted is None:
        return questions
    by_id = {question["question_id"]: question for question in questions}
    missing = [question_id for question_id in wanted if question_id not in by_id]
    if missing:
        raise ValueError(f"expected every wanted question id in the file, missing {missing[:5]}")
    return [by_id[question_id] for question_id in wanted]


def main(argv: list[str] | None = None) -> int:
    """Export the subgraphs of the wanted questions of one corpus."""
    # late imports: only needed to rebuild a plant, read from the checkout that PYTHONPATH names
    from plantgraph.graph.schema import EQUIPMENT_CLASSES, VALVE_CLASSES
    from plantgraph.qa.corpus import load_corpus_artifacts

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--ingest-json", required=True, type=Path)
    parser.add_argument("--questions", required=True, type=Path, help="questions.jsonl")
    parser.add_argument("--question-ids", type=Path, help="one id per line; default all")
    parser.add_argument("--radius", type=int, default=1)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    plant = load_corpus_artifacts(args.corpus_id, args.ingest_json).gold.plant
    if plant is None:
        raise ValueError(f"expected a synthetic corpus with a plant graph, got {args.corpus_id!r}")
    wanted = None
    if args.question_ids is not None:
        wanted = args.question_ids.read_text(encoding="utf-8").split()
    lines = args.questions.read_text(encoding="utf-8").splitlines()
    questions = select_questions(lines, wanted)
    items = EQUIPMENT_CLASSES | VALVE_CLASSES
    subgraphs = [
        subgraph_for_question(plant, q, args.radius, anchor_routes(plant, q, items, VALVE_CLASSES))
        for q in questions
    ]
    args.out.write_text(json.dumps({"subgraphs": subgraphs}, indent=1), encoding="utf-8")
    print(f"wrote {len(subgraphs)} subgraphs to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
