"""API-01 check: do the plant API's item edges and visible properties equal the gold plant's.

Edges are API-01 proper (design §3.4); the property check is PG-T1 (plant-graph design §A.2):
what the renderer will print about an item or an edge must be what the gold plant shows.

Gold side: this module reads the unsplit ground-truth plant, so it lives in
the harness and `qa/plant_api/` never imports it. Items are compared by their
printed tag, never by id: the item graph is built from the resolver's output
and the gold plant from the generator, and a tag is what both can show.
"""

from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.graph import schema
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import RELATION_GROUPS, PropertyValue
from plantgraph.qa.serialize import graphml_safe

#: One edge by tag: (source tag, relation, target tag).
TagEdge = tuple[str, str, str]
_UNTAGGED = "<untagged>"
_SAMPLE = 5
_ITEM_PROPERTY_KEYS = schema.VISIBLE_NODE_PROPERTIES - {"node_class"}
_EDGE_PROPERTY_KEYS = schema.VISIBLE_EDGE_PROPERTIES - {"relation"}


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


class PropertyFidelity(BaseModel):
    """How many tagged items and edges carry exactly the gold plant's visible properties."""

    model_config = ConfigDict(frozen=True)

    n_items: int
    n_items_matching: int
    n_edges: int
    n_edges_matching: int
    #: A few differing items or edges (sorted): `<what>: item graph <props> != gold <props>`.
    mismatch_sample: tuple[str, ...]

    @property
    def all_match(self) -> bool:
        """True when every compared item and edge matched."""
        return self.n_items == self.n_items_matching and self.n_edges == self.n_edges_matching


def compare_properties_by_tag(item_graph: ItemGraph, plant: nx.DiGraph[str]) -> PropertyFidelity:
    """Compare each tagged item's and each edge's visible properties with the gold plant's."""
    gold_items = _gold_item_properties(plant)
    gold_edges = _gold_edge_properties(plant)
    items = _item_graph_item_properties(item_graph)
    edges = _item_graph_edge_properties(item_graph)
    wrong_items = {tag for tag, props in items.items() if gold_items.get(tag) != props}
    wrong_edges = {edge for edge, props in edges.items() if gold_edges.get(edge) != props}
    mismatches = [_describe(t, items[t], gold_items.get(t)) for t in wrong_items]
    mismatches += [_describe(e, edges[e], gold_edges.get(e)) for e in wrong_edges]
    return PropertyFidelity(
        n_items=len(items),
        n_items_matching=len(items) - len(wrong_items),
        n_edges=len(edges),
        n_edges_matching=len(edges) - len(wrong_edges),
        mismatch_sample=tuple(sorted(mismatches)[:_SAMPLE]),
    )


def _describe(what: object, found: dict[str, PropertyValue], gold: object) -> str:
    return f"{what}: item graph {found} != gold {gold}"


def _item_graph_item_properties(item_graph: ItemGraph) -> dict[str, dict[str, PropertyValue]]:
    """Tag -> properties; a connector stub has no tag and is not compared."""
    records = (item_graph.item(item_id) for item_id in item_graph.all_ids())
    return {r.tag: r.properties for r in records if r.tag is not None}


def _item_graph_edge_properties(
    item_graph: ItemGraph,
) -> dict[TagEdge, dict[str, PropertyValue]]:
    return {
        (
            item_graph.item(edge.source).tag or _UNTAGGED,
            edge.relation,
            item_graph.item(edge.target).tag or _UNTAGGED,
        ): edge.properties
        for edge in item_graph.edges
    }


def _gold_item_properties(plant: nx.DiGraph[str]) -> dict[str, dict[str, PropertyValue]]:
    return {
        str(attrs["tag"]): _visible(attrs, _ITEM_PROPERTY_KEYS)
        for _, attrs in plant.nodes(data=True)
        if attrs.get("tag") is not None
    }


def _gold_edge_properties(plant: nx.DiGraph[str]) -> dict[TagEdge, dict[str, PropertyValue]]:
    relations = RELATION_GROUPS["any"]
    return {
        (str(plant.nodes[source]["tag"]), relation, str(plant.nodes[target]["tag"])): _visible(
            attrs, _EDGE_PROPERTY_KEYS
        )
        for source, target, attrs in plant.edges(data=True)
        if (relation := attrs.get("relation")) in relations
    }


def _visible(attrs: dict[str, object], keys: frozenset[str]) -> dict[str, PropertyValue]:
    return {k: graphml_safe(v) for k, v in sorted(attrs.items()) if k in keys and v is not None}
