"""Valve positions and fail actions live in the DEXPI file and plan, never in the store (D1 = A).

The proof has four parts: the model really carries both attributes (so the rest is not vacuous);
the schema graph read back from the model is identical with and without them; so is the oracle
graph written straight from the plan; and so are the Cypher load plan and the schema text the
system under test is given.
"""

from __future__ import annotations

import json

import networkx as nx
import pytest
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel
from pydexpi.loaders.json_serializer import JsonSerializer

from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.adapters.pydexpi_valve_attributes import (
    OPERATING_POSITION_ATTRIBUTE,
    annotate_valves,
)
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import GeneratedPlantV2, generate_plant_v2
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.rules.oracle_graph import GraphPlantBuilderV2
from plantgraph.ingest.headline_v2 import HeadlinePresetV2
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.resolution.localize import localize
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

_CONFIG = GeneratorConfigV22(seed=1, n_units=8)  # small, but with every valve role of a unit


@pytest.fixture(scope="module")
def plant() -> GeneratedPlantV2:
    return generate_plant_v2(_CONFIG)


def _strip_model(plant: GeneratedPlantV2) -> DexpiModel:
    """The same plant built from its plan with every position and fail action removed first."""
    builder = DexpiPlantBuilderV2(plant.plan.config.plant_id)
    _strip_plan(plant.plan).write(builder)
    return builder.build()


def _strip_plan(plan: PlantPlanV2) -> PlantPlanV2:
    units = []
    for unit in plan.units:
        inner = unit.instance.plan
        lines = tuple(
            line.model_copy(
                update={
                    "items": tuple(
                        i.model_copy(update={"operating_position": None}) for i in line.items
                    )
                }
            )
            for line in inner.lines
        )
        instruments = tuple(s.model_copy(update={"fail_action": None}) for s in inner.instruments)
        stripped = inner.model_copy(update={"lines": lines, "instruments": instruments})
        instance = unit.instance.model_copy(update={"plan": stripped})
        units.append(unit.model_copy(update={"instance": instance}))
    return plan.model_copy(update={"units": tuple(units)})


def _graph_bytes(graph: nx.DiGraph[str]) -> bytes:
    data = nx.node_link_data(graph, edges="edges")
    return json.dumps(data, sort_keys=True, default=str).encode()


def _load_plan(graph: nx.DiGraph[str], seed: int) -> LoadPlan:
    sheets, _ = split(graph, HeadlinePresetV2().split_config(seed))
    localized, _ = localize(sheets)
    return build_load_plan("strip-proof", localized, resolve(localized), profile="plant")


# ---- the attributes are really there ------------------------------------------------------------


def test_the_dexpi_model_carries_both_attributes(plant: GeneratedPlantV2) -> None:
    text = JsonSerializer().export_to_bytes(plant.model).decode()
    stripped = JsonSerializer().export_to_bytes(_strip_model(plant)).decode()
    assert text.count(OPERATING_POSITION_ATTRIBUTE) > 100
    assert '"fail close"' in text and '"fail open"' in text
    assert OPERATING_POSITION_ATTRIBUTE not in stripped
    assert '"fail close"' not in stripped and '"fail open"' not in stripped


def test_the_model_round_trips_through_json_with_its_attributes(plant: GeneratedPlantV2) -> None:
    serializer = JsonSerializer()
    data = serializer.export_to_bytes(plant.model)
    again = serializer.export_to_bytes(serializer.load_from_bytes(data))
    assert again == data


def test_writing_an_attribute_for_a_valve_that_is_not_in_the_model_is_refused(
    plant: GeneratedPlantV2,
) -> None:
    with pytest.raises(ValueError, match="expected every positioned valve in the model"):
        annotate_valves(_strip_model(plant), {"no-such-valve": "NO"}, {})


# ---- and the store never sees them --------------------------------------------------------------


def test_the_schema_graph_is_byte_identical_with_and_without_the_attributes(
    plant: GeneratedPlantV2,
) -> None:
    with_attributes, _ = plant_graph_v2(plant.model, plant.record)
    without, _ = plant_graph_v2(_strip_model(plant), plant.record)
    assert _graph_bytes(with_attributes) == _graph_bytes(without)
    assert "OperatingPosition" not in _graph_bytes(with_attributes).decode()


def test_the_oracle_graph_is_byte_identical_with_and_without_the_attributes(
    plant: GeneratedPlantV2,
) -> None:
    graphs = []
    for plan in (plant.plan, _strip_plan(plant.plan)):
        oracle = GraphPlantBuilderV2(plan.config.plant_id)
        plan.write(oracle)
        graphs.append(_graph_bytes(oracle.graph))
    assert graphs[0] == graphs[1]


def test_the_load_plan_and_the_schema_text_are_byte_identical_with_and_without_the_attributes(
    plant: GeneratedPlantV2,
) -> None:
    with_attributes, _ = plant_graph_v2(plant.model, plant.record)
    without, _ = plant_graph_v2(_strip_model(plant), plant.record)
    plan_with = _load_plan(with_attributes, _CONFIG.seed)
    plan_without = _load_plan(without, _CONFIG.seed)
    assert plan_with.model_dump_json() == plan_without.model_dump_json()
    assert build_schema_text(plan_with) == build_schema_text(plan_without)
    assert "osition" not in build_schema_text(plan_with)
