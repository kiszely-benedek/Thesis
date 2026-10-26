"""The base instrument templates (design generator-v2-realism.md 4.4): one test per template.

Each test writes the template to the graph oracle and to the DEXPI builder, checks the round trip,
and checks the chain, the letters and the shared loop number (S8) the template promises.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import item_spec, number_of, solenoids, sources, tags, targets
from trim_harness import STYLE, TrimHarness, assert_round_trip, convention

from plantgraph.benchmark.v2 import instruments, trims_extra, trims_valves, trims_vessel
from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.trim_plan import TrimDraft, combine
from plantgraph.benchmark.v2.vocabulary import OnOffLetter
from plantgraph.graph.schema import Relation

_SENSOR = "ProcessSignalGeneratingFunction"
_PIF = "ProcessInstrumentationFunction"
_PCF = "ProcessControlFunction"
_AF = "ActuatingFunction"
_SIGNAL, _CONTROL, _MEASURED = Relation.SEND_SIGNAL_TO, Relation.CONTROL, Relation.MEASURED_BY


def _flow(graph: nx.DiGraph[str]) -> nx.DiGraph[str]:
    return nx.DiGraph(
        (s, t) for s, t, d in graph.edges(data=True) if d["relation"] == Relation.SEND_TO.value
    )


def _hosts(h: TrimHarness) -> tuple[str, str]:
    return h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")


# ---- xT -> xIC -> AF -> xV ----------------------------------------------------------------------


def test_control_loop_is_transmitter_controller_actuator_valve_with_one_number() -> None:
    """Rules L17, L18, invariants S4, S8: `LT -> LIC -> AF -> LV`, the valve's tag sets the loop."""
    h = TrimHarness(config=convention(p_cv_station=0.0))
    vessel, sink = _hosts(h)
    valve_plan = trims_valves.control_valve(h.ctx, STYLE, "L")
    valve = part_of(valve_plan, "body")
    loop = instruments.control_loop(h.ctx, STYLE, valve, vessel)
    h.write(combine(valve_plan, loop), vessel, sink)
    graph = assert_round_trip(h)
    (transmitter,) = targets(graph, vessel, _MEASURED)
    (controller,) = targets(graph, transmitter, _SIGNAL)
    (actuator,) = targets(graph, controller, _SIGNAL)
    assert targets(graph, actuator, _CONTROL) == [valve.node_id]
    assert tags(graph, [transmitter, controller, valve.node_id])[:2] == [
        f"LT-{graph.nodes[controller]['tag'][4:]}",
        graph.nodes[controller]["tag"],
    ]
    assert graph.nodes[controller]["tag"].startswith("LIC-")
    assert graph.nodes[valve.node_id]["tag"].startswith("LV-")
    assert {number_of(graph, n) for n in (transmitter, controller, valve.node_id)} == {
        number_of(graph, valve.node_id)
    }
    assert graph.nodes[controller]["node_class"] == _PCF
    assert graph.nodes[actuator]["node_class"] == _AF and "tag" not in graph.nodes[actuator]
    assert graph.nodes[actuator]["loop_tag"] == graph.nodes[controller]["tag"]


def test_control_loop_works_on_a_station_and_on_every_variable() -> None:
    h = TrimHarness(config=convention(p_cv_station=1.0))
    for variable in ("F", "P", "L", "T"):
        vessel, sink = _hosts(h)
        valve_plan = trims_valves.control_valve(h.ctx, STYLE, variable)
        valve = part_of(valve_plan, "body")
        loop = instruments.control_loop(h.ctx, STYLE, valve, vessel)
        h.write(combine(valve_plan, loop), vessel, sink)
        graph = assert_round_trip(h)
        (transmitter,) = targets(graph, vessel, _MEASURED)
        assert graph.nodes[transmitter]["tag"].startswith(f"{variable}T-")


def test_control_loop_refuses_a_valve_that_is_not_a_control_valve() -> None:
    h = TrimHarness()
    plan = trims_valves.on_off_valve(h.ctx, STYLE)
    with pytest.raises(ValueError, match="expected a control_valve"):
        instruments.control_loop(h.ctx, STYLE, part_of(plan, "valve"), h.equipment("Tank", "TK"))


