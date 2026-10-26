"""The instrument templates the real samples added (design pid-vocabulary 5.1, 5.3, 13.5)."""

from __future__ import annotations

import pytest
from instrument_harness import motor_machine, number_of, sources, tags, targets
from pydantic import ValidationError
from trim_harness import STYLE, TrimHarness, assert_round_trip, convention

from plantgraph.benchmark.v2 import instruments, instruments_extra, trims_utility, trims_valves
from plantgraph.benchmark.v2.config import (
    GeneratorConfigV2,
    InstrumentConvention,
    InstrumentDensity,
    IntRange,
)
from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.trim_plan import combine
from plantgraph.graph.schema import Relation

_PCF = "ProcessControlFunction"
_AEF = "ActuatingElectricalFunction"
_SIGNAL, _CONTROL, _MEASURED = Relation.SEND_SIGNAL_TO, Relation.CONTROL, Relation.MEASURED_BY


def _hosts(h: TrimHarness) -> tuple[str, str]:
    return h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")


# ---- cascade (S22) ---------------------------------------------------------------------------


@pytest.mark.parametrize(("master", "master_letters"), [("L", "LT"), ("T", "TT"), ("A", "AT")])
def test_cascade_slave_has_one_sensor_and_one_master_and_keeps_the_valves_tag(
    master: str, master_letters: str
) -> None:
    """Invariant S22: slave PCF <- one PSGF and one PCF; the valve carries the slave's number."""
    h = TrimHarness(config=convention(p_cv_station=0.0))
    vessel, sink = _hosts(h)
    slave = instruments.flow_control_loop(
        h.ctx,
        STYLE,
        trims_valves.flow_element(h.ctx, STYLE, "liquid"),
        trims_valves.control_valve(h.ctx, STYLE, "F"),
    )
    cascade = instruments_extra.cascade_master(h.ctx, STYLE, slave, master, vessel)
    plan = h.write(combine(slave, cascade), vessel, sink)
    graph = assert_round_trip(h)
    slave_controller = plan.ports["controller"]
    feeders = sources(graph, slave_controller, _SIGNAL)
    kinds = sorted(graph.nodes[n]["node_class"] for n in feeders)
    assert kinds == [_PCF, "ProcessSignalGeneratingFunction"]
    master_controller = plan.ports["master_controller"]
    assert master_controller in feeders
    assert graph.nodes[master_controller]["node_class"] == _PCF
    (master_sensor,) = sources(graph, master_controller, _SIGNAL)
    assert graph.nodes[master_sensor]["tag"].startswith(f"{master_letters}-")
    assert number_of(graph, slave_controller) == number_of(graph, plan.ports["body"])
    # the two loops stay apart: master and slave each carry their own bubble's tag
    assert graph.nodes[master_sensor]["loop_tag"] == graph.nodes[master_controller]["tag"]
    assert (
        graph.nodes[plan.ports["transmitter"]]["loop_tag"] == graph.nodes[slave_controller]["tag"]
    )
    assert graph.nodes[plan.ports["actuator"]]["loop_tag"] == graph.nodes[slave_controller]["tag"]


# ---- split range (off by default) ------------------------------------------------------------


def test_split_range_is_never_drawn_at_its_default() -> None:
    """The default `p_split_range` is 0, so the draw never says yes (pid-vocabulary 7.1)."""
    h = TrimHarness()
    assert InstrumentConvention().p_split_range == 0.0
    assert not any(
        instruments_extra.wants_split_range(h.ctx, InstrumentConvention()) for _ in range(500)
    )


def test_split_range_is_drawn_when_its_chance_is_raised() -> None:
    h = TrimHarness()
    assert instruments_extra.wants_split_range(h.ctx, InstrumentConvention(p_split_range=1.0))


