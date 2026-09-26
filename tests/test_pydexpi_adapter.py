"""Invariants of the pyDEXPI model -> schema `DiGraph` adapter (`plant-generator.md` §3.4, §3.6).

`SEEDS` is small, because every element builds a real pyDEXPI model and runs it
through the `GraphAbstractor` — slower than the oracle-builder-based
`test_generator.py`, so only the invariants specific to the adapter itself are
rerun here (§9 step 3a: "using small sizes").
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import networkx as nx
import pytest
from pydexpi.loaders.graph_loader import GraphLoader
from pydexpi.loaders.json_serializer import JsonSerializer

from graph_plant_builder import GraphPlantBuilder
from plantgraph.adapters.pydexpi_adapter import LinearGraphLoader, plant_graph
from plantgraph.adapters.pydexpi_builder import GeneratedPlant, generate_plant
from plantgraph.adapters.pydexpi_io import load_json, save_json
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.rejoin import rejoin
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.strategies import STRATEGIES
from plantgraph.graph import schema, validation

SEEDS = range(5)


def _plant(seed: int, **overrides: object) -> nx.DiGraph[str]:
    plant, _ = plant_graph(generate_plant(GeneratorConfig(seed=seed, **overrides)))
    return plant


def _sorted_nodes(graph: nx.DiGraph[str]) -> list[tuple[str, dict[str, object]]]:
    return sorted((node_id, dict(attrs)) for node_id, attrs in graph.nodes(data=True))


def _sorted_edges(graph: nx.DiGraph[str]) -> list[tuple[str, str, dict[str, object]]]:
    return sorted((source, target, dict(attrs)) for source, target, attrs in graph.edges(data=True))


# ---- invariant 1: basic structure ------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_plant_graph_is_a_digraph_without_self_loops(seed: int) -> None:
    plant = _plant(seed)
    assert isinstance(plant, nx.DiGraph)
    assert nx.number_of_selfloops(plant) == 0


# ---- invariant 2: schema validity ----------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_plant_graph_is_schema_valid(seed: int) -> None:
    assert validation.validate_plant_graph(_plant(seed)) == []


# ---- invariant 3: reproducibility ---------------------------------------------------------


def test_same_seed_gives_the_same_graph_and_report() -> None:
    config = GeneratorConfig(seed=7)
    plant_a, report_a = plant_graph(generate_plant(config))
    plant_b, report_b = plant_graph(generate_plant(config))
    assert _sorted_nodes(plant_a) == _sorted_nodes(plant_b)
    assert _sorted_edges(plant_a) == _sorted_edges(plant_b)
    assert report_a == report_b


def test_seed_0_and_seed_1_differ() -> None:
    assert _sorted_nodes(_plant(0)) != _sorted_nodes(_plant(1))


# ---- invariant 5: basic connectivity -----------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_plant_graph_is_weakly_connected_and_unit1s_first_equipment_has_in_degree_zero(
    seed: int,
) -> None:
    config = GeneratorConfig(seed=seed)
    plant, _ = plant_graph(generate_plant(config))
    assert nx.is_weakly_connected(plant)
    assert plant.in_degree(f"{config.plant_id}-u1-eq1") == 0


# ---- invariant 6: at least one branch point across the seeds ----------------------------


def test_at_least_one_equipment_has_two_or_more_outgoing_streams_across_seeds() -> None:
    max_out_degree = 0
    for seed in SEEDS:
        plant = _plant(seed)
        for node_id, attrs in plant.nodes(data=True):
            if attrs["node_class"] not in schema.EQUIPMENT_CLASSES:
                continue
            max_out_degree = max(max_out_degree, _send_to_out_degree(plant, node_id))
    assert max_out_degree >= 2


def _send_to_out_degree(plant: nx.DiGraph[str], node_id: str) -> int:
    return sum(
        1
        for _, _, attrs in plant.out_edges(node_id, data=True)
        if attrs["relation"] == schema.Relation.SEND_TO.value
    )


# ---- invariant 9: byte-identical JSON export -----------------------------------------------------


def test_json_export_is_byte_identical_for_the_same_seed_and_differs_across_seeds() -> None:
    serializer = JsonSerializer()
    config = GeneratorConfig(seed=3)
    bytes_a = serializer.export_to_bytes(generate_plant(config).model)
    bytes_b = serializer.export_to_bytes(generate_plant(config).model)
    assert bytes_a == bytes_b

    bytes_other_seed = serializer.export_to_bytes(generate_plant(GeneratorConfig(seed=4)).model)
    assert bytes_a != bytes_other_seed


# ---- invariant 10: no uuid-shaped id ---------------------------------------------------------

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def test_no_dexpi_object_has_a_uuid_shaped_id() -> None:
    model = generate_plant(GeneratorConfig(seed=2)).model
    complete = LinearGraphLoader().dexpi_to_graph(model)
    uuid_shaped = [node_id for node_id in complete.nodes if _UUID_PATTERN.match(str(node_id))]
    assert uuid_shaped == [], f"uuid-shaped id(s) found: {uuid_shaped}"


# ---- invariant 11: linear loader == stock GraphLoader ----------------------------------------


@pytest.mark.parametrize("seed", range(5))
def test_linear_graph_loader_equals_the_stock_graph_loader(seed: int) -> None:
    # the stock GraphLoader is quadratic, so this runs with small n_units (§9 step 3a)
    model = generate_plant(GeneratorConfig(seed=seed, n_units=5)).model
    linear = LinearGraphLoader().dexpi_to_graph(model)
    stock = GraphLoader().dexpi_to_graph(model)

    assert list(linear.nodes) == list(stock.nodes)
    assert _canonical_nodes(linear) == _canonical_nodes(stock)
    assert _canonical_edges(linear) == _canonical_edges(stock)


def _canonical_nodes(graph: nx.MultiDiGraph[str]) -> list[tuple[str, list[tuple[str, object]]]]:
    return sorted((node_id, sorted(attrs.items())) for node_id, attrs in graph.nodes(data=True))


def _canonical_edges(
    graph: nx.MultiDiGraph[str],
) -> list[tuple[str, str, int, list[tuple[str, object]]]]:
    return sorted(
        (source, target, key, sorted(attrs.items()))
        for source, target, key, attrs in graph.edges(keys=True, data=True)
    )


# ---- invariant 12: complete coverage --------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_conversion_report_has_no_unmapped_topology_edges_and_resolves_every_valve_unit(
    seed: int,
) -> None:
    _, report = plant_graph(generate_plant(GeneratorConfig(seed=seed)))
    assert report.edges_dropped_per_label == {}
    assert report.valve_units_unresolved == 0


# ---- invariant 13: JSON round trip --------------------------------------------------------------


def test_json_round_trip_gives_the_same_plant_graph(tmp_path: Path) -> None:
    generated = generate_plant(GeneratorConfig(seed=5))
    plant_before, _ = plant_graph(generated)

    save_json(generated.model, tmp_path, "plant")
    loaded_model = load_json(tmp_path, "plant")
    plant_after, _ = plant_graph(GeneratedPlant(model=loaded_model, record=generated.record))

    assert _sorted_nodes(plant_before) == _sorted_nodes(plant_after)
    assert _sorted_edges(plant_before) == _sorted_edges(plant_after)


# ---- invariant 14: sorted insertion order ------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_plant_graph_nodes_and_edges_are_inserted_in_sorted_order(seed: int) -> None:
    plant = _plant(seed)
    assert list(plant.nodes) == sorted(plant.nodes)
    assert list(plant.edges) == sorted(plant.edges)


# ---- oracle-equality invariant (the "3-pyDEXPI" boxed note) --------------------------------

#: both sides carry these node properties; besides them, the real pipeline
#: produces nothing the oracle doesn't — the §4.8 data stays switched off
#: (step 3b, out of scope for this step)
_COMMON_NODE_KEYS = ("node_class", "tag", "plant_id", "unit_id", "loop_tag", "measured_variable")
#: `stream_kind` only appears on real-pipeline edges (the oracle doesn't write it) — not shared
_COMMON_EDGE_KEYS = ("relation", "line_number", "fluid_code")


def _project_nodes(
    graph: nx.DiGraph[str], keys: Iterable[str]
) -> list[tuple[str, tuple[tuple[str, object], ...]]]:
    return sorted(
        (node_id, tuple((key, attrs[key]) for key in keys if key in attrs))
        for node_id, attrs in graph.nodes(data=True)
    )


def _project_edges(
    graph: nx.DiGraph[str], keys: Iterable[str]
) -> list[tuple[str, str, tuple[tuple[str, object], ...]]]:
    return sorted(
        (source, target, tuple((key, attrs[key]) for key in keys if key in attrs))
        for source, target, attrs in graph.edges(data=True)
    )


@pytest.mark.parametrize("seed", range(5))
def test_plant_graph_matches_the_oracle_builder_on_their_shared_properties(seed: int) -> None:
    config = GeneratorConfig(seed=seed)
    real_plant, _ = plant_graph(generate_plant(config))

    oracle_builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, oracle_builder)
    oracle_plant = oracle_builder.graph

    assert _project_nodes(real_plant, _COMMON_NODE_KEYS) == _project_nodes(
        oracle_plant, _COMMON_NODE_KEYS
    )
    assert _project_edges(real_plant, _COMMON_EDGE_KEYS) == _project_edges(
        oracle_plant, _COMMON_EDGE_KEYS
    )


# ---- splitter integration on a real generated plant (invariants 7, 8 on the real pipeline) ----


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_split_then_rejoin_reproduces_a_pydexpi_generated_plant(strategy_name: str) -> None:
    plant = _plant(seed=1)
    split_config = SplitConfig(strategy=strategy_name, sheet_equipment_budget=3, seed=0)
    sheets, manifest = split(plant, split_config)
    rejoined = rejoin(sheets, manifest)

    assert set(rejoined.nodes) == set(plant.nodes)
    for node_id, attrs in plant.nodes(data=True):
        assert rejoined.nodes[node_id] == attrs, f"node {node_id} attributes differ"
    assert set(rejoined.edges) == set(plant.edges)
    for source, target, attrs in plant.edges(data=True):
        assert rejoined.edges[source, target] == attrs, f"edge ({source}, {target}) differs"

    for sheet in sheets:
        violations = validation.validate_sheet_graph(sheet.graph)
        assert violations == [], f"sheet {sheet.sheet_id}: {violations}"