def test_flow_control_loop_gives_the_element_the_valves_number() -> None:
    """S8 for flow: `FE-n, FT-n, FIC-n, FV-n`; the element planned first is renumbered."""
    h = TrimHarness(config=convention(p_cv_station=0.0))
    src, dst = _hosts(h)
    element_plan = trims_valves.flow_element(h.ctx, STYLE, "liquid")
    old_element_tag = part_of(element_plan, "element").tag
    valve_plan = trims_valves.control_valve(h.ctx, STYLE, "F")
    loop = instruments.flow_control_loop(h.ctx, STYLE, element_plan, valve_plan)
    plan = h.write(loop, src, dst)
    graph = assert_round_trip(h)
    element = plan.ports["element"]
    valve = plan.ports["body"]
    assert graph.nodes[element]["tag"] == f"FE-{graph.nodes[valve]['tag'][3:]}"
    assert graph.nodes[element]["tag"] != old_element_tag
    (transmitter,) = targets(graph, element, _MEASURED)
    assert graph.nodes[transmitter]["tag"] == f"FT-{graph.nodes[valve]['tag'][3:]}"
    # the element is upstream of the valve on the line
    assert nx.has_path(_flow(graph), element, valve)


# ---- indicating transmitters, alarms, machine monitoring ------------------------------------


def test_indicating_transmitter_is_a_sensor_feeding_an_indicator() -> None:
    """Template `xT -> xI`: two nodes, one number, no actuator."""
    h = TrimHarness()
    vessel, _ = _hosts(h)
    plan = h.write(instruments.indicating_transmitter(h.ctx, STYLE, vessel, "T"))
    graph = assert_round_trip(h)
    transmitter, indicator = plan.ports["transmitter"], plan.ports["indicator"]
    assert targets(graph, vessel, _MEASURED) == [transmitter]
    assert targets(graph, transmitter, _SIGNAL) == [indicator]
    assert graph.nodes[indicator]["node_class"] == _PIF
    assert tags(graph, [transmitter, indicator]) == [
        f"TT-{graph.nodes[indicator]['tag'][3:]}",
        graph.nodes[indicator]["tag"],
    ]
    assert graph.nodes[indicator]["tag"].startswith("TI-")


@pytest.mark.parametrize(("alarm", "letters"), [("H", "LIAH"), ("L", "LIAL")])
def test_indicator_alarm_is_in_the_bubbles_letters_not_a_node(alarm: str, letters: str) -> None:
    """Template `xT -> xIAH`: the alarm adds letters, not a node."""
    h = TrimHarness()
    vessel, _ = _hosts(h)
    plan = h.write(instruments.indicating_transmitter(h.ctx, STYLE, vessel, "L", alarm))  # type: ignore[arg-type]
    graph = assert_round_trip(h)
    assert graph.nodes[plan.ports["indicator"]]["tag"].startswith(f"{letters}-")
    assert len(plan.instruments) == 2


@pytest.mark.parametrize(
    ("kind", "sensor", "bubble"),
    [
        ("speed", "ST", "SI"),
        ("vibration", "VT", "VAH"),
        ("bearing_temperature", "TT", "TIAH"),
        ("motor_current", "IT", "II"),
    ],
)
def test_machine_monitor_is_a_sensor_on_a_machine_nozzle_and_a_bubble(
    kind: str, sensor: str, bubble: str
) -> None:
    """Templates `ST -> SI`, `VT -> VAH`, `TT -> TIAH`, `IT -> II` on a machine."""
    h = TrimHarness()
    machine = h.equipment("CentrifugalCompressor", "K")
    plan = h.write(instruments.machine_monitor(h.ctx, STYLE, machine, kind))  # type: ignore[arg-type]
    graph = assert_round_trip(h)
    assert targets(graph, machine, _MEASURED) == [plan.ports["transmitter"]]
    assert graph.nodes[plan.ports["transmitter"]]["tag"].startswith(f"{sensor}-")
    assert graph.nodes[plan.ports["indicator"]]["tag"].startswith(f"{bubble}-")


# ---- trips and hand switches (S7) ---------------------------------------------------------------


@pytest.mark.parametrize(("level", "switch"), [("HH", "LSHH"), ("LL", "LSLL")])
def test_process_trip_is_transmitter_switch_actuator_and_a_solenoid_valve(
    level: str, switch: str
) -> None:
    """Template `xT -> xSHH -> AF -> XV`, invariant S7: the XV has its `XY-n` solenoid."""
    h = TrimHarness(config=convention(p_limit_switches=0.0))
    src, dst = _hosts(h)
    valve_plan = trims_valves.on_off_valve(h.ctx, STYLE)
    valve = part_of(valve_plan, "valve")
    trip = instruments.process_trip(h.ctx, STYLE, valve, src, "L", level)  # type: ignore[arg-type]
    h.write(combine(valve_plan, trip), src, dst)
    graph = assert_round_trip(h)
    number = number_of(graph, valve.node_id)
    assert (
        graph.nodes[trip.ports["transmitter"]]["tag"]
        == f"LT-{graph.nodes[valve.node_id]['tag'][3:]}"
    )
    assert graph.nodes[trip.ports["trip_switch"]]["tag"].startswith(f"{switch}-")
    assert number_of(graph, trip.ports["trip_switch"]) == number
    assert targets(graph, trip.ports["actuator"], _CONTROL) == [valve.node_id]
    assert solenoids(h)[valve.node_id] == f"XY-{graph.nodes[valve.node_id]['tag'][3:]}"