def test_split_range_loop_is_one_controller_driving_two_valves() -> None:
    """Template `PIC -> AF1 -> PV-A`, `-> AF2 -> PV-B`: one controller, two actuators."""
    h = TrimHarness(config=convention(p_cv_station=0.0))
    vessel, sink = _hosts(h)
    first = trims_valves.control_valve(h.ctx, STYLE, "P")
    second = trims_valves.control_valve(h.ctx, STYLE, "P")
    loop = instruments_extra.split_range_loop(
        h.ctx, STYLE, part_of(first, "body"), part_of(second, "body"), vessel
    )
    both = combine(first.with_port_prefix("a"), second.with_port_prefix("b"), loop)
    h.write(both, vessel, sink)
    graph = assert_round_trip(h)
    actuators = targets(graph, loop.ports["controller"], _SIGNAL)
    assert len(actuators) == 2
    controlled = sorted(v for a in actuators for v in targets(graph, a, _CONTROL))
    assert controlled == sorted([both.ports["a.body"], both.ports["b.body"]])
    # S4 exemption: the second valve keeps its own number (tags stay unique, no suffix exists)
    assert number_of(graph, both.ports["a.body"]) == number_of(graph, loop.ports["controller"])
    assert number_of(graph, both.ports["b.body"]) != number_of(graph, loop.ports["controller"])


def test_split_range_refuses_an_on_off_valve_as_the_second_valve() -> None:
    h = TrimHarness(config=convention(p_cv_station=0.0))
    first = trims_valves.control_valve(h.ctx, STYLE, "P")
    xv = trims_valves.on_off_valve(h.ctx, STYLE)
    with pytest.raises(ValueError, match="expected a control valve as the second"):
        instruments_extra.split_range_loop(
            h.ctx, STYLE, part_of(first, "body"), part_of(xv, "valve"), h.equipment("Tank", "TK")
        )


# ---- motors: start/stop, status, variable speed ----------------------------------------------


def test_machine_start_stop_is_hs_aef_machine_with_a_running_status() -> None:
    """Template `HS -> AEF -> machine` and `YI` (S19): one signal source, one control target."""
    h = TrimHarness()
    pump = motor_machine(h)
    plan = h.write(instruments_extra.machine_start_stop(h.ctx, STYLE, InstrumentConvention(), pump))
    graph = assert_round_trip(h)
    switch = plan.ports["hand_switch"]
    (actuator,) = targets(graph, switch, _SIGNAL)
    assert graph.nodes[actuator]["node_class"] == _AEF
    assert targets(graph, actuator, _CONTROL) == [pump]
    assert graph.nodes[switch]["tag"].startswith("HS-")
    (status,) = targets(graph, pump, _MEASURED)
    assert graph.nodes[status]["tag"] == f"YI-{graph.nodes[switch]['tag'][3:]}"
    assert graph.out_degree(status) == 0


def test_machine_start_stop_is_drawn_with_chance_p_motor_hs() -> None:
    h = TrimHarness()
    pump = motor_machine(h)
    none = instruments_extra.machine_start_stop(
        h.ctx, STYLE, InstrumentConvention(p_motor_hs=0.0), pump
    )
    assert none.instruments == () and none.links == ()
    assert InstrumentConvention().p_motor_hs == 1.0


def test_start_stop_needs_a_motor_driven_machine() -> None:
    h = TrimHarness()
    plan = instruments_extra.machine_start_stop(
        h.ctx, STYLE, InstrumentConvention(), h.equipment("CentrifugalPump", "P")
    )
    with pytest.raises(ValueError, match="motor-driven machine"):
        h.write(plan)


def test_speed_control_loop_is_pt_pic_aef_pump() -> None:
    """Template `xT -> xIC -> AEF -> machine`: a variable-speed drive follows a pressure loop."""
    h = TrimHarness()
    pump = motor_machine(h)
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(instruments_extra.speed_control_loop(h.ctx, STYLE, pump, vessel, "P"))
    graph = assert_round_trip(h)
    assert tags(graph, [plan.ports["transmitter"], plan.ports["controller"]])[1].startswith("PIC-")
    assert graph.nodes[plan.ports["controller"]]["node_class"] == _PCF
    assert graph.nodes[plan.ports["actuator"]]["node_class"] == _AEF
    assert targets(graph, plan.ports["actuator"], _CONTROL) == [pump]
    assert targets(graph, vessel, _MEASURED) == [plan.ports["transmitter"]]


