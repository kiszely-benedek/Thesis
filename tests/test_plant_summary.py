"""Properties of `summarize_plant` on a real generated plant (`plant-generator.md` §3.2)."""

from __future__ import annotations

import networkx as nx

from plantgraph.adapters.plant_summary import summarize_plant
from plantgraph.adapters.pydexpi_adapter import plant_graph
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.graph import schema


def test_summary_counts_match_the_underlying_graph() -> None:
    plant, _ = plant_graph(generate_plant(GeneratorConfig(seed=1, n_units=3)))
    summary = summarize_plant(plant)

    assert summary.n_nodes == plant.number_of_nodes()
    assert summary.n_edges == plant.number_of_edges()
    assert summary.n_units == 3
    assert summary.n_equipment == sum(
        1 for _, attrs in plant.nodes(data=True) if attrs["node_class"] in schema.EQUIPMENT_CLASSES
    )
    assert summary.n_control_loops == sum(
        1
        for _, attrs in plant.nodes(data=True)
        if attrs["node_class"] == schema.NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value
    )
    assert sum(summary.streams_per_kind.values()) == summary.n_streams
    assert summary.max_streams_out_of_one_equipment >= 1


def test_summary_is_empty_for_an_empty_graph() -> None:
    summary = summarize_plant(nx.DiGraph())
    assert summary.n_nodes == 0
    assert summary.n_edges == 0
    assert summary.n_units == 0
    assert summary.n_equipment == 0
    assert summary.n_streams == 0
    assert summary.n_control_loops == 0
    assert summary.max_streams_out_of_one_equipment == 0
