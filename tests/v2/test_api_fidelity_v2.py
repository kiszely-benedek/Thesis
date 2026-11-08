"""API-01 (edges and properties) on a correct-by-construction v2 plant: it must pass exactly."""

from __future__ import annotations

from corpus_v2 import corpus

from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.api_fidelity import compare_edges_by_tag, compare_properties_by_tag
from plantgraph.qa.plant_api.item_graph import build_item_graph


def test_api_01_passes_on_a_generated_v2_plant() -> None:
    built = corpus()
    view = NetworkxGraphView("T", built.localized_sheets, built.resolution)
    graph = build_item_graph(view)

    edges = compare_edges_by_tag(graph, built.plant)
    assert edges.split_tags == ()
    assert (edges.precision, edges.recall) == (1.0, 1.0), edges
    assert edges.n_gold > 100  # the plant is big enough to hold untagged actuators and stubs
    assert compare_properties_by_tag(graph, built.plant).all_match