def test_flame_failure_trip_is_be_bsl_af_xv_on_a_furnace() -> None:
    """Template `BE -> BSL -> AF -> XV`: the flame sensor sits on the furnace."""
    h = TrimHarness()
    furnace = h.equipment("Furnace", "H")
    dst = h.equipment("Tank", "TK")
    valve_plan = trims_valves.on_off_valve(h.ctx, STYLE)
    valve = part_of(valve_plan, "valve")
    trip = instruments.flame_failure_trip(h.ctx, STYLE, valve, furnace)
    h.write(combine(valve_plan, trip), dst, furnace)
    graph = assert_round_trip(h)
    assert tags(graph, targets(graph, furnace, _MEASURED))[0].startswith("BE-")
    assert graph.nodes[trip.ports["trip_switch"]]["tag"].startswith("BSL-")
    assert targets(graph, trip.ports["actuator"], _CONTROL) == [valve.node_id]


def test_hand_switch_is_a_bubble_without_a_sensor_driving_an_xv() -> None:
    """Template `HS -> AF -> XV`, invariant S7: remote manual, so the loop has no sensor."""
    h = TrimHarness()
    src, dst = _hosts(h)
    valve_plan = trims_valves.on_off_valve(h.ctx, STYLE)
    valve = part_of(valve_plan, "valve")
    switch = instruments.hand_switch(h.ctx, STYLE, valve)
    h.write(combine(valve_plan, switch), src, dst)
    graph = assert_round_trip(h)
    bubble = switch.ports["hand_switch"]
    assert graph.nodes[bubble]["tag"].startswith("HS-")
    assert sources(graph, bubble, _SIGNAL) == []
    assert targets(graph, switch.ports["actuator"], _CONTROL) == [valve.node_id]
    assert solenoids(h)[valve.node_id].startswith("XY-")  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("letter", "valve", "solenoid"), [(OnOffLetter.X, "XV", "XY"), (OnOffLetter.Y, "YV", "YY")]
)
def test_the_trains_on_off_letter_gives_the_valve_and_its_solenoid(
    letter: OnOffLetter, valve: str, solenoid: str
) -> None:
    """Template X/Y: a train's letter shows in the valve (`YV`) and in its solenoid (`YY`)."""
    h = TrimHarness(on_off=letter)
    src, dst = _hosts(h)
    valve_plan = trims_valves.on_off_valve(h.ctx, STYLE)
    part = part_of(valve_plan, "valve")
    trip = instruments.process_trip(h.ctx, STYLE, part, src, "P", "HH")
    h.write(combine(valve_plan, trip), src, dst)
    graph = assert_round_trip(h)
    assert graph.nodes[part.node_id]["tag"].startswith(f"{valve}-")
    assert solenoids(h)[part.node_id].startswith(f"{solenoid}-")  # type: ignore[union-attr]


def test_position_switches_share_the_xv_number_and_sit_on_the_valve() -> None:
    """Template `ZSO`, `ZSC` on an XV: built by the 6.9 trim, one PSGF each, on the valve."""
    h = TrimHarness(config=convention(p_limit_switches=1.0))
    src, dst = _hosts(h)
    plan = h.write(trims_valves.on_off_valve(h.ctx, STYLE), src, dst)
    graph = assert_round_trip(h)
    valve = plan.ports["valve"]
    switches = targets(graph, valve, _MEASURED)
    assert sorted(graph.nodes[n]["tag"][:3] for n in switches) == ["ZSC", "ZSO"]
    assert {number_of(graph, n) for n in switches} == {number_of(graph, valve)}
    assert all(graph.out_degree(n) == 0 for n in switches)  # one PSGF, no bubble (I-2)


def test_local_gauges_are_one_sensor_each_with_no_bubble() -> None:
    """Template local gauges (convention I-2): `PI` and `TI` are single PSGFs of degree one."""
    h = TrimHarness()
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(
        trims_vessel.vessel_top_instruments(h.ctx, STYLE, vessel), vessel, h.equipment("Tank", "TK")
    )
    graph = assert_round_trip(h)
    gauges = [n for n, d in graph.nodes(data=True) if d["node_class"] == _SENSOR]
    assert len(gauges) == 2 and plan.run == ()
    assert all(graph.out_degree(n) == 0 and graph.in_degree(n) == 1 for n in gauges)
    assert graph.nodes[gauges[0]]["loop_tag"] == graph.nodes[gauges[0]]["tag"]


# ---- measurements that are not loops ------------------------------------------------------------


