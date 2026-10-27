"""U2, U3 and U8 in plants: invariants over many instances, determinism and the grammar end to end.

The first half builds compressor stages, reactor systems and blending units in one harness unit
(`patterns_machines.py`) and checks S4, S6, S7, S8, S9, S10, S19, S20, S22, the round trip and deck
coverage over all of them. The second half runs the flowsheet grammar, which now draws every
pattern, through DEXPI and the schema graph, and hands the plant to the v2 splitter (S20).
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
from machine_checks import check_s19, check_s20
from pattern_checks import assert_line_numbers_unique_and_valid, reaches_a_safety_device
from pattern_harness import PatternHarness
from patterns_machines import build_machine_plant
from plant_v2 import generated, graph_of
from trim_harness import assert_round_trip

from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, PortDirection
from plantgraph.benchmark.v2.patterns.registry import available_patterns
from plantgraph.benchmark.v2.split_by_sheet_group import by_sheet_group
from plantgraph.benchmark.v2.trims_vessel import PSV_VESSEL_CLASSES
from plantgraph.graph import validation

Built = tuple[PatternHarness, list[PatternInstance]]


def labels(instances: list[PatternInstance], pattern: str) -> list[str]:
    """The variant labels of the instances of one pattern."""
    return [i.variant for i in instances if i.pattern == pattern]


@pytest.fixture(scope="module", params=[False, True], ids=["default", "all_on"])
def plant(request: pytest.FixtureRequest) -> Built:
    h = PatternHarness(seed=5)
    return h, build_machine_plant(h, optional_parts=request.param)


@pytest.fixture(scope="module")
def both() -> list[Built]:
    """The default and the all-on plant, for tests that need a variant to appear in either."""
    builds = []
    for optional in (False, True):
        h = PatternHarness(seed=5)
        builds.append((h, build_machine_plant(h, optional_parts=optional)))
    return builds


def test_the_whole_plant_survives_the_dexpi_round_trip(plant: Built) -> None:
    h, instances = plant
    assert len(instances) == 11
    assert assert_round_trip(h).number_of_nodes() > 1500


def test_the_three_patterns_and_their_system_codes_are_in_the_plant(plant: Built) -> None:
    _, instances = plant
    assert {(i.pattern, i.system_code) for i in instances} == {
        ("U2", "CMP"),
        ("U3", "RXN"),
        ("U8", "BLD"),
    }


def test_s4_s7_s8_s9_hold_over_the_whole_plant(plant: Built) -> None:
    h, _ = plant
    graph = h.oracle.graph
    assert check_s4(graph) >= 30
    assert check_s7(graph, solenoids(h)) >= 15
    assert check_s8(graph) >= 150
    assert check_s9(graph) == sum("tag" in d for _, d in graph.nodes(data=True))


def test_s22_the_all_on_plant_draws_cascades(both: list[Built]) -> None:
    assert check_s22(both[0][0].oracle.graph) >= 0
    assert check_s22(both[1][0].oracle.graph) >= 3


def test_s19_every_machine_control_comes_from_an_aef_with_a_signal_source(plant: Built) -> None:
    h, _ = plant
    assert check_s19(h.oracle.graph) >= 25  # hand switches, speed loops, ratio loops, agitators


def test_s20_no_agitator_or_machine_control_edge_crosses_a_sheet(plant: Built) -> None:
    _, instances = plant
    assert sum(check_s20(instance) for instance in instances) >= 25


def test_s6_every_vessel_has_a_safety_valve_and_none_is_a_drain_pot(plant: Built) -> None:
    h, instances = plant
    graph = h.oracle.graph
    vessels = [n for n, d in graph.nodes(data=True) if d["node_class"] in PSV_VESSEL_CLASSES]
    assert len(vessels) >= 12
    for vessel in vessels:
        assert reaches_a_safety_device(graph, vessel), vessel
    assert all("condensate_drain_pot" not in i.plan.roles.values() for i in instances)


def test_s10_line_numbers_are_unique_and_every_reactor_has_one_spec_break(plant: Built) -> None:
    _, instances = plant
    lines = tuple(line for i in instances for line in i.plan.lines)
    assert_line_numbers_unique_and_valid(lines)
    assert sum(line.line_number_after_break is not None for line in lines) == 3  # one per reactor


def test_no_class_outside_the_generated_list_is_planned(plant: Built) -> None:
    _, instances = plant
    classes = {e.node_class for i in instances for e in i.plan.equipment}
    assert classes <= GENERATED_EQUIPMENT_CLASSES
    assert not {"CentrifugalBlower", "AxialFan", "Chimney"} & classes


# ---- deck coverage ------------------------------------------------------------------------------


def test_every_variant_of_every_deck_appears_in_the_two_plants(both: list[Built]) -> None:
    instances = [i for _, built in both for i in built]
    u2, u3, u8 = (" ".join(labels(instances, p)) for p in ("U2", "U3", "U8"))
    expected = {
        "U2": [
            *(f"compressor={c}Compressor" for c in ("Centrifugal", "Reciprocating", "Rotary")),
            "aftercooler=TubularHeatExchanger",
            "aftercooler=AirCoolingSystem",
            "suction_filter=True",
            "suction_filter=False",
            "discharge_ko_drum=True",
            "discharge_ko_drum=False",
            "drive=vfd",
            "drive=fixed_speed",
        ],
        "U3": ["reactor=plain", "reactor=agitated"],
        "U8": [
            *(f"mixer={m}" for m in ("StaticMixer", "RotaryMixer", "EjectorPump")),
            "agitated_vessel=True",
            "agitated_vessel=False",
            "injection=plain",
            "injection=InLineMixer",
            "dosing=vfd",
            "dosing=ratio_valve",
        ],
    }
    for text, wanted in zip((u2, u3, u8), expected.values(), strict=True):
        for variant in wanted:
            assert variant in text, variant


# ---- determinism ---------------------------------------------------------------------------------

_DIGEST_SCRIPT = """
import hashlib, json
from pydexpi.loaders.json_serializer import JsonSerializer
from pattern_harness import PatternHarness
from patterns_machines import build_machine_plant
from trim_harness import project
for optional_parts in (False, True):
    h = PatternHarness(seed=5)
    build_machine_plant(h, optional_parts)
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
    """Invariant S14 for U2, U3 and U8: nothing depends on `PYTHONHASHSEED`."""
    first, second = _digests(0), _digests(999)
    assert len(first) == 4
    assert first == second


