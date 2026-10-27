"""U1, the distillation column (design 7.2, pid-vocabulary 5.2 and 13.3): ports, loops, trims.

Each test builds one column on the graph oracle and the DEXPI builder and checks the round trip and
the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names. The vacuum
variants and the sheet layouts are in `test_column_variants.py`.
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
    nodes_of_class,
    nodes_with_letters,
    reaches_a_safety_device,
)
from pattern_harness import PatternHarness, config_with
from trim_harness import ids_with_role

from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.patterns.column import build_distillation_column
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.graph.schema import Relation

_TWO_PUMPS = {"p_single_pump": 0.0, "p_triple_pump_set": 0.0}
_STAY = {"pump_set.group": ("with_suction_vessel",)}  # pumps join their vessel's sheet


def column(
    cards: dict[str, tuple[str, ...]] | None = None,
    seed: int = 0,
    **sections: dict[str, object],
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    """Build one column: `sections` override knob groups (`instruments={"p_cascade": 1.0}`)."""
    sections.setdefault("patterns", {})
    sections.setdefault("trims", {"condensate_mode_weights": {"trap": 1.0}})  # no drain pot's `LV`
    sections["patterns"] = {**_TWO_PUMPS, **sections["patterns"]}
    h = PatternHarness(seed, config_with(**sections), deck_cards={**_STAY, **(cards or {})})
    instance = build_distillation_column(h.pctx)
    instance.plan.write(h.builder)
    return h, instance, assert_pattern_invariants(h)


def one(instance: PatternInstance, role: str) -> str:
    """The id of the single node planned for `role`."""
    (node_id,) = ids_with_role(instance.plan, role)
    return node_id


def letters(graph: nx.DiGraph[str], node_id: str) -> str:
    """The tag letters of a node (`LIC` of `LIC-12005`)."""
    return graph.nodes[node_id]["tag"].partition("-")[0]


def controller_location(graph: nx.DiGraph[str], controller: str) -> str:
    """The item the process sensor feeding `controller` is located on."""
    (sensor,) = [
        s
        for s in sources(graph, controller, Relation.SEND_SIGNAL_TO)
        if graph.nodes[s]["node_class"] == "ProcessSignalGeneratingFunction"
    ]
    (location,) = sources(graph, sensor, Relation.MEASURED_BY)
    return location


def sensor_location(graph: nx.DiGraph[str], valve: str) -> tuple[str, str]:
    """For a control valve: the letters of its controller and the item its sensor is located on."""
    (actuator,) = sources(graph, valve, Relation.CONTROL)
    (controller,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
    return letters(graph, controller), controller_location(graph, controller)


# ---- ports --------------------------------------------------------------------------------------


def test_the_ports_are_feed_distillate_vapour_and_bottoms_last() -> None:
    _, instance, graph = column({"U1.vacuum": ("none",)})
    kinds = {p.name: (p.direction, p.phase) for p in instance.ports}
    assert instance.port_names == ["feed", "distillate", "vapour", "bottoms"]
    assert kinds == {
        "feed": (PortDirection.IN, Phase.LIQUID),
        "distillate": (PortDirection.OUT, Phase.LIQUID),
        "vapour": (PortDirection.OUT, Phase.GAS),
        "bottoms": (PortDirection.OUT, Phase.LIQUID),
    }
    lines = {line.line_number: line for line in instance.plan.lines}
    assert lines[instance.port("feed").line_number].src_id is None
    for name in ("distillate", "vapour", "bottoms"):
        assert lines[instance.port(name).line_number].dst_id is None
        assert instance.port(name).node_id in graph


def test_a_vacuum_device_takes_the_vapour_so_there_is_no_vapour_port() -> None:
    _, instance, _ = column({"U1.vacuum": ("air_ejector",)})
    assert instance.port_names == ["feed", "distillate", "bottoms"]


def test_p_side_draw_adds_a_liquid_out_port_before_the_bottoms() -> None:
    _, instance, graph = column({"U1.vacuum": ("none",)}, flowsheet={"p_side_draw": 1.0})
    assert instance.port_names == ["feed", "distillate", "side_draw", "vapour", "bottoms"]
    side = instance.port("side_draw")
    assert (side.direction, side.phase) == (PortDirection.OUT, Phase.LIQUID)
    assert graph.nodes[side.node_id]["node_class"].endswith("FlowMeasuringElement")
    assert "side_draw" not in column(flowsheet={"p_side_draw": 0.0})[1].port_names


# ---- rules --------------------------------------------------------------------------------------


def test_s6_column_and_drum_each_have_a_safety_valve_without_passing_equipment() -> None:
    _, instance, graph = column()
    assert reaches_a_safety_device(graph, one(instance, "column"))
    assert reaches_a_safety_device(graph, one(instance, "reflux_drum"))


def test_column_pressure_loop_moves_a_valve_on_the_vapour_outlet() -> None:
    """`PT` on the column -> `PIC` -> `PV` between the drum's top tee and the open end."""
    _, instance, graph = column({"U1.vacuum": ("none",)})
    (valve,) = nodes_with_letters(graph, "PV")
    drum, column_id = one(instance, "reflux_drum"), one(instance, "column")
    assert nx.has_path(flow_graph(graph), drum, valve)
    assert nx.has_path(flow_graph(graph), valve, instance.port("vapour").node_id)
    assert sensor_location(graph, valve) == ("PIC", column_id)


