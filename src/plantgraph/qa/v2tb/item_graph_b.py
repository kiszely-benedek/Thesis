"""The plant as one graph of items, with `operating_position` among each item's properties.

The frozen `build_item_graph` keeps only `VISIBLE_NODE_PROPERTIES`. A B corpus also
shows `operating_position`, so this builder runs the same steps (merge drawings into items, fold
flow through untagged pipe parts) and keeps the B keys. On a view whose items carry no position it
returns exactly what the frozen builder returns.

It imports three private helpers of the frozen module rather than copy them: a copy would drift.
"""

from __future__ import annotations

from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.graph_view import ItemRecord as OccurrenceRecord  # one drawing of an item
from plantgraph.qa.plant_api.contraction import contract
from plantgraph.qa.plant_api.item_graph import (
    ItemGraph,
    _drawings_by_item,
    _ids_by_tag,
    _item_record,
)
from plantgraph.qa.plant_api.line_graph import add_line_view
from plantgraph.qa.plant_api.model import ItemRecord
from plantgraph.qa.v2tb.visible import OPERATING_POSITION


def build_item_graph_b(view: GraphView, *, line_view: bool = False) -> ItemGraph:
    """`build_item_graph` for a B corpus: each valve's position is an item property.

    Args:
        view: the resolver-built occurrence graph; its valves may carry `operating_position`.
        line_view: also fold flow through untagged pipe parts, as the frozen builder does.

    Raises:
        ValueError: an identity group's home drawing is missing, or contraction fails.
    """
    occurrences = view.items()
    contraction = contract({o.local_key: o.node_class for o in occurrences}, view.edges())
    drawings = _drawings_by_item(occurrences, contraction)
    items = [
        _with_position(_item_record(item_id, members), members)
        for item_id, members in drawings.items()
    ]
    ids_by_tag = _ids_by_tag(drawings)
    if not line_view:
        return ItemGraph(items, contraction.edges, ids_by_tag)
    line_items, line_edges = add_line_view(items, contraction.edges)
    return ItemGraph(line_items, contraction.edges, ids_by_tag, line_edges)


def _with_position(record: ItemRecord, members: list[OccurrenceRecord]) -> ItemRecord:
    """The record with its home drawing's position added; unchanged when the home shows none."""
    home = next(m for m in members if m.local_key == record.item_id)  # `_item_record` checked it
    position = home.properties.get(OPERATING_POSITION)
    if not isinstance(position, str):
        return record
    return record.model_copy(
        update={"properties": {**record.properties, OPERATING_POSITION: position}}
    )
