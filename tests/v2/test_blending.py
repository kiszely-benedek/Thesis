"""U8, blending (design 7.2, pid-vocabulary 5.1, 5.2, 13.3): ports, ratio loop, mixers, variants.

Each test builds one blending unit on the graph oracle and the DEXPI builder and checks the round
trip and the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names.
S19 and S20 cover the drives (hand switches, ratio-set pump speed, agitator).
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources, targets
from machine_checks import check_s19, check_s20
from pattern_checks import (
    assert_line_numbers_unique_and_valid,
    assert_pattern_invariants,
    flow_graph,
    nodes_of_class,
    nodes_with_letters,
    reaches_a_safety_device,
)
from pattern_harness import PatternHarness, config_with
from test_column import letters
from trim_harness import ids_with_role

from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.patterns.blending import build_blending
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.graph.schema import Relation

_PLAIN = {"U8.agitated_vessel": ("absent",), "U8.mixer": ("StaticMixer",)}
_TWO_PUMPS = {"p_single_pump": 0.0, "p_triple_pump_set": 0.0}
_STAY = {"pump_set.group": ("with_suction_vessel",)}


def blend(
    cards: dict[str, tuple[str, ...]] | None = None, seed: int = 0, **sections: dict[str, object]
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    """Build one unit: `sections` override knob groups (`density={"p_vfd": 1.0}`)."""
    sections["patterns"] = {**_TWO_PUMPS, **sections.get("patterns", {})}
    deck_cards = {**_PLAIN, **_STAY, **(cards or {})}
    h = PatternHarness(seed, config_with(**sections), deck_cards=deck_cards)
    instance = build_blending(h.pctx)
    instance.plan.write(h.builder)
    return h, instance, assert_pattern_invariants(h)


def one(instance: PatternInstance, role: str) -> str:
    """The id of the single node planned for `role`."""
    (node_id,) = ids_with_role(instance.plan, role)
    return node_id


def class_of(graph: nx.DiGraph[str], node_id: str) -> str:
    """The node class of `node_id`."""
    return str(graph.nodes[node_id]["node_class"])


# ---- ports and flow -----------------------------------------------------------------------------


def test_the_ports_are_main_and_additive_in_and_blend_out() -> None:
    _, instance, graph = blend()
    assert instance.port_names == ["main", "additive", "blend"]
    directions = {p.name: (p.direction, p.phase) for p in instance.ports}
    assert directions == {
        "main": (PortDirection.IN, Phase.LIQUID),
        "additive": (PortDirection.IN, Phase.LIQUID),
        "blend": (PortDirection.OUT, Phase.LIQUID),
    }
    lines = {line.line_number: line for line in instance.plan.lines}
    assert lines[instance.port("main").line_number].src_id is None
    assert lines[instance.port("additive").line_number].src_id is None
    assert lines[instance.port("blend").line_number].dst_id is None
    assert all(instance.port(p).node_id in graph for p in instance.port_names)


def test_main_and_additive_meet_in_the_mixer_and_the_blend_leaves_it() -> None:
    _, instance, graph = blend()
    mixer, tank = one(instance, "mixer"), one(instance, "additive_tank")
    pump = ids_with_role(instance.plan, "dosing_pump")[0]
    flow = flow_graph(graph)
    assert nx.has_path(flow, instance.port("main").node_id, mixer)
    assert nx.has_path(flow, instance.port("additive").node_id, tank)
    assert nx.has_path(flow, tank, pump) and nx.has_path(flow, pump, mixer)
    assert nx.has_path(flow, mixer, instance.port("blend").node_id)


def test_the_additive_lines_are_a_smaller_pipe_than_the_main_line() -> None:
    _, instance, _ = blend()
    main = parse_line_number(instance.port("main").line_number)
    additive = parse_line_number(instance.port("additive").line_number)
    assert main is not None and additive is not None and additive.size < main.size


# ---- ratio control ------------------------------------------------------------------------------


def test_the_ratio_controller_reads_both_flows_and_moves_the_additive_valve() -> None:
    """`FFT` on the main meter, `FT` on the additive meter -> `FFIC` -> `FV` after the pumps."""
    _, instance, graph = blend(density={"p_vfd": 0.0})
    main_meter, additive_meter = (
        one(instance, "main_flow_meter"),
        one(instance, "additive_flow_meter"),
    )
    assert class_of(graph, main_meter) == "ElectromagneticFlowMeter"
    assert class_of(graph, additive_meter) == "MassFlowMeasuringElement"
    (controller,) = nodes_with_letters(graph, "FFIC")
    located = {
        letters(graph, s): sources(graph, s, Relation.MEASURED_BY)
        for s in sources(graph, controller, Relation.SEND_SIGNAL_TO)
    }
    assert located == {"FFT": [main_meter], "FT": [additive_meter]}
    (valve,) = nodes_with_letters(graph, "FV")
    (actuator,) = targets(graph, controller, Relation.SEND_SIGNAL_TO)
    assert targets(graph, actuator, Relation.CONTROL) == [valve]
    pump, mixer = ids_with_role(instance.plan, "dosing_pump")[0], one(instance, "mixer")
    flow = flow_graph(graph)
    assert nx.has_path(flow, pump, valve) and nx.has_path(flow, valve, mixer)
    assert check_s19(graph) == 2  # the two pumps' hand switches only


def test_a_variable_speed_drive_replaces_the_valve_with_one_ratio_loop_per_pump() -> None:
    _, instance, graph = blend(density={"p_vfd": 1.0})
    pumps = ids_with_role(instance.plan, "dosing_pump")
    assert not nodes_with_letters(graph, "FV")
    controllers = nodes_with_letters(graph, "FFIC")
    assert len(controllers) == len(pumps) == 2  # one controller drives one machine (S8)
    for pump in pumps:
        drivers = []
        for actuator in sources(graph, pump, Relation.CONTROL):
            (bubble,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
            drivers.append(letters(graph, bubble))
        assert sorted(drivers) == ["FFIC", "HS"]
    assert check_s19(graph) == 4
    assert check_s20(instance) == 4
    assert "dosing=vfd" in instance.variant


# ---- mixers -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mixer_class", "motor"),
    [("StaticMixer", False), ("RotaryMixer", True), ("EjectorPump", False)],
)
def test_the_mixer_class_follows_the_deck_and_only_the_rotary_mixer_has_a_motor(
    mixer_class: str, motor: bool
) -> None:
    _, instance, graph = blend({"U8.mixer": (mixer_class,)})
    mixer = one(instance, "mixer")
    assert class_of(graph, mixer) == mixer_class
    assert any(e.node_id == mixer and e.has_motor for e in instance.plan.equipment) is motor
    assert bool(sources(graph, mixer, Relation.CONTROL)) is motor  # started from a hand switch
    assert check_s19(graph) == 2 + motor
    assert f"mixer={mixer_class}" in instance.variant


@pytest.mark.parametrize("injection", ["plain", "InLineMixer"])
def test_the_additive_injection_variant_puts_an_in_line_mixer_before_the_mixer(
    injection: str,
) -> None:
    _, instance, graph = blend({"U8.additive_injection": (injection,)})
    inline = nodes_of_class(graph, "InLineMixer")
    assert bool(inline) is (injection == "InLineMixer")
    if inline:
        flow = flow_graph(graph)
        pump = ids_with_role(instance.plan, "dosing_pump")[0]
        assert nx.has_path(flow, pump, inline[0]) and nx.has_path(
            flow, inline[0], one(instance, "mixer")
        )


def test_the_dosing_pumps_are_reciprocating_pumps_with_a_relief_path_and_an_isolation_valve() -> (
    None
):
    _, instance, graph = blend()
    pumps = ids_with_role(instance.plan, "dosing_pump")
    assert {class_of(graph, p) for p in pumps} == {"ReciprocatingPump"}
    assert len(nodes_of_class(graph, "SpringLoadedAngleGlobeSafetyValve")) >= len(pumps)  # L5
    isolation = [n for n, role in instance.plan.roles.items() if role == "dosing_isolation_valve"]
    assert len(isolation) == 1 and class_of(graph, isolation[0]) in {
        "GateValve",
        "StraightwayValve",
    }


def test_an_analyser_on_the_blend_is_an_indicator_only() -> None:
    for chance, expected in ((1.0, True), (0.0, False)):
        _, _, graph = blend(density={"p_optional_instrument": chance})
        assert bool(nodes_with_letters(graph, "AT")) is expected
        assert not nodes_with_letters(graph, "AIC")  # a cascade master would break S22


# ---- the day tank and the agitated vessel ---------------------------------------------------


def test_the_additive_comes_from_a_day_tank_with_a_vent_a_drain_and_a_level_transmitter() -> None:
    _, instance, graph = blend()
    tank = one(instance, "additive_tank")
    assert class_of(graph, tank) == "Tank"
    assert nodes_of_class(graph, "VentilationDevice")  # additives are not flammable: a plain vent
    sensors = {letters(graph, s) for s in targets(graph, tank, Relation.MEASURED_BY)}
    assert "LT" in sensors


def test_the_agitated_vessel_holds_the_blend_before_a_level_controlled_outlet() -> None:
    _, instance, graph = blend({"U8.agitated_vessel": ("present",)})
    vessel, mixer = one(instance, "blend_vessel"), one(instance, "mixer")
    flow = flow_graph(graph)
    assert nx.has_path(flow, mixer, vessel)
    assert nx.has_path(flow, vessel, instance.port("blend").node_id)
    (valve,) = nodes_with_letters(graph, "LV")
    assert nx.has_path(flow, vessel, valve) and nx.has_path(
        flow, valve, instance.port("blend").node_id
    )
    assert reaches_a_safety_device(graph, vessel)  # S6


def test_the_vessel_agitator_is_driven_and_stays_on_the_vessel_sheet() -> None:
    _, instance, graph = blend({"U8.agitated_vessel": ("present",), "U8.mixer": ("StaticMixer",)})
    vessel, agitator = one(instance, "blend_vessel"), one(instance, "agitator")
    assert targets(graph, vessel, Relation.HAS_AGITATOR) == [agitator]
    assert class_of(graph, agitator) == "Agitator"
    assert check_s19(graph) == 3  # two pumps and the agitator
    assert check_s20(instance) == 4
    group = instance.drawing_group_of
    assert group[vessel] == group[agitator] == "G2"


def test_without_a_vessel_there_is_no_agitator_and_one_drawing_group() -> None:
    _, instance, graph = blend({"U8.agitated_vessel": ("absent",)})
    assert not nodes_of_class(graph, "Agitator", "PressureVessel")
    assert set(instance.drawing_group_of.values()) == {"G1"}


def test_a_pump_set_on_its_own_sheet_is_pinned_after_the_vessel_group() -> None:
    _, instance, _ = blend({"pump_set.group": ("own_sheet",), "U8.agitated_vessel": ("present",)})
    pumps = ids_with_role(instance.plan, "dosing_pump")
    assert {instance.drawing_group_of[p] for p in pumps} == {"G3"}
    assert instance.pinned_groups == {"G3"}


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = blend()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


@pytest.mark.parametrize("seed", range(8))
def test_only_generated_equipment_classes_appear(seed: int) -> None:
    _, instance, _ = blend(seed=seed)
    assert {e.node_class for e in instance.plan.equipment} <= GENERATED_EQUIPMENT_CLASSES