def test_reflux_flow_loop_moves_a_valve_on_the_line_from_the_pumps_to_the_column() -> None:
    _, instance, graph = column(instruments={"p_cascade": 0.0})
    (valve,) = nodes_with_letters(graph, "FV")
    pump, column_id = ids_with_role(instance.plan, "reflux_pump")[0], one(instance, "column")
    assert nx.has_path(flow_graph(graph), pump, valve)
    assert nx.has_path(flow_graph(graph), valve, column_id)
    controller, location = sensor_location(graph, valve)
    assert controller == "FIC" and letters(graph, location) == "FE"


def test_level_loops_hold_the_drum_and_the_sump_through_letdown_valves() -> None:
    _, instance, graph = column(instruments={"p_cascade": 0.0})
    drum, column_id = one(instance, "reflux_drum"), one(instance, "column")
    valves = nodes_with_letters(graph, "LV")
    assert all(graph.nodes[v]["node_class"].startswith("Angle") for v in valves)
    valve_at = {sensor_location(graph, v)[1]: v for v in valves}
    assert set(valve_at) == {drum, column_id}
    assert nx.has_path(flow_graph(graph), valve_at[drum], instance.port("distillate").node_id)
    assert nx.has_path(flow_graph(graph), valve_at[column_id], instance.port("bottoms").node_id)


def test_tray_temperature_moves_the_reboiler_steam_valve() -> None:
    """`TT` on the column -> `TIC` -> `TV` on the reboiler's steam line (plain, no cascade)."""
    _, instance, graph = column(
        instruments={"p_cascade": 0.0}, cards={"U1.feed_preheater": ("absent",)}
    )
    (valve,) = nodes_with_letters(graph, "TV")
    reboiler = one(instance, "reboiler")
    assert graph.edges[valve, next(iter(graph.successors(valve)))]["fluid_code"] == "LPS"
    assert nx.has_path(flow_graph(graph), valve, reboiler)
    assert sensor_location(graph, valve) == ("TIC", one(instance, "column"))


def test_s22_with_p_cascade_the_temperature_and_the_distillate_level_set_flow_controllers() -> None:
    _, instance, graph = column(
        instruments={"p_cascade": 1.0}, cards={"U1.feed_preheater": ("absent",)}
    )
    assert check_s22(graph) == 2
    assert not nodes_with_letters(graph, "TV")
    assert len(nodes_with_letters(graph, "FV")) == 3  # reflux, steam, distillate
    assert len(nodes_with_letters(graph, "LV")) == 1  # the bottoms valve: not an eligible slot
    column_id, drum = one(instance, "column"), one(instance, "reflux_drum")
    masters = {
        (letters(graph, c), controller_location(graph, c))
        for c in nodes_with_letters(graph, "TIC", "LIC")
    }
    assert masters == {("TIC", column_id), ("LIC", drum), ("LIC", column_id)}


