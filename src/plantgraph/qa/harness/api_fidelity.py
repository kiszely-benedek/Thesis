"""API-01 check: do the plant API's item edges and visible properties equal the gold plant's.

Edges are API-01 proper (design §3.4); the property check is PG-T1 (plant-graph design §A.2):
what the renderer will print about an item or an edge must be what the gold plant shows.

Gold side: this module reads the unsplit ground-truth plant, so it lives in
the harness and `qa/plant_api/` never imports it. Items are compared by their
printed tag, never by id: the item graph is built from the resolver's output
and the gold plant from the generator, and a tag is what both can show.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.graph import schema
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import RELATION_GROUPS, PropertyValue
from plantgraph.qa.serialize import graphml_safe

#: One edge by tag: (source tag, relation, target tag).
TagEdge = tuple[str, str, str]
#: A node's id, relation and neighbour as the id-level edges of either side list them.
IdEdge = tuple[str, str, str]
#: The property dicts of every edge that shares one by-tag name, sorted.
EdgeProperties = list[dict[str, PropertyValue]]
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
    #: Tags carried by more than one item-graph item: one real item left in pieces. By tag the
    #: pieces look like one item, so the edge sets alone cannot show the break.
    split_tags: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """The gate: no split identity, precision = recall = 1."""
        return not self.split_tags and self.precision == 1.0 and self.recall == 1.0


def compare_edges_by_tag(item_graph: ItemGraph, plant: nx.DiGraph[str]) -> EdgeFidelity:
    """Compare the item graph's edge set with the gold plant's topology edges, by tag."""
    return compare_tag_edges(
        _item_graph_edges(item_graph), plant, repeated_tags(_item_graph_tags(item_graph))
    )


def compare_tag_edges(
    found: set[TagEdge], plant: nx.DiGraph[str], split_tags: tuple[str, ...] = ()
) -> EdgeFidelity:
    """Compare any set of edges-by-tag (item graph, stored layer) with the gold plant's."""
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
        split_tags=split_tags,
    )


def repeated_tags(tags: Iterable[str | None]) -> tuple[str, ...]:
    """Tags that more than one item carries (sorted, a few); untagged items are not counted."""
    counts = Counter(tag for tag in tags if tag is not None)
    return tuple(sorted(tag for tag, n in counts.items() if n > 1)[:_SAMPLE])


def name_nodes(
    node_ids: Iterable[str], edges: list[IdEdge], tag_of: Callable[[str], str | None]
) -> dict[str, str]:
    """Name each node for the by-tag comparison: its tag, else a label from its neighbours.

    An untagged node (an actuator, a connector stub) has no tag. Naming all of them `<untagged>`
    would merge unrelated ones and could hide a wrong edge. Its id differs between the two sides,
    so it is named by what is around it: each (direction, relation, neighbour tag) it has. Two
    untagged nodes stay distinct unless they sit in the same place in the graph.
    """
    around: dict[str, list[str]] = defaultdict(list)
    for source, relation, target in edges:
        around[source].append(f"->{relation}:{tag_of(target) or '?'}")
        around[target].append(f"<-{relation}:{tag_of(source) or '?'}")
    return {
        node: tag_of(node) or f"<untagged {','.join(sorted(around[node]))}>" for node in node_ids
    }


def _item_graph_id_edges(item_graph: ItemGraph) -> list[IdEdge]:
    return [(e.source, e.relation, e.target) for e in item_graph.edges]


def _item_graph_tags(item_graph: ItemGraph) -> list[str | None]:
    return [item_graph.item(item_id).tag for item_id in item_graph.all_ids()]


def _item_graph_names(item_graph: ItemGraph) -> dict[str, str]:
    return name_nodes(
        item_graph.all_ids(),
        _item_graph_id_edges(item_graph),
        lambda item_id: item_graph.item(item_id).tag,
    )


def _item_graph_edges(item_graph: ItemGraph) -> set[TagEdge]:
    names = _item_graph_names(item_graph)
    return {(names[s], relation, names[t]) for s, relation, t in _item_graph_id_edges(item_graph)}


def _gold_id_edges(plant: nx.DiGraph[str]) -> list[IdEdge]:
    """The plant's four topology relations; structural or fallback edges are not API edges."""
    relations = RELATION_GROUPS["any"]
    return [
        (source, relation, target)
        for source, target, attrs in plant.edges(data=True)
        if (relation := attrs.get("relation")) in relations
    ]


def _gold_names(plant: nx.DiGraph[str]) -> dict[str, str]:
    def tag_of(node_id: str) -> str | None:
        tag = plant.nodes[node_id].get("tag")
        return None if tag is None else str(tag)

    return name_nodes(plant.nodes, _gold_id_edges(plant), tag_of)


def _gold_edges(plant: nx.DiGraph[str]) -> set[TagEdge]:
    names = _gold_names(plant)
    return {(names[s], relation, names[t]) for s, relation, t in _gold_id_edges(plant)}


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


def _describe(what: object, found: object, gold: object) -> str:
    return f"{what}: item graph {found} != gold {gold}"


def _item_graph_item_properties(item_graph: ItemGraph) -> dict[str, dict[str, PropertyValue]]:
    """Tag -> properties; a connector stub has no tag and is not compared."""
    records = (item_graph.item(item_id) for item_id in item_graph.all_ids())
    return {r.tag: r.properties for r in records if r.tag is not None}


def _item_graph_edge_properties(item_graph: ItemGraph) -> dict[TagEdge, EdgeProperties]:
    names = _item_graph_names(item_graph)
    return _grouped(
        ((names[e.source], e.relation, names[e.target]), e.properties) for e in item_graph.edges
    )


def _grouped(
    pairs: Iterable[tuple[TagEdge, dict[str, PropertyValue]]],
) -> dict[TagEdge, EdgeProperties]:
    """Edge -> property dicts, sorted; edges sharing one name (look-alike untagged ends) pile up.

    Two different untagged items can look alike (same neighbour tags), so two real edges can
    share one name. Comparing the sorted lists treats them as a multiset, not as a clash.
    """
    grouped: dict[TagEdge, list[dict[str, PropertyValue]]] = defaultdict(list)
    for edge, properties in pairs:
        grouped[edge].append(properties)
    return {edge: sorted(props, key=repr) for edge, props in grouped.items()}


def _gold_item_properties(plant: nx.DiGraph[str]) -> dict[str, dict[str, PropertyValue]]:
    return {
        str(attrs["tag"]): _visible(attrs, _ITEM_PROPERTY_KEYS)
        for _, attrs in plant.nodes(data=True)
        if attrs.get("tag") is not None
    }


def _gold_edge_properties(plant: nx.DiGraph[str]) -> dict[TagEdge, EdgeProperties]:
    names = _gold_names(plant)
    return _grouped(
        (
            (names[source], relation, names[target]),
            _visible(plant.edges[source, target], _EDGE_PROPERTY_KEYS),
        )
        for source, relation, target in _gold_id_edges(plant)
    )


def _visible(attrs: dict[str, object], keys: frozenset[str]) -> dict[str, PropertyValue]:
    return {k: graphml_safe(v) for k, v in sorted(attrs.items()) if k in keys and v is not None}
