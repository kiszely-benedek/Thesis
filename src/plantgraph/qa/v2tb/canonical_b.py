"""The canonical program of V2T-B: what a reader of the B view can work out about untagged valves.

A B system sees the plant only through its view (`NetworkxGraphViewB`): tags, classes, the
`operating_position` of valves and the `line_number` on each `send_to` edge. This module is a
**canonical program** over that view, the reference answer to "is the gold readable?" (design
`v2t-b` §10.6 criterion 9). It:

1. merges the drawings into items and crosses every off-page connector pair (`continues_as`), by
   building the same item graph the B agent walks (`build_item_graph_b`);
2. turns that graph into a plain `networkx` plant of visible facts only;
3. is then read with the same descriptor rules the gold uses (`descriptor.py`: `PlantIndex`,
   `canonical_descriptor`, `resolve_descriptor`), built over this visible plant.

It reads nothing but the view, so it imports no gold. The gold side compares its results with the
gold's own descriptors in `expressiveness_b.py`.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.graph.schema import Relation
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.v2tb.item_graph_b import build_item_graph_b
from plantgraph.qa.v2tb.plant_api_b import LINE_NUMBER
from plantgraph.qa.v2tb.visible import OPERATING_POSITION

_SEND_TO = Relation.SEND_TO.value


def visible_plant(view: GraphView) -> nx.DiGraph[str]:
    """One node per item and one edge per `send_to` hop, from what the B view shows.

    A node holds `node_class`, its `tag` when it prints one and its `operating_position` when it
    has one; an edge holds `relation` and, when drawn, the `line_number`. Node ids are the items'
    ids (the local key of their home drawing). Off-page connector pairs are already crossed.
    """
    graph = build_item_graph_b(view)
    plant: nx.DiGraph[str] = nx.DiGraph()
    for item_id in graph.all_ids():
        record = graph.item(item_id)
        attrs: dict[str, str] = {"node_class": record.node_class}
        if record.tag is not None:
            attrs["tag"] = record.tag
        position = record.properties.get(OPERATING_POSITION)
        if isinstance(position, str):
            attrs[OPERATING_POSITION] = position
        plant.add_node(item_id, **attrs)
    for edge in graph.edges:
        if edge.relation == _SEND_TO:
            attrs = {"relation": _SEND_TO}
            line_number = edge.properties.get(LINE_NUMBER)
            if isinstance(line_number, str):
                attrs[LINE_NUMBER] = line_number
            plant.add_edge(edge.source, edge.target, **attrs)
    return plant
