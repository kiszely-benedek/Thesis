"""`reach_from` ranks BFS layers instead of comparing tag sequences; the answer must not change.

The reference here is the plain definition: among equal-length shortest paths, the one whose
tag sequence is lexicographically smallest wins. v2 plants have many such ties (parallel
branches between two tees), so they are the right place to check the shortcut.
"""

from __future__ import annotations

import networkx as nx
from corpus_v2 import corpus

from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.qa.questions.common import nodes_of_classes, send_to_successors
from plantgraph.qa.questions.evidence import SheetIndex
from plantgraph.qa.questions.families_flow import layer_sort_tags, reach_from


def _smallest_tag_sequence_parents(
    plant: nx.DiGraph[str], successors: dict[str, list[str]], source: str
) -> dict[str, str | None]:
    """The definition, spelled out: keep every node's full tag sequence and compare them."""

    def label(node_id: str) -> str:
        return str(plant.nodes[node_id].get("tag", node_id))

    sequence = {source: [label(source)]}
    parent: dict[str, str | None] = {source: None}
    frontier = [source]
    while frontier:
        found: dict[str, str] = {}
        for node_id in frontier:
            for successor in successors[node_id]:
                if successor in parent:
                    continue
                best = found.get(successor)
                if best is None or sequence[node_id] < sequence[best]:
                    found[successor] = node_id
        for node_id, chosen in found.items():
            sequence[node_id] = [*sequence[chosen], label(node_id)]
            parent[node_id] = chosen
        frontier = sorted(found)
    return parent


def test_ranked_layers_choose_the_same_parents_as_comparing_tag_sequences() -> None:
    built = corpus(12)
    plant = built.plant
    index = SheetIndex.from_sheets(built.sheets, built.manifest)
    successors = {node_id: send_to_successors(plant, node_id) for node_id in plant.nodes}
    sources = nodes_of_classes(plant, EQUIPMENT_CLASSES)[:12]
    assert sources
    tags = layer_sort_tags(plant)
    for source in sources:
        reached = reach_from(plant, successors, source, index)
        expected = _smallest_tag_sequence_parents(plant, successors, source)
        assert {n: r.parent for n, r in reached.items()} == expected, source
        # the prebuilt tag table is only a speed-up: same parents, same k
        assert reach_from(plant, successors, source, index, tags=tags) == reached, source