# ---- point level, drain pot, reactor ---------------------------------------------------------


@pytest.mark.parametrize(("side", "switch", "alarm"), [("H", "LSH", "LAH"), ("L", "LSL", "LAL")])
def test_point_level_alarm_is_a_level_switch_feeding_an_alarm(
    side: str, switch: str, alarm: str
) -> None:
    """Template `LSH -> LAH`, `LSL -> LAL` on tanks, drums and drain pots."""
    h = TrimHarness()
    tank = h.equipment("Tank", "TK")
    plan = h.write(instruments_extra.point_level_alarm(h.ctx, STYLE, tank, side))  # type: ignore[arg-type]
    graph = assert_round_trip(h)
    assert graph.nodes[plan.ports["transmitter"]]["tag"].startswith(f"{switch}-")
    assert graph.nodes[plan.ports["indicator"]]["tag"].startswith(f"{alarm}-")
    assert targets(graph, tank, _MEASURED) == [plan.ports["transmitter"]]


def test_drain_pot_has_a_level_loop_a_tube_leak_trip_and_a_conductivity_indicator() -> None:
    """Template `CT -> CI`, `CSHH -> XV` and the pot's `LT -> LIC -> LV` (pid-vocabulary 5.3)."""
    h = TrimHarness(config=convention())
    h.ctx.config = h.ctx.config.model_copy(update={"condensate_mode_weights": {"drain_pot": 1.0}})
    heater = h.equipment("TubularHeatExchanger", "E")
    stub = h.write(trims_utility.utility_return_stub(h.ctx, STYLE, "LPS", heater))
    instruments_plan = instruments_extra.drain_pot_instruments(h.ctx, STYLE, stub)
    instruments_plan.write(h.builder)
    graph = assert_round_trip(h)
    pot = next(i.node_id for i in stub.equipment)
    level_valve = next(n for n, role in stub.roles.items() if role == "pot_level_valve")
    trip_valve = next(n for n, role in stub.roles.items() if role == "pot_trip_valve")
    assert {graph.nodes[n]["tag"][:2] for n in targets(graph, pot, _MEASURED)} == {"LT", "CT"}
    level_controller = instruments_plan.ports["level.controller"]
    assert targets(graph, instruments_plan.ports["level.actuator"], _CONTROL) == [level_valve]
    assert graph.nodes[level_controller]["tag"].startswith("LIC-")
    trip_switch = instruments_plan.ports["trip.trip_switch"]
    assert graph.nodes[trip_switch]["tag"].startswith("CSHH-")
    assert targets(graph, instruments_plan.ports["trip.actuator"], _CONTROL) == [trip_valve]
    indicator = instruments_plan.ports["conductivity.indicator"]
    assert graph.nodes[indicator]["tag"].startswith("CI-")
    # the trip has a transmitter of its own, apart from the indicating one
    assert sources(graph, trip_switch, _SIGNAL) != sources(graph, indicator, _SIGNAL)


def test_multivariable_controller_reads_a_temperature_and_a_pressure() -> None:
    """Template `TT, PT -> UC` on a reactor."""
    h = TrimHarness()
    reactor = h.equipment("PressureVessel", "R")
    plan = h.write(instruments_extra.multivariable_controller(h.ctx, STYLE, reactor))
    graph = assert_round_trip(h)
    controller = plan.ports["controller"]
    assert graph.nodes[controller]["tag"].startswith("UC-")
    assert graph.nodes[controller]["node_class"] == _PCF
    assert sorted(tags(graph, sources(graph, controller, _SIGNAL)))[0][:2] in {"PT", "TT"}
    assert {graph.nodes[n]["loop_tag"] for n in sources(graph, controller, _SIGNAL)} == {
        graph.nodes[controller]["tag"]
    }
    assert len(targets(graph, reactor, _MEASURED)) == 2


