"""The plant as one graph of items, with what a B corpus adds to the valves.

The frozen `build_item_graph` keeps only `VISIBLE_NODE_PROPERTIES`. A B corpus also shows each
valve's `operating_position` and, on an untagged valve, its own line numbers (`line_numbers`, read
from the `send_to` edges that touch it). This builder runs the same steps (merge drawings into
items, fold flow through untagged pipe parts) and adds those two. On a view whose items carry no
position it returns exactly what the frozen builder returns.

It imports three private helpers of the frozen module rather than copy them: a copy would drift.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.graph.schema import VALVE_CLASSES
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
from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord
from plantgraph.qa.v2tb.descriptor import fold_line_number
from plantgraph.qa.v2tb.visible import LINE_NUMBER_SEPARATOR, LINE_NUMBERS, OPERATING_POSITION

_SEND_TO = "send_to"
_EDGE_LINE_NUMBER = "line_number"


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
    if any(OPERATING_POSITION in item.properties for item in items):  # a B corpus; else frozen
        items = with_line_numbers(items, contraction.edges)
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


def with_line_numbers(items: list[ItemRecord], edges: Sequence[ItemEdge]) -> list[ItemRecord]:
    """Every untagged valve gets the line numbers of the `send_to` edges into and out of it."""
    numbers: dict[str, dict[str, str]] = {}  # item id -> folded line number -> as drawn
    for edge in edges:
        written = edge.properties.get(_EDGE_LINE_NUMBER)
        if edge.relation != _SEND_TO or not isinstance(written, str):
            continue
        for end in (edge.source, edge.target):
            numbers.setdefault(end, {}).setdefault(fold_line_number(written), written)
    return [_with_numbers_of(item, numbers.get(item.item_id, {})) for item in items]


def _with_numbers_of(item: ItemRecord, drawn: dict[str, str]) -> ItemRecord:
    """The item with `line_numbers` set when it is an untagged valve that has any."""
    if item.tag is not None or item.node_class not in VALVE_CLASSES or not drawn:
        return item
    ordered = [drawn[key] for key in sorted(drawn)]  # folded order, printed as drawn
    packed = LINE_NUMBER_SEPARATOR.join(ordered)
    return item.model_copy(update={"properties": {**item.properties, LINE_NUMBERS: packed}})


def shows_b_properties(graph: ItemGraph) -> bool:
    """True when the graph is a B corpus's: some valve carries `operating_position`."""
    return any(OPERATING_POSITION in graph.item(i).properties for i in graph.all_ids())
