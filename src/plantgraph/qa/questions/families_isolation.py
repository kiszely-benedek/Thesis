"""UPSTREAM_ISOLATION: which valves must be closed to cut an item off from everything upstream.

Reads the `send_to` edges backwards from the item. A **route** is one chain
of `send_to` edges leading into the item. On each route the valve to close
is the first operated valve met going upstream (a globe or ball valve, see
`OPERATED_VALVE_CLASSES`); a check valve only lets flow pass one way and is
not operated, so the walk passes straight through it (design §9).
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, OPERATED_VALVE_CLASSES, Relation
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question, nodes_of_classes
from plantgraph.qa.questions.evidence import Evidence, SheetIndex, connector_cut
from plantgraph.qa.questions.templates import upstream_isolation_text

_TEMPLATE_VERSION = "1"


def _send_to_predecessors(plant: nx.DiGraph[str], node_id: str) -> list[str]:
    return sorted(
        p
        for p in plant.predecessors(node_id)
        if plant.edges[p, node_id]["relation"] == Relation.SEND_TO.value
    )


def _visit(
    plant: nx.DiGraph[str],
    node_id: str,
    valves: set[str],
    seen: set[str],
    next_frontier: list[str],
) -> None:
    """Stop at an operated valve; otherwise keep walking through the node."""
    if plant.nodes[node_id]["node_class"] in OPERATED_VALVE_CLASSES:
        valves.add(node_id)
    elif node_id not in seen:
        next_frontier.append(node_id)
    seen.add(node_id)


def _upstream_walk(
    plant: nx.DiGraph[str], node_id: str
) -> tuple[frozenset[str], frozenset[tuple[str, str]]] | None:
    """Walk upstream from `node_id`: `(valves, edges walked)`, or `None` if a route has no valve.

    `None` means the precondition fails: some route ends at a source (a node
    nothing flows into) before meeting an operated valve. There is no hop
    cap (ADR-0029): the `seen` set stops the walk at cycles and re-joins, so
    it visits each node once and always ends.
    """
    valves: set[str] = set()
    edges: set[tuple[str, str]] = set()
    seen = {node_id}
    frontier = [node_id]
    while frontier:
        next_frontier: list[str] = []
        for current in frontier:
            upstream = _send_to_predecessors(plant, current)
            if not upstream:
                return None  # a route with nothing on it to close
            edges.update((p, current) for p in upstream)
            for predecessor in upstream:
                _visit(plant, predecessor, valves, seen, next_frontier)
        frontier = next_frontier
    return frozenset(valves), frozenset(edges)


def upstream_isolation_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per equipment item whose every upstream route has an operated valve."""
    cut = connector_cut(manifest)
    index = SheetIndex.from_sheets(sheets)
    questions = []
    for node_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        walk = _upstream_walk(plant, node_id)
        if walk is None:
            continue
        valves, edges = walk
        tag = str(plant.nodes[node_id]["tag"])
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.UPSTREAM_ISOLATION,
                template_id="UPSTREAM_ISOLATION",
                template_version=_TEMPLATE_VERSION,
                text=upstream_isolation_text(tag),
                answer_type=AnswerType.TAG_SET,
                reference=sorted(str(plant.nodes[v]["tag"]) for v in valves),
                evidence=Evidence(
                    nodes=frozenset({node_id, *(n for edge in edges for n in edge)}),
                    edges=edges,
                ),
                anchors=[tag],
                plant=plant,
                index=index,
                cut=cut,
                seed=seed,
            )
        )
    return questions
