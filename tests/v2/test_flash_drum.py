"""U6, the flash drum (design 7.2, pid-vocabulary 13.3): its loops, trip, trims and variants.

Each test builds the drum on the graph oracle and the DEXPI builder and checks the round trip and
the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources
from instrument_invariants import check_s22
from pattern_checks import (
    assert_line_numbers_unique_and_valid,
    assert_pattern_invariants,
    flow_graph,
    located_on,
    nodes_with_letters,
    reaches_a_safety_device,
)
from pattern_harness import PatternHarness, config_with
from trim_harness import ids_with_role, send_to_path

from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.benchmark.v2.patterns.separation import build_flash_drum
from plantgraph.graph.schema import Relation

_TWO_PUMPS = {"p_single_pump": 0.0, "p_triple_pump_set": 0.0}


def _drum(
    cards: dict[str, tuple[str, ...]] | None = None,
    instruments: dict[str, object] | None = None,
    density: dict[str, object] | None = None,
    seed: int = 0,
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    config = config_with(instruments=instruments or {}, density=density or {}, patterns=_TWO_PUMPS)
    h = PatternHarness(seed, config, deck_cards=cards)
    instance = build_flash_drum(h.pctx)
    instance.plan.write(h.builder)
    return h, instance, assert_pattern_invariants(h)


def _drum_id(instance: PatternInstance) -> str:
    (drum,) = ids_with_role(instance.plan, "flash_drum")
    return drum


def _letters(graph: nx.DiGraph[str], node_id: str) -> str:
    return graph.nodes[node_id]["tag"].partition("-")[0]


# ---- variants and ports --------------------------------------------------------------------------


@pytest.mark.parametrize("vessel", ["PressureVessel", "GravitationalSeparator"])
def test_vessel_variant_sets_the_drum_class(vessel: str) -> None:
    _, instance, graph = _drum({"U6.vessel": (vessel,)})
    assert graph.nodes[_drum_id(instance)]["node_class"] == vessel
    assert f"vessel={vessel}" in instance.variant


def test_the_ports_are_a_feed_in_a_vapour_out_and_a_liquid_out() -> None:
    _, instance, graph = _drum()
    kinds = {p.name: (p.direction, p.phase) for p in instance.ports}
    assert kinds == {
        "feed": (PortDirection.IN, Phase.LIQUID),
        "vapour": (PortDirection.OUT, Phase.GAS),
        "liquid": (PortDirection.OUT, Phase.LIQUID),
    }
    lines = {line.line_number: line for line in instance.plan.lines}
    assert lines[instance.port("feed").line_number].src_id is None
    assert lines[instance.port("vapour").line_number].dst_id is None
    assert lines[instance.port("liquid").line_number].dst_id is None
    assert instance.port("vapour").node_id in graph and instance.port("liquid").node_id in graph


def test_the_drum_is_group_one_and_its_pumps_join_it_or_get_a_pinned_sheet() -> None:
    _, joined, _ = _drum({"pump_set.group": ("with_suction_vessel",)})
    _, own, _ = _drum({"pump_set.group": ("own_sheet",)})
    assert set(joined.drawing_group_of.values()) == {"G1"} and not joined.pinned_groups
    assert set(own.drawing_group_of.values()) == {"G1", "G2"}
    assert own.pinned_groups == frozenset({"G2"})


# ---- rules ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("vessel", ["PressureVessel", "GravitationalSeparator"])
def test_s6_the_drum_has_a_safety_valve_reachable_without_passing_equipment(vessel: str) -> None:
    _, instance, graph = _drum({"U6.vessel": (vessel,)})
    assert reaches_a_safety_device(graph, _drum_id(instance))


def test_the_pressure_loop_moves_a_valve_on_the_vapour_outlet() -> None:
    """`PT` on the drum -> `PIC` -> `PV` between the top tee and the open end."""
    _, instance, graph = _drum()
    drum = _drum_id(instance)
    valves = nodes_with_letters(graph, "PV")
    assert len(valves) == 1
    assert nx.has_path(flow_graph(graph), drum, valves[0])
    assert nx.has_path(flow_graph(graph), valves[0], instance.port("vapour").node_id)
    (actuator,) = sources(graph, valves[0], Relation.CONTROL)
    (controller,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
    assert _letters(graph, controller) == "PIC"
    (sensor,) = sources(graph, controller, Relation.SEND_SIGNAL_TO)
    assert sensor in located_on(graph, drum) and _letters(graph, sensor) == "PT"


def test_the_level_loop_moves_a_valve_on_the_pump_discharge() -> None:
    _, instance, graph = _drum(instruments={"p_cascade": 0.0})
    valves = nodes_with_letters(graph, "LV")
    assert len(valves) == 1 and graph.nodes[valves[0]]["node_class"].startswith("Angle")
    pump = instance.plan.equipment[1].node_id
    assert nx.has_path(flow_graph(graph), pump, valves[0])
    assert nx.has_path(flow_graph(graph), valves[0], instance.port("liquid").node_id)
    assert check_s22(graph) == 0  # no cascade


def test_s22_with_a_cascade_the_level_controller_sets_a_flow_controller() -> None:
    _, instance, graph = _drum(instruments={"p_cascade": 1.0})
    assert check_s22(graph) == 1
    assert not nodes_with_letters(graph, "LV")
    (valve,) = nodes_with_letters(graph, "FV")
    assert graph.nodes[valve]["node_class"].startswith("Angle")
    assert nx.has_path(flow_graph(graph), valve, instance.port("liquid").node_id)
    assert nodes_with_letters(graph, "FE")
    (master,) = nodes_with_letters(graph, "LIC")
    (sensor,) = sources(graph, master, Relation.SEND_SIGNAL_TO)
    assert sensor in located_on(graph, _drum_id(instance))


def test_the_high_level_trip_shuts_a_valve_on_the_feed() -> None:
    """`LT` on the drum -> `LSHH` -> `XV`; the valve sits between the feed port and the drum."""
    _, instance, graph = _drum()
    drum = _drum_id(instance)
    path = send_to_path(graph, instance.port("feed").node_id, drum)
    (valve,) = [n for n in path if (graph.nodes[n].get("tag") or "")[:2] in ("XV", "YV")]
    (actuator,) = sources(graph, valve, Relation.CONTROL)
    (switch,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
    assert _letters(graph, switch) == "LSHH"
    (sensor,) = sources(graph, switch, Relation.SEND_SIGNAL_TO)
    assert sensor in located_on(graph, drum)


def test_the_drum_has_gauges_on_top_and_inlet_a_level_glass_and_monitoring_points() -> None:
    _, instance, graph = _drum()
    drum = _drum_id(instance)
    assert ids_with_role(instance.plan, "vessel_top_pi") and ids_with_role(
        instance.plan, "vessel_top_ti"
    )
    assert ids_with_role(instance.plan, "inlet_ti")
    assert any(_letters(graph, s) == "LG" for s in located_on(graph, drum))
    points = [  # one sensor per point: a gauge, or the transmitter of a transmitter and indicator
        n
        for n, role in instance.plan.roles.items()
        if role in {"monitor_gauge", "monitor"}
        and graph.nodes[n]["node_class"] == "ProcessSignalGeneratingFunction"
        and _letters(graph, n) in {"TI", "PI", "TT", "PT"}
    ]
    assert 5 <= len(points) <= 7  # monitor_points_per_major_item is 5 to 7


@pytest.mark.parametrize(("chance", "expected"), [(1.0, True), (0.0, False)])
def test_optional_alarms_follow_their_chances(chance: float, expected: bool) -> None:
    density = {"p_optional_instrument": chance, "p_point_level_switch": chance}
    _, _, graph = _drum(density=density)
    assert bool(nodes_with_letters(graph, "LSLL")) is expected
    assert bool(nodes_with_letters(graph, "LSH")) is expected


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = _drum()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


def test_every_drum_variant_appears_within_one_deck_cycle() -> None:
    """The vessel deck has 3 cards (2 : 1): three drums deal both classes."""
    h = PatternHarness(config=config_with())
    labels = [build_flash_drum(h.pctx).variant for _ in range(3)]
    assert {label.split("|")[0] for label in labels} == {
        "vessel=PressureVessel",
        "vessel=GravitationalSeparator",
    }
