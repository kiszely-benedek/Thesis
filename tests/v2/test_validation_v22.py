"""Task T6b (design 17.15 S8): the v2.2 validation wrapper around the frozen validator."""

from __future__ import annotations

import pytest
from t6b_plants import PlantWithRecord, plant_and_record

from plantgraph.benchmark.v2.rules.control_graph import is_control_valve
from plantgraph.benchmark.v2.validation_v22 import untagged_manual_valves, validate_plant_graph_v22
from plantgraph.graph.schema import VALVE_CLASSES
from plantgraph.graph.validation import validate_plant_graph

_SEEDS = (1, 2)


@pytest.mark.parametrize("untagged", [True, False])
@pytest.mark.parametrize("seed", _SEEDS)
def test_a_generated_plant_has_no_violation(seed: int, untagged: bool) -> None:
    built = plant_and_record(seed, untagged=untagged)
    assert validate_plant_graph_v22(built.plant, built.record) == []


@pytest.mark.parametrize("seed", _SEEDS)
def test_it_removes_exactly_the_records_untagged_manual_valves(seed: int) -> None:
    built = plant_and_record(seed, untagged=True)
    frozen = validate_plant_graph(built.plant)
    exempt = untagged_manual_valves(built.plant, built.record)
    assert exempt
    assert len(frozen) == len(exempt)  # the frozen validator's only complaints are these tags
    # independently: every untagged valve of the plant is one of them
    assert exempt == {
        n
        for n, d in built.plant.nodes(data=True)
        if d["node_class"] in VALVE_CLASSES and not d.get("tag")
    }


def test_a_tagged_plant_has_nothing_to_remove() -> None:
    built = plant_and_record(1, untagged=False)
    assert untagged_manual_valves(built.plant, built.record) == frozenset()


def _without_tag(built: PlantWithRecord, node: str) -> PlantWithRecord:
    plant = built.plant.copy()
    del plant.nodes[node]["tag"]
    return PlantWithRecord(plant, built.record)


def test_removing_one_control_valves_tag_gives_exactly_one_violation() -> None:
    built = plant_and_record(1, untagged=True)
    control = next(n for n in sorted(built.plant) if is_control_valve(built.plant, n))
    damaged = _without_tag(built, control)
    violations = validate_plant_graph_v22(damaged.plant, damaged.record)
    assert [(v.kind, v.subject) for v in violations] == [("missing_property", control)]


def test_removing_one_safety_valves_tag_gives_exactly_one_violation() -> None:
    built = plant_and_record(1, untagged=True)
    safety = next(
        n for n, d in sorted(built.plant.nodes(data=True)) if "SafetyValve" in d["node_class"]
    )
    damaged = _without_tag(built, safety)
    violations = validate_plant_graph_v22(damaged.plant, damaged.record)
    assert [(v.kind, v.subject) for v in violations] == [("missing_property", safety)]
