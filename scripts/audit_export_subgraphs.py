"""Cut the plant around each question's gold evidence into plain JSON, for the scorer audit.

Usage (on any checkout that can rebuild the corpus, e.g. a `git archive` copy of the commit that
made the plants; set PYTHONPATH to that copy's `src`):

    python audit_export_subgraphs.py --corpus-id H100g2 --ingest-json CORPUS/ingest.json \
        --questions QUESTIONS/H100g2/questions.jsonl --question-ids ids.txt --out subgraphs.json

The only plantgraph function used is `plantgraph.qa.corpus.load_corpus_artifacts(corpus_id,
ingest_json_path)`, which has the same signature at the E8 commit (4dfad69) and in v2.1. Questions
are read as plain JSON (`question_id`, `evidence_tags`), so no model class is imported either.
The output is read by `plantgraph.qa.audit.excerpt.SubgraphFile`.
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
    plant: nx.DiGraph[str], question: dict[str, Any], radius: int = 1
) -> dict[str, Any]:
    """The plant around one question's evidence: evidence, routes between it, `radius` rings."""
    evidence_ids = evidence_node_ids(plant, list(question["evidence_tags"]))
    core = set(evidence_ids) | route_node_ids(plant, evidence_ids)
    distance = distances_from(plant, core, radius)
    return {
        "question_id": question["question_id"],
        "corpus_id": question["corpus_id"],
        "evidence_ids": evidence_ids,
        "nodes": [_export_node(plant, n, d) for n, d in sorted(distance.items())],
        "edges": _export_edges(plant, set(distance)),
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
    from plantgraph.qa.corpus import load_corpus_artifacts  # late: only needed to rebuild a plant

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
    subgraphs = [subgraph_for_question(plant, q, args.radius) for q in questions]
    args.out.write_text(json.dumps({"subgraphs": subgraphs}, indent=1), encoding="utf-8")
    print(f"wrote {len(subgraphs)} subgraphs to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