# ---- monitoring points and density -----------------------------------------------------------


def test_monitor_points_draw_five_to_seven_points_and_all_local_when_asked() -> None:
    """Density 13.5: `monitor_points_per_major_item` 5-7; `p_monitor_local` 1 gives gauges only."""
    counts = set()
    for seed in range(12):
        h = TrimHarness(seed=seed)
        column = h.equipment("ProcessColumn", "T")
        density = InstrumentDensity(p_monitor_local=1.0)
        plan = h.write(instruments_extra.monitor_points(h.ctx, STYLE, density, column))
        graph = assert_round_trip(h)
        counts.add(len(targets(graph, column, _MEASURED)))
        assert all(graph.out_degree(n) == 0 for n in targets(graph, column, _MEASURED))
        assert len(plan.instruments) == len(targets(graph, column, _MEASURED))
    assert counts <= {5, 6, 7} and len(counts) > 1


def test_monitor_points_use_transmitters_with_indicators_when_not_local() -> None:
    h = TrimHarness()
    vessel = h.equipment("PressureVessel", "V")
    density = InstrumentDensity(
        p_monitor_local=0.0,
        monitor_points_per_major_item=IntRange(low=3, high=3),
        monitor_variable_weights={"T": 1.0, "P": 1e-9},
    )
    h.write(instruments_extra.monitor_points(h.ctx, STYLE, density, vessel))
    graph = assert_round_trip(h)
    sensors = targets(graph, vessel, _MEASURED)
    assert len(sensors) == 3
    assert all(graph.nodes[n]["tag"].startswith("TT-") for n in sensors)
    assert all(graph.out_degree(n) == 1 for n in sensors)


def test_temperature_points_count_follows_the_range() -> None:
    h = TrimHarness()
    column = h.equipment("ProcessColumn", "T")
    density = InstrumentDensity()
    plan = h.write(
        instruments_extra.temperature_points(h.ctx, STYLE, column, density.tray_temperature_points)
    )
    graph = assert_round_trip(h)
    assert 2 <= len(targets(graph, column, _MEASURED)) <= 4
    assert len(plan.instruments) == 2 * len(targets(graph, column, _MEASURED))


def test_alarm_side_follows_p_indicator_alarm() -> None:
    h = TrimHarness()
    never = InstrumentDensity(p_indicator_alarm=0.0)
    always = InstrumentDensity(p_indicator_alarm=1.0)
    assert instruments_extra.alarm_side(h.ctx, never, "H") is None
    assert instruments_extra.alarm_side(h.ctx, always, "L") == "L"


def test_density_defaults_are_the_declared_values_and_survive_json() -> None:
    density = InstrumentDensity()
    assert (
        density.monitor_points_per_major_item.low,
        density.monitor_points_per_major_item.high,
    ) == (5, 7)
    assert density.p_monitor_local == 0.7 and density.p_vfd == 0.5
    assert (density.tray_temperature_points.low, density.tray_temperature_points.high) == (2, 4)
    assert (density.reactor_temperature_points.low, density.reactor_temperature_points.high) == (
        3,
        5,
    )
    config = GeneratorConfigV2(n_units=1)
    assert GeneratorConfigV2.model_validate_json(config.model_dump_json()) == config


def test_density_rejects_a_reversed_range_and_a_non_positive_weight() -> None:
    with pytest.raises(ValidationError, match="low <= high"):
        IntRange(low=7, high=5)
    with pytest.raises(ValidationError, match="strictly positive"):
        InstrumentDensity(monitor_variable_weights={"T": 0.0, "P": 1.0})
