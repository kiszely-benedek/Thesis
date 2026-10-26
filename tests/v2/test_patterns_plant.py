"""All T9 patterns in one plant: invariants S4, S7, S8, S9, S22, S6, round trip and determinism.

The plant is `patterns_everything.build_pattern_plant`. The invariants are in
`instrument_invariants.py` and `pattern_checks.py` and read only the graph.
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
from patterns_everything import build_pattern_plant
from trim_harness import assert_round_trip

from plantgraph.benchmark.v2.patterns.ports import PatternInstance


@pytest.fixture(scope="module")
def plant() -> tuple[PatternHarness, list[PatternInstance]]:
    h = PatternHarness(seed=5)
    return h, build_pattern_plant(h)


def test_the_whole_plant_survives_the_dexpi_round_trip(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    h, instances = plant
    assert len(instances) == 18
    assert assert_round_trip(h).number_of_nodes() > 1500


def test_every_pattern_and_system_code_is_in_the_plant(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    _, instances = plant
    assert {(i.pattern, i.system_code) for i in instances} == {
        ("U4", "TKF"),
        ("U6", "FLS"),
        ("U7", "FIL"),
    }


def test_s4_every_actuator_drives_a_valve_with_the_loops_number(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    h, _ = plant
    assert check_s4(h.oracle.graph) > 50


def test_s7_every_xv_has_one_driver_and_a_solenoid(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    h, _ = plant
    assert check_s7(h.oracle.graph, solenoids(h)) > 20


def test_s8_every_loop_has_one_sensor_one_bubble_one_actuator_and_one_number(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    h, _ = plant
    assert check_s8(h.oracle.graph) > 200


def test_s9_every_tag_is_unique_parses_and_fits_its_class(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    h, _ = plant
    graph = h.oracle.graph
    assert check_s9(graph) == sum("tag" in d for _, d in graph.nodes(data=True))


def test_s22_the_all_on_drums_draw_cascades(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    h, _ = plant
    assert (
        check_s22(h.oracle.graph) >= 3
    )  # the three all-on drums, plus any default drum that drew one


def test_s6_every_drum_has_a_safety_valve(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    h, instances = plant
    drums = [i for i in instances if i.pattern == "U6"]
    assert len(drums) == 6
    for drum in drums:
        (vessel,) = [n for n, role in drum.plan.roles.items() if role == "flash_drum"]
        assert reaches_a_safety_device(h.oracle.graph, vessel), vessel


def test_s10_line_numbers_are_unique_over_the_whole_plant(
    plant: tuple[PatternHarness, list[PatternInstance]],
) -> None:
    _, instances = plant
    assert_line_numbers_unique_and_valid(tuple(line for i in instances for line in i.plan.lines))


# ---- determinism ---------------------------------------------------------------------------------

_DIGEST_SCRIPT = """
import hashlib, json
from pydexpi.loaders.json_serializer import JsonSerializer
from pattern_harness import PatternHarness
from patterns_everything import build_pattern_plant
from trim_harness import project
h = PatternHarness(seed=5)
build_pattern_plant(h)
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
    """Invariant S14 for the patterns: nothing depends on `PYTHONHASHSEED`."""
    first, second = _digests(0), _digests(999)
    assert len(first) == 2
    assert first == second


def test_the_patterns_leave_the_global_random_stream_alone() -> None:
    random.seed(123)
    expected = random.random()
    random.seed(123)
    build_pattern_plant(PatternHarness(seed=2))
    assert random.random() == expected


def test_a_different_seed_changes_the_plant() -> None:
    def tags(seed: int) -> str:
        h = PatternHarness(seed=seed)
        build_pattern_plant(h)
        return "|".join(sorted(str(d.get("tag")) for _, d in h.oracle.graph.nodes(data=True)))

    assert tags(1) == tags(1)
    assert tags(1) != tags(2)
