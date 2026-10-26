"""All trims and all instrument templates in one plant: invariants S4, S7, S8, S9, S22, round trip.

The plant is `instrument_everything.build_instrumented_plant`. The invariants are in
`instrument_invariants.py` and read only the graph.
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
from instrument_everything import build_instrumented_plant
from instrument_harness import solenoids
from instrument_invariants import check_s4, check_s7, check_s8, check_s9, check_s22
from trim_everything import ALL_ON
from trim_harness import TrimHarness, assert_round_trip

from plantgraph.benchmark.v2.config import TrimConvention
from plantgraph.benchmark.v2.tags import parse_tag

#: the letters of every instrument template, base 4.4 and pid-vocabulary 5.3 (split range is off)
_TEMPLATE_LETTERS = {
    "LT",
    "LIC",
    "FT",
    "FIC",
    "FE",
    "PIC",
    "TIC",
    "AIC",  # control loops and cascades
    "LSHH",
    "PSLL",
    "BE",
    "BSL",
    "HS",  # trips and hand switches
    "LIAH",
    "LIAL",
    "PDT",
    "PDI",
    "FQI",
    "FFT",
    "FFIC",
    "AT",
    "AI",  # monitoring, ratio, analyser
    "ST",
    "SI",
    "VT",
    "VAH",
    "TIAH",
    "IT",
    "II",
    "YI",
    "UC",  # machines and reactor
    "LSH",
    "LAH",
    "LSL",
    "LAL",
    "CT",
    "CSHH",
    "CI",  # point level, drain pot
    "ZSO",
    "ZSC",
    "PI",
    "TI",  # position switches and local gauges (built by the trims)
}


@pytest.fixture(scope="module")
def plant() -> TrimHarness:
    h = TrimHarness(seed=5, config=TrimConvention(**ALL_ON))  # type: ignore[arg-type]
    build_instrumented_plant(h)
    return h


def test_the_whole_plant_survives_the_dexpi_round_trip(plant: TrimHarness) -> None:
    graph = assert_round_trip(plant)
    assert graph.number_of_nodes() > 500


def test_every_template_appears_in_the_plant(plant: TrimHarness) -> None:
    present = {
        parse_tag(d["tag"]).letters  # type: ignore[union-attr]
        for _, d in plant.oracle.graph.nodes(data=True)
        if d.get("tag") and parse_tag(d["tag"]) is not None
    }
    assert _TEMPLATE_LETTERS <= present, sorted(_TEMPLATE_LETTERS - present)


def _tags_with_letters(plant: TrimHarness, wanted: set[str]) -> list[str]:
    return sorted(
        d["tag"]
        for _, d in plant.oracle.graph.nodes(data=True)
        if d.get("tag") and (parsed := parse_tag(d["tag"])) and parsed.letters in wanted
    )


def test_s4_every_actuator_drives_a_valve_with_the_loops_number(plant: TrimHarness) -> None:
    graph = plant.oracle.graph
    actuators = [n for n, d in graph.nodes(data=True) if d["node_class"] == "ActuatingFunction"]
    assert check_s4(graph) == len(actuators) > 0


def test_s7_every_xv_has_a_driver_and_a_solenoid(plant: TrimHarness) -> None:
    on_off = _tags_with_letters(plant, {"XV", "YV"})
    assert check_s7(plant.oracle.graph, solenoids(plant)) == len(on_off) > 0


def test_s8_every_loop_has_one_sensor_one_bubble_one_actuator_and_one_number(
    plant: TrimHarness,
) -> None:
    graph = plant.oracle.graph
    bubbles = [
        n
        for n, d in graph.nodes(data=True)
        if d["node_class"] in ("ProcessInstrumentationFunction", "ProcessControlFunction")
    ]
    assert check_s8(graph) == len(bubbles) > 0


def test_s9_every_tag_is_unique_parses_and_fits_its_class(plant: TrimHarness) -> None:
    graph = plant.oracle.graph
    assert check_s9(graph) == sum("tag" in d for _, d in graph.nodes(data=True))


def test_s22_every_cascade_slave_has_one_sensor_and_one_master(plant: TrimHarness) -> None:
    """The plant has cascades with a level, a temperature and an analyser master."""
    graph = plant.oracle.graph
    assert check_s22(graph) >= 3
    master_letters = {
        parse_tag(graph.nodes[n]["tag"]).letters  # type: ignore[union-attr]
        for n, d in graph.nodes(data=True)
        if d["node_class"] == "ProcessControlFunction"
        and any(
            graph.nodes[t]["node_class"] == "ProcessControlFunction" for t in graph.successors(n)
        )
    }
    assert master_letters == {"LIC", "TIC", "AIC"}


# ---- determinism ---------------------------------------------------------------------------------

_DIGEST_SCRIPT = """
import hashlib, json
from pydexpi.loaders.json_serializer import JsonSerializer
from plantgraph.benchmark.v2.config import TrimConvention
from instrument_everything import build_instrumented_plant
from trim_everything import ALL_ON
from trim_harness import TrimHarness, project
h = TrimHarness(seed=5, config=TrimConvention(**ALL_ON))
build_instrumented_plant(h)
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
    """Invariant S14 for instruments: nothing depends on `PYTHONHASHSEED`."""
    assert _digests(0) == _digests(999)


def test_instrument_templates_leave_the_global_random_stream_alone() -> None:
    random.seed(123)
    expected = random.random()
    random.seed(123)
    build_instrumented_plant(TrimHarness(seed=2, config=TrimConvention(**ALL_ON)))  # type: ignore[arg-type]
    assert random.random() == expected


def test_a_different_seed_changes_the_plant() -> None:
    def digest(seed: int) -> str:
        h = TrimHarness(seed=seed, config=TrimConvention(**ALL_ON))  # type: ignore[arg-type]
        build_instrumented_plant(h)
        return "|".join(sorted(str(d.get("tag")) for _, d in h.oracle.graph.nodes(data=True)))

    assert digest(1) == digest(1)
    assert digest(1) != digest(2)
