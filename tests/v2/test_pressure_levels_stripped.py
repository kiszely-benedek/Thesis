"""The hidden pressure levels live in the answer key only: no output the system sees carries one.

The proof follows `test_valve_positions_stripped.py`: the same plant is built with its levels and
with the levels removed from the record, and everything the system under test can read must be
byte-identical. The levels are really there first, so the comparison is not vacuous.
"""

from __future__ import annotations

import json
from dataclasses import replace

import networkx as nx
import pytest
from pydexpi.loaders.json_serializer import JsonSerializer

from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import GeneratedPlantV2, generate_plant_v2
from plantgraph.benchmark.v2.record_v22 import GenerationRecordV22
from plantgraph.benchmark.v2.rules.oracle_graph import GraphPlantBuilderV2
from plantgraph.ingest.headline_v2 import HeadlinePresetV2
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.resolution.localize import localize
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

_CONFIG = GeneratorConfigV22(seed=1, n_units=8)  # small, but with a pump, a letdown and a vacuum


@pytest.fixture(scope="module")
def plant() -> GeneratedPlantV2:
    return generate_plant_v2(_CONFIG)


def _without_levels(plant: GeneratedPlantV2) -> GeneratedPlantV2:
    """The same plant whose record has lost its pressure levels."""
    record = plant.record
    assert isinstance(record, GenerationRecordV22)
    emptied = record.hidden_state.model_copy(update={"segment_level": {}})
    return replace(plant, record=record.model_copy(update={"hidden_state": emptied}))


def _graph_bytes(graph: nx.DiGraph[str]) -> bytes:
    data = nx.node_link_data(graph, edges="edges")
    return json.dumps(data, sort_keys=True, default=str).encode()


def _oracle_bytes(plant: GeneratedPlantV2) -> bytes:
    oracle = GraphPlantBuilderV2(plant.plan.config.plant_id)
    plant.plan.write(oracle)
    return _graph_bytes(oracle.graph)


def _load_plan(graph: nx.DiGraph[str]) -> LoadPlan:
    sheets, _ = split(graph, HeadlinePresetV2().split_config(_CONFIG.seed))
    localized, _ = localize(sheets)
    return build_load_plan("strip-proof", localized, resolve(localized), profile="plant")


def test_the_record_really_holds_levels(plant: GeneratedPlantV2) -> None:
    assert isinstance(plant.record, GenerationRecordV22)
    levels = plant.record.hidden_state.segment_level
    assert len(levels) > 100
    assert len(set(levels.values())) >= 3
    assert _without_levels(plant).record.hidden_state.segment_level == {}  # type: ignore[attr-defined]


def test_the_plan_dump_and_the_dexpi_model_carry_no_level(plant: GeneratedPlantV2) -> None:
    dexpi = JsonSerializer().export_to_bytes(plant.model).decode()
    plan = plant.plan.model_dump_json()
    for text in (dexpi, plan):
        assert "segment_level" not in text
        assert "PressureLevel" not in text
    # the plan is the same object whatever the record holds: the levels never entered it
    assert _without_levels(plant).plan.model_dump_json() == plan


def test_the_schema_graph_is_byte_identical_with_and_without_the_levels(
    plant: GeneratedPlantV2,
) -> None:
    with_levels, _ = plant_graph_v2(plant.model, plant.record)
    without, _ = plant_graph_v2(plant.model, _without_levels(plant).record)
    assert _graph_bytes(with_levels) == _graph_bytes(without)


def test_the_oracle_graph_is_byte_identical_with_and_without_the_levels(
    plant: GeneratedPlantV2,
) -> None:
    assert _oracle_bytes(plant) == _oracle_bytes(_without_levels(plant))


def test_the_load_plan_and_the_schema_text_are_byte_identical_with_and_without_the_levels(
    plant: GeneratedPlantV2,
) -> None:
    with_levels, _ = plant_graph_v2(plant.model, plant.record)
    without, _ = plant_graph_v2(plant.model, _without_levels(plant).record)
    plan_with, plan_without = _load_plan(with_levels), _load_plan(without)
    assert plan_with.model_dump_json() == plan_without.model_dump_json()
    assert build_schema_text(plan_with) == build_schema_text(plan_without)
    assert "evel" not in build_schema_text(plan_with)
