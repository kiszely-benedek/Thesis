"""U2, the compressor stage (design 7.2, pid-vocabulary 5.1, 5.2, 13.3): ports, loops, variants.

Each test builds one stage on the graph oracle and the DEXPI builder and checks the round trip and
the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names, and S19
and S20 for the compressor's drives.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources
from machine_checks import check_s19, check_s20
from pattern_checks import (
    assert_line_numbers_unique_and_valid,
    assert_pattern_invariants,
    flow_graph,
    located_on,
    nodes_of_class,
    nodes_with_letters,
    reaches_a_safety_device,
)
from pattern_harness import PatternHarness, config_with
from test_column import letters, sensor_location
from trim_harness import ids_with_role

from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.patterns.compression import build_compressor_stage
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.graph.schema import Relation

_AEF = "ActuatingElectricalFunction"
_PLAIN = {"U2.suction_filter": ("absent",), "U2.discharge_ko_drum": ("absent",)}


def stage(
    cards: dict[str, tuple[str, ...]] | None = None, seed: int = 0, **sections: dict[str, object]
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    """Build one stage: `sections` override knob groups (`density={"p_vfd": 1.0}`)."""
    h = PatternHarness(seed, config_with(**sections), deck_cards={**_PLAIN, **(cards or {})})
    instance = build_compressor_stage(h.pctx)
    instance.plan.write(h.builder)
    return h, instance, assert_pattern_invariants(h)


def one(instance: PatternInstance, role: str) -> str:
    """The id of the single node planned for `role`."""
    (node_id,) = ids_with_role(instance.plan, role)
    return node_id


def drives_of(graph: nx.DiGraph[str], machine: str) -> list[str]:
    """The letters of the controller or switch behind each AEF that drives `machine`."""
    drivers = []
    for actuator in sources(graph, machine, Relation.CONTROL):
        (bubble,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
        drivers.append(letters(graph, bubble))
    return sorted(drivers)


# ---- ports and flow -----------------------------------------------------------------------------


def test_the_ports_are_a_gas_in_and_a_compressed_gas_out() -> None:
    _, instance, graph = stage()
    assert instance.port_names == ["gas", "compressed"]
    gas, compressed = instance.port("gas"), instance.port("compressed")
    assert (gas.direction, gas.phase) == (PortDirection.IN, Phase.GAS)
    assert (compressed.direction, compressed.phase) == (PortDirection.OUT, Phase.GAS)
    lines = {line.line_number: line for line in instance.plan.lines}
    assert lines[gas.line_number].src_id is None
    assert lines[compressed.line_number].dst_id is None
    assert gas.node_id in graph and compressed.node_id in graph


def test_gas_flows_drum_compressor_aftercooler_and_out() -> None:
    _, instance, graph = stage()
    drum, machine = one(instance, "suction_ko_drum"), one(instance, "compressor")
    cooler = one(instance, "aftercooler")
    flow = flow_graph(graph)
    assert nx.has_path(flow, instance.port("gas").node_id, drum)
    assert nx.has_path(flow, drum, machine) and nx.has_path(flow, machine, cooler)
    assert nx.has_path(flow, cooler, instance.port("compressed").node_id)


def test_the_knocked_out_liquid_leaves_by_a_level_valve_to_a_drain_stub_not_a_port() -> None:
    _, instance, graph = stage({"U2.suction_filter": ("absent",)})
    drum = one(instance, "suction_ko_drum")
    (valve,) = nodes_with_letters(graph, "LV")
    assert sensor_location(graph, valve) == ("LIC", drum)
    assert graph.nodes[valve]["node_class"].startswith("Angle")  # a letdown valve
    ends_open = [
        line
        for line in instance.plan.lines
        if line.dst_id is None and any(item.node_id == valve for item in line.items)
    ]
    assert len(ends_open) == 1  # the level valve's line ends open: a drain stub
    assert all(port.phase is Phase.GAS for port in instance.ports)  # no liquid port to wire


# ---- loops --------------------------------------------------------------------------------------


def test_anti_surge_recycles_from_the_aftercooler_outlet_back_to_the_inlet() -> None:
    """`FT -> FIC -> FV` on a line from the cooler's outlet to the inlet tee: the recycle stream."""
    _, instance, graph = stage()
    (valve,) = nodes_with_letters(graph, "FV")
    cooler, drum = one(instance, "aftercooler"), one(instance, "suction_ko_drum")
    flow = flow_graph(graph)
    assert nx.has_path(flow, cooler, valve) and nx.has_path(flow, valve, drum)
    controller, location = sensor_location(graph, valve)
    assert controller == "FIC" and letters(graph, location) in {"FE"}
    assert nx.has_path(flow, drum, location)  # the meter is on the suction line, after the drum
    assert nx.has_path(flow, location, one(instance, "compressor"))
    recycle = [
        line.line_number
        for line in instance.plan.lines
        if instance.plan.stream_kinds[line.line_number] is StreamKindV2.RECYCLE
    ]
    assert len(recycle) == 1