def test_the_patterns_leave_the_global_random_stream_alone() -> None:
    random.seed(123)
    expected = random.random()
    random.seed(123)
    build_machine_plant(PatternHarness(seed=2))
    build_machine_plant(PatternHarness(seed=2), optional_parts=True)
    assert random.random() == expected


def test_a_different_seed_changes_the_plant() -> None:
    def tags(seed: int) -> str:
        h = PatternHarness(seed=seed)
        build_machine_plant(h)
        return "|".join(sorted(str(d.get("tag")) for _, d in h.oracle.graph.nodes(data=True)))

    assert tags(1) == tags(1)
    assert tags(1) != tags(2)


# ---- through the flowsheet grammar ---------------------------------------------------------------

SEED, UNITS = 1, 60  # a plant with every pattern U1 to U8


def test_every_pattern_is_registered_and_the_grammar_draws_them_all() -> None:
    assert available_patterns() == frozenset({f"U{n}" for n in (1, 2, 3, 4, 5, 6, 7, 8)})
    drawn = {u.instance.pattern for u in generated(SEED, UNITS).plan.units}
    assert drawn == available_patterns()


def test_the_grammar_places_u2_after_u3_and_u8_in_conditioning() -> None:
    units = generated(SEED, UNITS).plan.units
    patterns = [u.instance.pattern for u in units]
    assert all(patterns[i - 1] == "U3" for i, p in enumerate(patterns) if p == "U2")
    assert {u.slot.slot.value for u in units if u.instance.pattern == "U8"} == {"conditioning"}


def test_the_compressor_takes_the_reactor_gas_and_the_next_unit_the_reactor_liquid() -> None:
    units = generated(5, UNITS).plan.units
    found = 0
    for reactor, stage, after in zip(units, units[1:], units[2:], strict=False):
        if (reactor.instance.pattern, stage.instance.pattern) != ("U3", "U2"):
            continue
        assert _source_of(stage.instance, "gas") == reactor.instance.port("gas").node_id
        assert (
            _source_of(after.instance, _entry(after.instance))
            == reactor.instance.port("liquid").node_id
        )
        found += 1
    assert found >= 1


def _entry(instance: PatternInstance) -> str:
    return next(p.name for p in instance.ports if p.direction is PortDirection.IN)


def _source_of(instance: PatternInstance, in_port_name: str) -> str | None:
    line_number = instance.port(in_port_name).line_number
    return next(line.src_id for line in instance.plan.lines if line.line_number == line_number)


def test_the_full_plant_loses_nothing_and_validates() -> None:
    graph, report = graph_of(SEED, UNITS)
    assert set(report.nodes_dropped_per_class) <= {"ProcessPlant", "PlantSection"}
    assert report.edges_dropped_per_label == {}
    assert validation.validate_plant_graph(graph) == []


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_v2_splitter_accepts_the_plant_s20(seed: int) -> None:
    graph, _ = graph_of(seed, UNITS)
    sheets = by_sheet_group(graph, SplitConfig(), random.Random(0))  # raises on a cut S20 edge
    assert len(set(sheets.values())) >= generated(seed, UNITS).plan.sheet_count
