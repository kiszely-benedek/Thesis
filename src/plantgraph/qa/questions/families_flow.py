"""NEIGHBOURS_DOWNSTREAM and FLOW_PATH: questions that follow `send_to` edges (design §9).

`send_to` is the pipe-segment relation: `A -send_to-> B` means material
flows from `A` directly into `B` (`graph/schema.py`). Both families below
walk only this relation — never `send_signal_to`, `control` or
`measured_by`, which are the *instrumentation* wiring `families_loop.py`
reads instead.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question, send_to_successors, tagged_nodes_by_tag
from plantgraph.qa.questions.evidence import Evidence, connector_cut

_TEMPLATE_VERSION = "1"

#: How many `send_to` hops a FLOW_PATH candidate may span. Keeps candidate
#: enumeration bounded on a large plant instead of computing a path between
#: every pair of nodes (design §9, "Sampling": "a bounded forward BFS ...
#: rather than enumerating all pairs"). QA-T7's sampler may pass its own
#: bound; this is only the default used when none is given.
DEFAULT_MAX_PATH_EDGES = 6


def neighbours_downstream_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per node with at least one direct `send_to` successor."""
    cut = connector_cut(manifest)
    questions = []
    for node_id, tag in tagged_nodes_by_tag(plant):
        successor_ids = send_to_successors(plant, node_id)
        if not successor_ids:
            continue
        evidence = Evidence(
            nodes=frozenset({node_id, *successor_ids}),
            edges=frozenset((node_id, successor_id) for successor_id in successor_ids),
        )
        questions.append(
            build_question(
                corpus_id=corpus_id,
                family=QuestionFamily.NEIGHBOURS_DOWNSTREAM,
                template_id="NEIGHBOURS_DOWNSTREAM",
                template_version=_TEMPLATE_VERSION,
                text=f"Which equipment items and valves receive flow directly from {tag}?",
                answer_type=AnswerType.TAG_SET,
                reference=sorted(str(plant.nodes[n]["tag"]) for n in successor_ids),
                evidence=evidence,
                anchors=[tag],
                plant=plant,
                sheets=sheets,
                cut=cut,
                seed=seed,
            )
        )
    return questions


def flow_path_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
    max_path_edges: int = DEFAULT_MAX_PATH_EDGES,
) -> list[Question]:
    """One candidate per `(source, target)` pair within `max_path_edges` `send_to` hops."""
    cut = connector_cut(manifest)
    questions = []
    for source_id, source_tag in tagged_nodes_by_tag(plant):
        paths = _lexicographically_smallest_paths_from(plant, source_id, max_path_edges)
        del paths[source_id]  # a path from a node to itself is not a question
        for target_id in sorted(paths):
            questions.append(
                _flow_path_question(
                    plant,
                    sheets,
                    cut,
                    corpus_id=corpus_id,
                    seed=seed,
                    source_tag=source_tag,
                    target_tag=str(plant.nodes[target_id]["tag"]),
                    path=paths[target_id],
                )
            )
    return questions


def _flow_path_question(
    plant: nx.DiGraph[str],
    sheets: list[SheetGraph],
    cut: frozenset[tuple[str, str]],
    *,
    corpus_id: str,
    seed: int,
    source_tag: str,
    target_tag: str,
    path: list[str],
) -> Question:
    evidence = Evidence(nodes=frozenset(path), edges=frozenset(zip(path, path[1:], strict=False)))
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.FLOW_PATH,
        template_id="FLOW_PATH",
        template_version=_TEMPLATE_VERSION,
        text=(
            f"Trace the process flow path from {source_tag} to {target_tag}. "
            "List every equipment item and valve in order."
        ),
        answer_type=AnswerType.TAG_PATH,
        reference=[str(plant.nodes[node_id]["tag"]) for node_id in path],
        evidence=evidence,
        anchors=[source_tag, target_tag],
        plant=plant,
        sheets=sheets,
        cut=cut,
        seed=seed,
    )


def _lexicographically_smallest_paths_from(
    plant: nx.DiGraph[str], source_id: str, max_hops: int
) -> dict[str, list[str]]:
    """Shortest (by hop count) `send_to` paths from `source_id`, up to `max_hops` edges.

    Among several equal-length shortest paths to the same node, keeps the
    one whose *tag* sequence is lexicographically smallest (design §9,
    FLOW_PATH: "ties broken by the lexicographic tag sequence"). This is
    found a whole BFS layer at a time: every node discovered while expanding
    one layer is reachable in the same number of hops, so the smallest
    candidate path seen while expanding that layer is provably the smallest
    shortest path overall — no need to compare against later, longer paths.
    """
    paths: dict[str, list[str]] = {source_id: [source_id]}
    frontier = [source_id]
    hops = 0
    while frontier and hops < max_hops:
        hops += 1
        newly_reached = _expand_one_layer(plant, frontier, paths)
        paths.update(newly_reached)
        frontier = sorted(newly_reached)
    return paths


def _expand_one_layer(
    plant: nx.DiGraph[str], frontier: list[str], paths: dict[str, list[str]]
) -> dict[str, list[str]]:
    """One BFS layer: for every not-yet-reached successor, the smallest-tag path that reaches it."""
    best_by_target: dict[str, list[str]] = {}
    for node_id in frontier:
        for successor_id in send_to_successors(plant, node_id):
            if successor_id in paths:
                continue
            candidate = [*paths[node_id], successor_id]
            current_best = best_by_target.get(successor_id)
            if current_best is None or _is_smaller_tag_sequence(plant, candidate, current_best):
                best_by_target[successor_id] = candidate
    return best_by_target


def _is_smaller_tag_sequence(plant: nx.DiGraph[str], left: list[str], right: list[str]) -> bool:
    """Compare two equal-length node-id paths by their printed tags, not their internal ids."""
    left_tags = [plant.nodes[node_id]["tag"] for node_id in left]
    right_tags = [plant.nodes[node_id]["tag"] for node_id in right]
    return left_tags < right_tags
