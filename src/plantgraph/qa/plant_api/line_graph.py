"""The line view of an item graph: `line_to` edges, a `kind` on every item, line-end marks.

On a v2 drawing, items are joined through untagged pipe parts (tees, blind flanges...). The
line view (`graph/line_view.py`, pure) folds those parts away; this module applies it to the
merged items and edges, so the plant API can follow "what is downstream of this valve" from one
line item to the next. It reads only the resolver's output, never the answer key.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.graph.line_view import (
    LINE_ITEM_CLASSES,
    LineEdge,
    LineEnds,
    fold_line_edges,
    kind_of,
    line_ends,
)
from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord

LINE_RELATION = "line_to"


def add_line_view(
    items: Sequence[ItemRecord], edges: Sequence[ItemEdge]
) -> tuple[list[ItemRecord], list[ItemEdge]]:
    """The items with `kind` and line-end marks filled in, and the `line_to` edges.

    Raises:
        ValueError: an item's class is not a drawing item (`kind_of`), or a flow edge touches an
            unknown item.
    """
    classes = {item.item_id: item.node_class for item in items}
    tags = {item.item_id: item.tag for item in items}
    flow = [(edge.source, edge.target) for edge in edges if edge.relation == "send_to"]
    line_edges = fold_line_edges(classes, tags, flow)
    line_item_ids = [i for i, node_class in classes.items() if node_class in LINE_ITEM_CLASSES]
    ends = line_ends(line_item_ids, line_edges)
    return [_with_kind(item, ends) for item in items], [_as_item_edge(e) for e in line_edges]


def _with_kind(item: ItemRecord, ends: LineEnds) -> ItemRecord:
    # only a line item can be a line's start or stop; a fitting or an instrument is never marked
    marks = ends.marks_of(item.item_id) if item.node_class in LINE_ITEM_CLASSES else ()
    return item.model_copy(update={"kind": kind_of(item.node_class), "line_marks": marks})


def _as_item_edge(edge: LineEdge) -> ItemEdge:
    return ItemEdge(
        source=edge.source,
        target=edge.target,
        relation=LINE_RELATION,
        via_tags=edge.via_tags,
        n_fittings=edge.n_fittings,
    )
