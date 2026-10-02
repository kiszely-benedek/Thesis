"""API-01 check: do the plant API's item edges equal the gold plant's edges (design §3.4).

Gold side: this module reads the unsplit ground-truth plant, so it lives in
the harness and `qa/plant_api/` never imports it. Items are compared by their
printed tag, never by id: the item graph is built from the resolver's output
and the gold plant from the generator, and a tag is what both can show.
"""

from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import RELATION_GROUPS

#: One edge by tag: (source tag, relation, target tag).
TagEdge = tuple[str, str, str]
_UNTAGGED = "<untagged>"
_SAMPLE = 5


class EdgeFidelity(BaseModel):
    """Precision and recall of the item graph's edges against the gold plant's."""

    model_config = ConfigDict(frozen=True)

    n_gold: int
    n_item_graph: int
    n_matched: int
    #: Share of item-graph edges that are gold edges; 1.0 when there are no item-graph edges.
    precision: float
    #: Share of gold edges the item graph has; 1.0 when there are no gold edges.
    recall: float
    #: A few gold edges the item graph lacks (sorted), for debugging.
    missing_sample: tuple[TagEdge, ...]
    #: A few item-graph edges the gold plant lacks (sorted), for debugging.
    extra_sample: tuple[TagEdge, ...]


def compare_edges_by_tag(item_graph: ItemGraph, plant: nx.DiGraph[str]) -> EdgeFidelity:
    """Compare the item graph's edge set with the gold plant's topology edges, by tag."""
    found = _item_graph_edges(item_graph)
    gold = _gold_edges(plant)
    matched = found & gold
    return EdgeFidelity(
        n_gold=len(gold),
        n_item_graph=len(found),
        n_matched=len(matched),
        precision=len(matched) / len(found) if found else 1.0,
        recall=len(matched) / len(gold) if gold else 1.0,
        missing_sample=tuple(sorted(gold - found)[:_SAMPLE]),
        extra_sample=tuple(sorted(found - gold)[:_SAMPLE]),
    )


def _item_graph_edges(item_graph: ItemGraph) -> set[TagEdge]:
    return {
        (
            item_graph.item(edge.source).tag or _UNTAGGED,
            edge.relation,
            item_graph.item(edge.target).tag or _UNTAGGED,
        )
        for edge in item_graph.edges
    }


def _gold_edges(plant: nx.DiGraph[str]) -> set[TagEdge]:
    """The plant's four topology relations; structural or fallback edges are not API edges."""
    relations = RELATION_GROUPS["any"]
    return {
        (str(plant.nodes[source]["tag"]), relation, str(plant.nodes[target]["tag"]))
        for source, target, attrs in plant.edges(data=True)
        if (relation := attrs.get("relation")) in relations
    }