def _tee_on_a_line(h: TrimHarness) -> str:
    draft = TrimDraft(h.ctx, STYLE)
    tee = trims_extra.tee_part(draft, "host_tee")
    src, dst = _hosts(h)
    h.write(draft.finish(run=(tee,)), src, dst)
    return tee.node_id


def test_differential_pressure_is_a_pdt_pdi_pair_on_a_needle_valve_tap() -> None:
    """Template `PDT -> PDI`: tap `tee -> needle valve -> flange`, transmitter on the flange."""
    h = TrimHarness()
    tee = _tee_on_a_line(h)
    plan = h.write(instruments.differential_pressure(h.ctx, STYLE, tee))
    graph = assert_round_trip(h)
    flange = plan.ports["tap_flange"]
    root = sources(graph, flange, Relation.SEND_TO)[0]
    assert graph.nodes[root]["node_class"] == "NeedleValve"
    assert sources(graph, root, Relation.SEND_TO) == [tee]
    assert tags(graph, targets(graph, flange, _MEASURED))[0].startswith("PDT-")
    assert graph.nodes[plan.ports["indicator"]]["tag"].startswith("PDI-")


def test_totaliser_takes_the_flow_elements_number() -> None:
    """Template `FT -> FQI`: `FE-n`, `FT-n`, `FQI-n`."""
    h = TrimHarness()
    src, dst = _hosts(h)
    element_plan = h.write(trims_valves.flow_element(h.ctx, STYLE, "liquid"), src, dst)
    element = part_of(element_plan, "element")
    plan = h.write(instruments.totaliser(h.ctx, STYLE, element))
    graph = assert_round_trip(h)
    assert graph.nodes[plan.ports["indicator"]]["tag"] == f"FQI-{element.tag[3:]}"  # type: ignore[index]
    assert targets(graph, element.node_id, _MEASURED) == [plan.ports["transmitter"]]


def test_analyser_point_is_an_at_on_a_flange_feeding_an_ai() -> None:
    """Template `AT -> AI`: the probe flange is a blind flange on a tap."""
    h = TrimHarness()
    tee = _tee_on_a_line(h)
    plan = h.write(instruments.analyser_point(h.ctx, STYLE, tee))
    graph = assert_round_trip(h)
    flange = plan.ports["flange"]
    assert graph.nodes[flange]["node_class"] == "BlindFlange"
    assert targets(graph, flange, _MEASURED) == [plan.ports["transmitter"]]
    assert graph.nodes[plan.ports["transmitter"]]["tag"].startswith("AT-")
    assert graph.nodes[plan.ports["indicator"]]["tag"].startswith("AI-")


def test_analyser_point_without_an_indicator_is_only_the_tap() -> None:
    h = TrimHarness()
    plan = h.write(instruments.analyser_point(h.ctx, STYLE, _tee_on_a_line(h), indicator=False))
    assert plan.instruments == () and set(plan.ports) == {"flange"}


def test_ratio_control_loop_has_two_transmitters_feeding_one_controller() -> None:
    """Template `FFT, FT -> FFIC -> AF -> FV` (blending): controlled and wild stream, one number."""
    h = TrimHarness(config=convention(p_cv_station=0.0))
    main_src, main_dst = _hosts(h)
    wild_plan = h.write(trims_valves.flow_element(h.ctx, STYLE, "liquid"), main_src, main_dst)
    wild = wild_plan.ports["element"]
    add_src, add_dst = _hosts(h)
    element_plan = trims_valves.flow_element(h.ctx, STYLE, "liquid")
    valve_plan = trims_valves.control_valve(h.ctx, STYLE, "F")
    loop = instruments.ratio_control_loop(h.ctx, STYLE, wild, element_plan, valve_plan)
    plan = h.write(loop, add_src, add_dst)
    graph = assert_round_trip(h)
    controller = plan.ports["controller"]
    assert graph.nodes[controller]["tag"].startswith("FFIC-")
    feeders = sources(graph, controller, _SIGNAL)
    assert sorted(tags(graph, feeders))[0].startswith("FFT-")
    assert {number_of(graph, n) for n in [*feeders, controller, plan.ports["body"]]} == {
        number_of(graph, plan.ports["body"])
    }
    assert {graph.nodes[n]["loop_tag"] for n in feeders} == {graph.nodes[controller]["tag"]}
    assert targets(graph, wild, _MEASURED) == [plan.ports["transmitter_wild"]]


def test_item_spec_reads_a_valve_back_from_the_graph() -> None:
    """The harness helper the whole-plant test uses to attach a loop to a trim's valve."""
    h = TrimHarness()
    src, dst = _hosts(h)
    plan = h.write(trims_valves.on_off_valve(h.ctx, STYLE), src, dst)
    assert item_spec(h.oracle.graph, plan.ports["valve"]) == part_of(plan, "valve")