def test_a_high_level_in_the_drum_shuts_a_valve_on_the_suction() -> None:
    """`LT -> LSHH -> XV` with the valve between the drum and the compressor."""
    _, instance, graph = stage()
    (switch,) = nodes_with_letters(graph, "LSHH")
    (valve,) = nodes_with_letters(graph, "XV")
    (actuator,) = [t for _, t in graph.out_edges(switch)]
    assert valve in [t for _, t in graph.out_edges(actuator)]
    assert nx.has_path(flow_graph(graph), one(instance, "suction_ko_drum"), valve)
    assert nx.has_path(flow_graph(graph), valve, one(instance, "compressor"))


def test_fixed_speed_holds_the_suction_pressure_with_a_valve_on_the_drum_pressure() -> None:
    _, instance, graph = stage(density={"p_vfd": 0.0})
    (valve,) = nodes_with_letters(graph, "PV")
    assert sensor_location(graph, valve) == ("PIC", one(instance, "suction_ko_drum"))
    assert nx.has_path(flow_graph(graph), one(instance, "suction_ko_drum"), valve)
    assert drives_of(graph, one(instance, "compressor")) == ["HS"]


def test_a_variable_speed_drive_replaces_the_valve_and_sets_the_speed_from_the_pressure() -> None:
    _, instance, graph = stage(density={"p_vfd": 1.0})
    machine = one(instance, "compressor")
    assert not nodes_with_letters(graph, "PV")
    assert drives_of(graph, machine) == ["HS", "PIC"]
    (controller,) = nodes_with_letters(graph, "PIC")
    (sensor,) = [
        s for s in sources(graph, controller, Relation.SEND_SIGNAL_TO) if letters(graph, s) == "PT"
    ]
    assert sources(graph, sensor, Relation.MEASURED_BY) == [one(instance, "suction_ko_drum")]


# ---- trims and safety ---------------------------------------------------------------------------


def test_l16_butterfly_block_and_strainer_before_the_machine_check_valve_after_it() -> None:
    _, instance, graph = stage()
    machine = one(instance, "compressor")
    before = nx.ancestors(flow_graph(graph), machine)
    after = nx.descendants(flow_graph(graph), machine)
    assert {"ButterflyValve", "ConicalStrainer"} <= {graph.nodes[n]["node_class"] for n in before}
    assert "CheckValve" in {graph.nodes[n]["node_class"] for n in after}


def test_s6_the_compressor_and_every_drum_have_a_safety_valve_without_passing_equipment() -> None:
    _, instance, graph = stage({"U2.discharge_ko_drum": ("present",)})
    drums = ids_with_role(instance.plan, "suction_ko_drum") + ids_with_role(
        instance.plan, "discharge_ko_drum"
    )
    assert len(drums) == 2
    for vessel in [*drums, one(instance, "compressor")]:
        assert reaches_a_safety_device(graph, vessel), vessel


def test_the_aftercooler_has_cooling_water_unless_it_is_an_air_cooler() -> None:
    for cooler_class in ("TubularHeatExchanger", "AirCoolingSystem"):
        _, instance, graph = stage({"U2.aftercooler": (cooler_class,)})
        cooler = one(instance, "aftercooler")
        assert graph.nodes[cooler]["node_class"] == cooler_class
        water = [d for _, _, d in graph.in_edges(cooler, data=True) if d.get("fluid_code") == "CWS"]
        assert bool(water) is (cooler_class == "TubularHeatExchanger")


def test_the_discharge_has_a_pressure_gauge_and_the_cooler_outlet_a_thermometer() -> None:
    _, instance, graph = stage()
    assert {"discharge_pi", "cooler_outlet_ti", "inlet_ti"} <= set(instance.plan.roles.values())
    gauges = [
        n for n in nodes_with_letters(graph, "PI") if "discharge_pi" == instance.plan.roles[n]
    ]
    assert len(gauges) == 1


