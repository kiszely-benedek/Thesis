"""Rows of the `plant_lines` store profile: the plant layer plus the line view (qa-tuning-v2 QT-3).

On a v2 drawing two items (pumps, tanks, valves...) are rarely joined directly: untagged pipe
parts (tees, blind flanges) sit between them. The plain `plant` layer keeps those parts as nodes,
so "what is downstream of valve V-1" needs a long path query. This profile adds, on top of the
unchanged plant layer:

- `(:PlantItem)-[:line_to {via_tags, n_fittings}]->(:PlantItem)`: flow from one line item (an
  equipment item or a valve) to the next, folded by `graph/line_view.py`, the same code the plant
  API uses, so both tiers see the same edges;
- a `kind` property on every item (`equipment`, `valve`, `instrument`, ...);
- the umbrella label `:Valve` on every valve;
- `no_inflow` / `no_outflow` (booleans, on line items only): the item is where a line starts or
  stops.

Only the resolver's output is read, never the answer key. Pure data, no `neo4j` import.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema
from plantgraph.graph.line_view import (
    LINE_ITEM_CLASSES,
    LINE_TO_RELATION,
    VALVE_LABEL,
    LineEdge,
    LineEnds,
    fold_line_edges,
    kind_of,
    line_ends,
)
from plantgraph.resolution.models import Resolution
from plantgraph.store.neo4j_rows import NodeRow, RelationshipRow
from plantgraph.store.plant_rows import (
    item_uid,
    plant_node_rows,
    plant_relationship_rows,
    plant_structure_node_rows,
    plant_structure_relationship_rows,
)


def plant_lines_rows(
    corpus_id: str,
    sheets: Sequence[SheetGraph],
    resolution: Resolution,
    asserted_by: Literal["resolver", "oracle"],
) -> tuple[list[NodeRow], list[RelationshipRow]]:
    """The `plant` profile's rows, with `kind`, `Valve`, line-end marks and the `line_to` edges."""
    edges, ends = line_view_of_plant(resolution.plant)
    node_rows = plant_structure_node_rows(corpus_id, sheets, resolution) + [
        _with_line_properties(corpus_id, row, ends)
        for row in plant_node_rows(corpus_id, sheets, resolution)
    ]
    relationship_rows = (
        plant_structure_relationship_rows(corpus_id, sheets, resolution)
        + plant_relationship_rows(corpus_id, sheets, resolution, asserted_by)
        + [_line_to_row(corpus_id, edge) for edge in edges]
    )
    return node_rows, relationship_rows


def line_view_of_plant(plant: nx.DiGraph[str]) -> tuple[list[LineEdge], LineEnds]:
    """The line edges of a merged plant, and which line items start or stop a line.

    Raises:
        ValueError: a plant node has no `node_class`.
    """
    classes = {key: _node_class(plant, key) for key in plant.nodes}
    tags = {key: _tag(plant.nodes[key]) for key in plant.nodes}
    flow = [
        (source, target)
        for source, target, attrs in plant.edges(data=True)
        if attrs.get("relation") == schema.Relation.SEND_TO.value
    ]
    edges = fold_line_edges(classes, tags, flow)
    line_items = [key for key, node_class in classes.items() if node_class in LINE_ITEM_CLASSES]
    return edges, line_ends(line_items, edges)


def _node_class(plant: nx.DiGraph[str], key: str) -> str:
    node_class = plant.nodes[key].get("node_class")
    if not isinstance(node_class, str):
        raise ValueError(f"expected plant node {key!r} to have a node_class, found {node_class!r}")
    return node_class


def _tag(attrs: dict[str, object]) -> str | None:
    tag = attrs.get("tag")
    return tag if isinstance(tag, str) else None


def _with_line_properties(corpus_id: str, row: NodeRow, ends: LineEnds) -> NodeRow:
    """`kind`, the `Valve` label for a valve, and line-end marks for a line item."""
    node_class = str(row.props["node_class"])
    kind = kind_of(node_class)
    props = {**row.props, "kind": kind}
    labels = row.labels
    if kind == "valve" and VALVE_LABEL not in labels:
        labels = (*labels, VALVE_LABEL)
    if node_class in LINE_ITEM_CLASSES:
        home_key = _home_key(corpus_id, row.uid)
        props["no_inflow"] = home_key in ends.no_inflow
        props["no_outflow"] = home_key in ends.no_outflow
    return NodeRow(labels, row.uid, props)


def _home_key(corpus_id: str, row_uid: str) -> str:
    prefix = item_uid(corpus_id, "")
    if not row_uid.startswith(prefix):
        raise ValueError(f"expected a plant item uid starting with {prefix!r}, found {row_uid!r}")
    return row_uid[len(prefix) :]


def _line_to_row(corpus_id: str, edge: LineEdge) -> RelationshipRow:
    props: dict[str, object] = {"via_tags": list(edge.via_tags), "n_fittings": edge.n_fittings}
    return RelationshipRow(
        LINE_TO_RELATION, item_uid(corpus_id, edge.source), item_uid(corpus_id, edge.target), props
    )
