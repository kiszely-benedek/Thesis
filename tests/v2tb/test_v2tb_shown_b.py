"""T14d R14f check 1: every B item line is exact, on forced-untagged seed 1."""

from __future__ import annotations

from seed1_b import seed1

from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.item_graph_b import build_item_graph_b
from plantgraph.qa.v2tb.shown_b import item_line_misses


def test_every_item_line_is_exact_on_the_plant() -> None:
    plant = seed1()
    graph = build_item_graph_b(plant.view, line_view=True)

    misses = item_line_misses(
        graph, plant.by_local_key, PlantIndex(plant.corpus.plant), plant.corpus.occurrence_map
    )

    assert misses == []
    assert sum("operating_position" in graph.item(i).properties for i in graph.all_ids()) == len(
        plant.by_local_key
    )
