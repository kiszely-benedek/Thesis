"""What the B agent is shown: the exactness check on its item lines (design §10.9 R14f, check 1).

`item_line_misses` compares every item line with the frozen line plus exactly the brackets the
gold plant calls for (a position on a positioned valve, the plant's line numbers on an untagged
valve). It reads the gold plant, so this module is gold side. Nothing here calls a model.
"""

from __future__ import annotations

from collections.abc import Mapping

from plantgraph.graph.schema import VALVE_CLASSES
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import ItemRecord
from plantgraph.qa.plant_api.results import item_line
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.plant_api_b import item_line_b
from plantgraph.resolution.localize import OccurrenceMap

# ---- 1. exactness -------------------------------------------------------------------------------


def expected_item_line(
    item: ItemRecord,
    positions: Mapping[str, str],
    plant_index: PlantIndex,
    occurrence_map: OccurrenceMap,
) -> str:
    """The line the plant calls for: the frozen line, then the position, then the line numbers."""
    line = item_line(item)
    if item.item_id in positions:
        line += f" [operating_position {positions[item.item_id]}]"
    node_id = occurrence_map.original_node_id(item.item_id)
    if item.node_class in VALVE_CLASSES and plant_index.tag_of(node_id) is None:
        keys = plant_index.line_numbers(node_id)
        written = ", ".join(plant_index.line_as_written(key) for key in keys)
        if keys:
            line += f" [{'lines' if len(keys) > 1 else 'line'} {written}]"
    return line


def item_line_misses(
    graph: ItemGraph,
    positions: Mapping[str, str],
    plant_index: PlantIndex,
    occurrence_map: OccurrenceMap,
) -> list[str]:
    """Item ids whose B line differs from the expected one (empty list = 100 % exact)."""
    return [
        item_id
        for item_id in graph.all_ids()
        if item_line_b(graph.item(item_id))
        != expected_item_line(graph.item(item_id), positions, plant_index, occurrence_map)
    ]
