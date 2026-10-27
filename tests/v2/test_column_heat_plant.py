"""U1 and U5 in plants: invariants over many instances, determinism, and the grammar end to end.

The first half builds columns and trains in one harness unit (`patterns_columns_heat.py`) and
checks S4, S6, S7, S8, S9, S10, S22 and the round trip over all of them. The second half runs the
flowsheet grammar, which now draws U1 in Separation and U5 in Conditioning, through DEXPI and the
schema graph, and hands the plant to the v2 splitter (S20).
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
from instrument_harness import solenoids
from instrument_invariants import check_s4, check_s7, check_s8, check_s9, check_s22
from pattern_checks import assert_line_numbers_unique_and_valid, reaches_a_safety_device
from pattern_harness import PatternHarness
from patterns_columns_heat import build_column_heat_plant
from plant_v2 import generated, graph_of
from trim_harness import assert_round_trip

from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, PortDirection
from plantgraph.benchmark.v2.split_by_sheet_group import by_sheet_group
from plantgraph.graph import validation

Built = tuple[PatternHarness, list[PatternInstance]]


@pytest.fixture(scope="module")
def plant() -> Built:
    h = PatternHarness(seed=5)
    return h, build_column_heat_plant(h)


def test_the_whole_plant_survives_the_dexpi_round_trip(plant: Built) -> None:
    h, instances = plant
    assert len(instances) == 14
    assert assert_round_trip(h).number_of_nodes() > 3000


def test_both_patterns_and_their_system_codes_are_in_the_plant(plant: Built) -> None:
    _, instances = plant
    assert {(i.pattern, i.system_code) for i in instances} == {("U1", "DST"), ("U5", "HXT")}


def test_every_vacuum_variant_and_both_layouts_are_in_the_plant(plant: Built) -> None:
    _, instances = plant
    labels = [i.variant for i in instances if i.pattern == "U1"]
    for expected in ("vacuum=none", "vacuum=air_ejector", "vacuum=liquid_ring"):
        assert any(expected in label for label in labels), expected
    assert any("layout=combined" in label for label in labels)
    assert any("layout=two_sheets" in label for label in labels)


def test_s4_s7_s8_s9_hold_over_the_whole_plant(plant: Built) -> None:
    h, _ = plant
    graph = h.oracle.graph
    assert check_s4(graph) >= 50
    assert check_s7(graph, solenoids(h)) >= 1  # only the drain pots' tube-leak trips
    assert check_s8(graph) >= 250
    assert check_s9(graph) == sum("tag" in d for _, d in graph.nodes(data=True))


def test_s22_the_all_on_columns_draw_two_cascades_each(plant: Built) -> None:
    h, _ = plant
    assert check_s22(h.oracle.graph) >= 8


def test_s6_every_column_and_reflux_drum_has_a_safety_valve(plant: Built) -> None:
    h, instances = plant
    columns = [i for i in instances if i.pattern == "U1"]
    assert len(columns) == 8
    for instance in columns:
        for role in ("column", "reflux_drum"):
            (vessel,) = [n for n, r in instance.plan.roles.items() if r == role]
            assert reaches_a_safety_device(h.oracle.graph, vessel), vessel


def test_s10_line_numbers_are_unique_over_the_whole_plant(plant: Built) -> None:
    _, instances = plant
    assert_line_numbers_unique_and_valid(tuple(line for i in instances for line in i.plan.lines))


def test_no_class_outside_the_generated_list_is_planned(plant: Built) -> None:
    _, instances = plant
    classes = {e.node_class for i in instances for e in i.plan.equipment}
    assert classes <= GENERATED_EQUIPMENT_CLASSES
    assert {"AirEjector", "RotaryCompressor", "PlateHeatExchanger", "ElectricHeater"} <= classes


# ---- determinism ---------------------------------------------------------------------------------

_DIGEST_SCRIPT = """
import hashlib, json
from pydexpi.loaders.json_serializer import JsonSerializer
from pattern_harness import PatternHarness
from patterns_columns_heat import build_column_heat_plant
from trim_harness import project
h = PatternHarness(seed=5)
build_column_heat_plant(h)
text = json.dumps(project(h.oracle.graph), default=str).encode()
print(hashlib.sha256(text).hexdigest())
print(hashlib.sha256(JsonSerializer().export_to_bytes(h.dexpi.build())).hexdigest())
"""


def _digests(hash_seed: int) -> list[str]:
    tests_dir = Path(__file__).parent
    env = {
        **os.environ,
        "PYTHONHASHSEED": str(hash_seed),
        "PYTHONPATH": f"{tests_dir.parent}{os.pathsep}{tests_dir}",
    }
    out = subprocess.run(
        [sys.executable, "-c", _DIGEST_SCRIPT], env=env, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def test_same_seed_gives_identical_graph_and_dexpi_bytes_under_hash_seeds_0_and_999() -> None:
    """Invariant S14 for U1 and U5: nothing depends on `PYTHONHASHSEED`."""
    first, second = _digests(0), _digests(999)
    assert len(first) == 2
    assert first == second


def test_the_patterns_leave_the_global_random_stream_alone() -> None:
    random.seed(123)
    expected = random.random()
    random.seed(123)
    build_column_heat_plant(PatternHarness(seed=2))
    assert random.random() == expected


def test_a_different_seed_changes_the_plant() -> None:
    def tags(seed: int) -> str:
        h = PatternHarness(seed=seed)
        build_column_heat_plant(h)
        return "|".join(sorted(str(d.get("tag")) for _, d in h.oracle.graph.nodes(data=True)))

    assert tags(1) == tags(1)
    assert tags(1) != tags(2)


# ---- through the flowsheet grammar ---------------------------------------------------------------

SEED, UNITS = 4, 30  # a plant with five columns (all three vacuum variants) and five trains


def test_the_grammar_draws_columns_in_separation_and_trains_in_conditioning() -> None:
    plan = generated(SEED, UNITS).plan
    slots = {(u.slot.slot.value, u.instance.pattern) for u in plan.units}
    assert ("separation", "U1") in slots and ("conditioning", "U5") in slots
    variants = " ".join(u.instance.variant for u in plan.units if u.instance.pattern == "U1")
    for kind in ("none", "air_ejector", "liquid_ring"):
        assert f"vacuum={kind}" in variants


def test_the_plant_with_columns_and_trains_loses_nothing_and_validates() -> None:
    graph, report = graph_of(SEED, UNITS)
    assert set(report.nodes_dropped_per_class) <= {"ProcessPlant", "PlantSection"}
    assert report.edges_dropped_per_label == {}
    assert validation.validate_plant_graph(graph) == []


def test_the_v2_splitter_accepts_the_plant_s20() -> None:
    graph, _ = graph_of(SEED, UNITS)
    sheets = by_sheet_group(graph, SplitConfig(), random.Random(0))  # raises on a cut S20 edge
    assert len(set(sheets.values())) >= generated(SEED, UNITS).plan.sheet_count


def test_the_bottoms_of_a_column_feed_the_next_unit() -> None:
    """T10's wiring takes the last out-port of a phase: for a column that is the bottoms."""
    units = generated(SEED, UNITS).plan.units
    joined = 0
    for column, following in zip(units, units[1:], strict=False):
        if column.instance.pattern != "U1" or following.instance.pattern == "U1":
            continue
        entry = next(p for p in following.instance.ports if p.direction is PortDirection.IN)
        lines = following.instance.plan.lines
        line = next(item for item in lines if item.line_number == entry.line_number)
        assert line.src_id == column.instance.port("bottoms").node_id
        joined += 1
    assert joined >= 1