# ---- the machine's instruments (S19) --------------------------------------------------------


def test_s19_the_compressor_is_started_from_a_hand_switch_through_an_aef_and_monitored() -> None:
    _, instance, graph = stage()
    machine = one(instance, "compressor")
    assert check_s19(graph) == 1
    tags = {letters(graph, s) for s in located_on(graph, machine)}
    assert {"YI", "ST", "VT"} <= tags  # running status, speed, vibration
    assert graph.nodes[machine]["node_class"] in GENERATED_EQUIPMENT_CLASSES


@pytest.mark.parametrize(("chance", "expected"), [(1.0, True), (0.0, False)])
def test_motor_current_and_bearing_temperature_follow_their_chances(
    chance: float, expected: bool
) -> None:
    density = {"p_motor_current": chance, "p_bearing_temperature": chance}
    _, _, graph = stage(density=density)
    assert bool(nodes_with_letters(graph, "IT")) is expected
    assert bool(nodes_with_letters(graph, "TIAH")) is expected


@pytest.mark.parametrize("vfd", [0.0, 1.0])
def test_s20_the_drives_stay_on_the_machine_sheet(vfd: float) -> None:
    _, instance, graph = stage(density={"p_vfd": vfd})
    assert check_s19(graph) == (2 if vfd else 1)
    assert check_s20(instance) == (2 if vfd else 1)


# ---- variants -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "compressor", ["CentrifugalCompressor", "ReciprocatingCompressor", "RotaryCompressor"]
)
def test_the_compressor_class_follows_the_deck(compressor: str) -> None:
    _, instance, graph = stage({"U2.compressor": (compressor,)})
    assert graph.nodes[one(instance, "compressor")]["node_class"] == compressor
    assert f"compressor={compressor}" in instance.variant
    assert any(e.has_motor for e in instance.plan.equipment if e.node_class == compressor)


def test_the_screw_variant_has_motor_current_and_a_variable_speed_drive() -> None:
    """pid-vocabulary 5.2: screw variant, motor current `IT -> II`, VFD."""
    _, instance, graph = stage(
        {"U2.compressor": ("RotaryCompressor",)}, density={"p_motor_current": 1.0, "p_vfd": 1.0}
    )
    machine = one(instance, "compressor")
    assert "IT" in {letters(graph, s) for s in located_on(graph, machine)}
    assert "PIC" in drives_of(graph, machine)


@pytest.mark.parametrize("present", ["present", "absent"])
def test_the_suction_filter_variant_adds_a_filter_with_a_pressure_drop_tap(present: str) -> None:
    _, instance, graph = stage({"U2.suction_filter": (present,)})
    filters = nodes_of_class(graph, "GasFilter")
    assert bool(filters) is (present == "present")
    assert bool(nodes_with_letters(graph, "PDT")) is (present == "present")
    if filters:
        flow = flow_graph(graph)
        assert nx.has_path(flow, one(instance, "suction_ko_drum"), filters[0])
        assert nx.has_path(flow, filters[0], one(instance, "compressor"))


@pytest.mark.parametrize("present", ["present", "absent"])
def test_the_second_drum_variant_puts_a_drum_between_the_cooler_and_the_out_port(
    present: str,
) -> None:
    _, instance, graph = stage({"U2.discharge_ko_drum": (present,)})
    drums = nodes_of_class(graph, "ScrubbingSeparator")
    assert len(drums) == (2 if present == "present" else 1)
    if present == "present":
        second = one(instance, "discharge_ko_drum")
        flow = flow_graph(graph)
        assert nx.has_path(flow, one(instance, "aftercooler"), second)
        assert nx.has_path(flow, second, instance.port("compressed").node_id)
        assert len(nodes_with_letters(graph, "LV")) == 2


def test_the_stage_is_one_drawing_group() -> None:
    _, instance, _ = stage(
        {"U2.suction_filter": ("present",), "U2.discharge_ko_drum": ("present",)}
    )
    assert set(instance.drawing_group_of.values()) == {"G1"}
    assert len(instance.drawing_group_of) == 5


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = stage()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


@pytest.mark.parametrize("seed", range(8))
def test_only_generated_equipment_classes_appear(seed: int) -> None:
    _, instance, _ = stage(seed=seed)
    assert {e.node_class for e in instance.plan.equipment} <= GENERATED_EQUIPMENT_CLASSES