def test_the_preheater_steam_is_set_by_its_own_outlet_temperature() -> None:
    _, instance, graph = column({"U1.feed_preheater": ("present",)}, instruments={"p_cascade": 0.0})
    pre = one(instance, "feed_preheater")
    located = {sensor_location(graph, v) for v in nodes_with_letters(graph, "TV")}
    assert ("TIC", pre) in located and len(located) == 2
    feed = instance.port("feed").node_id
    assert nx.has_path(flow_graph(graph), feed, pre)
    assert nx.has_path(flow_graph(graph), pre, one(instance, "column"))


@pytest.mark.parametrize("present", ["present", "absent"])
def test_the_reflux_sight_glass_variant_puts_a_glass_on_the_reflux_line(present: str) -> None:
    _, instance, graph = column({"U1.reflux_sight_glass": (present,)})
    glasses = nodes_of_class(graph, "SightGlass", "IlluminatedSightGlass")
    assert bool(glasses) is (present == "present")


def test_every_exchanger_outlet_and_the_feed_carry_a_thermometer() -> None:
    _, instance, graph = column({"U1.feed_preheater": ("present",)})
    for role in ("feed_ti", "preheater_outlet_ti", "reboiler_return_ti", "condenser_outlet_ti"):
        (thermometer,) = ids_with_role(instance.plan, role)
        assert graph.nodes[thermometer]["node_class"] == "ProcessSignalGeneratingFunction"
        assert letters(graph, thermometer) == "TI"


def test_the_column_has_trays_a_differential_pressure_tap_and_level_and_pressure_gauges() -> None:
    _, instance, graph = column()
    column_id = one(instance, "column")
    trays = [s for s in located_on(graph, column_id) if letters(graph, s) in {"TT", "TI"}]
    assert len(trays) >= 2
    assert len(nodes_with_letters(graph, "PDT")) == 1
    assert {"bottom_pi", "sump_level_gauge"} <= set(instance.plan.roles.values())
    assert any(letters(graph, s) == "LG" for s in located_on(graph, column_id))


@pytest.mark.parametrize(("chance", "expected"), [(1.0, True), (0.0, False)])
def test_optional_instruments_follow_their_chances(chance: float, expected: bool) -> None:
    density = {"p_optional_instrument": chance, "p_point_level_switch": chance}
    _, _, graph = column(density=density)
    assert bool(nodes_with_letters(graph, "LSHH")) is expected  # drum high-high alarm
    assert bool(nodes_with_letters(graph, "AT")) is expected  # analyser on the distillate
    assert bool(nodes_with_letters(graph, "LSH")) is expected  # point level switch


# ---- variants and sheets ------------------------------------------------------------------------


@pytest.mark.parametrize("condenser", ["TubularHeatExchanger", "AirCoolingSystem"])
def test_condenser_variant_sets_the_class_and_the_cooling_water(condenser: str) -> None:
    _, instance, graph = column({"U1.condenser": (condenser,)})
    cooler = one(instance, "condenser")
    assert graph.nodes[cooler]["node_class"] == condenser
    water = [d for _, _, d in graph.in_edges(cooler, data=True) if d.get("fluid_code") == "CWS"]
    assert bool(water) is (condenser == "TubularHeatExchanger")  # an air cooler has no water line


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = column()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


@pytest.mark.parametrize("seed", range(8))
def test_only_generated_equipment_classes_appear(seed: int) -> None:
    _, instance, graph = column(seed=seed)
    classes = {e.node_class for e in instance.plan.equipment}
    assert classes <= GENERATED_EQUIPMENT_CLASSES
    assert "SpiralHeatExchanger" not in classes and "ElectricalSeparator" not in classes
