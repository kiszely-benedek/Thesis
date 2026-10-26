"""One plant with every trim and every instrument template: the input of the invariant tests.

Not a test module (no `test_` prefix). `build_instrumented_plant` first writes every trim
(`trim_everything.build_everything`), then attaches a loop to every control valve and every
on-off valve those trims built, then adds the templates that need hosts of their own. Split range
is left out on purpose: it is off by default (and exempt from invariant S4).
"""

from __future__ import annotations

import networkx as nx
from instrument_harness import item_spec, motor_machine
from trim_everything import build_everything
from trim_harness import STYLE, TrimHarness

from plantgraph.benchmark.v2 import (
    instruments,
    instruments_extra,
    trims_extra,
    trims_utility,
    trims_valves,
)
from plantgraph.benchmark.v2.config import InstrumentConvention, InstrumentDensity
from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind
from plantgraph.graph.schema import CONTROL_VALVE_BODY_CLASSES


def build_instrumented_plant(h: TrimHarness) -> None:
    """Every trim, every loop on the trims' valves, and every other template once or more."""
    build_everything(h)
    host = h.equipment("PressureVessel", "V")  # the loops' sensors hang on this vessel's nozzles
    control_valves, on_off_valves = _valves_without_a_driver(h.oracle.graph)
    _attach_control_loops(h, control_valves, host)
    _attach_on_off_drivers(h, on_off_valves, host)
    _flow_loops(h)
    _measurements(h, host)
    _machines(h)
    _alarms_and_pot(h, host)


def _valves_without_a_driver(
    graph: nx.DiGraph[str],
) -> tuple[list[LineItemSpec], list[LineItemSpec]]:
    """The control valves and on-off valves the trims built, by node id."""
    control: list[LineItemSpec] = []
    on_off: list[LineItemSpec] = []
    for node_id in sorted(graph.nodes):
        data = graph.nodes[node_id]
        parsed = parse_tag(data.get("tag") or "")
        if parsed is None or data["node_class"] not in CONTROL_VALVE_BODY_CLASSES:
            continue
        kind = item_kind(data["node_class"], parsed.letters)
        if kind is ItemKind.CONTROL_VALVE:
            control.append(item_spec(graph, node_id))
        elif kind is ItemKind.ON_OFF_VALVE:
            on_off.append(item_spec(graph, node_id))
    return control, on_off


def _write(h: TrimHarness, *plans: TrimPlan) -> None:
    combine(*plans).write(h.builder)


def _attach_control_loops(h: TrimHarness, valves: list[LineItemSpec], host: str) -> None:
    """Plain loops, and loops with a temperature or analyser master (a cascade), in turn."""
    for index, valve in enumerate(valves):
        loop = instruments.control_loop(h.ctx, STYLE, valve, host)
        masters = {1: "T", 2: "A"}
        if index % 4 in masters:
            master = instruments_extra.cascade_master(h.ctx, STYLE, loop, masters[index % 4], host)
            loop = combine(loop, master)
        _write(h, loop)


def _attach_on_off_drivers(h: TrimHarness, valves: list[LineItemSpec], host: str) -> None:
    """Each on-off valve gets one driver: a high trip, a low trip, a hand switch or a flame trip."""
    furnace = h.equipment("Furnace", "H")
    for index, valve in enumerate(valves):
        drivers = (
            lambda v: instruments.process_trip(h.ctx, STYLE, v, host, "L", "HH"),
            lambda v: instruments.process_trip(h.ctx, STYLE, v, host, "P", "LL"),
            lambda v: instruments.hand_switch(h.ctx, STYLE, v),
            lambda v: instruments.flame_failure_trip(h.ctx, STYLE, v, furnace),
        )
        _write(h, drivers[index % len(drivers)](valve))


def _line(h: TrimHarness, plan: TrimPlan) -> TrimPlan:
    """Write a plan with a `run` into a line between two fresh hosts."""
    return h.write(plan, h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK"))


def _flow_loops(h: TrimHarness) -> None:
    """A plain flow loop, one under a level cascade, a ratio loop and a totaliser."""
    for service, cascade in (("liquid", False), ("gas", True)):
        element = trims_valves.flow_element(h.ctx, STYLE, service)  # type: ignore[arg-type]
        valve = trims_valves.control_valve(h.ctx, STYLE, "F")
        loop = instruments.flow_control_loop(h.ctx, STYLE, element, valve)
        if cascade:
            master = instruments_extra.cascade_master(
                h.ctx, STYLE, loop, "L", h.equipment("PressureVessel", "V")
            )
            loop = combine(loop, master)
        _line(h, loop)
    wild = _line(h, trims_valves.flow_element(h.ctx, STYLE, "liquid"))
    additive = trims_valves.flow_element(h.ctx, STYLE, "liquid")
    valve = trims_valves.control_valve(h.ctx, STYLE, "F")
    _line(h, instruments.ratio_control_loop(h.ctx, STYLE, wild.ports["element"], additive, valve))
    metered = _line(h, trims_valves.flow_element(h.ctx, STYLE, "liquid"))
    _write(h, instruments.totaliser(h.ctx, STYLE, part_of(metered, "element")))


def _tee(h: TrimHarness) -> str:
    draft = TrimDraft(h.ctx, STYLE)
    tee = trims_extra.tee_part(draft, "host_tee")
    _line(h, draft.finish(run=(tee,)))
    return tee.node_id


def _measurements(h: TrimHarness, host: str) -> None:
    """Differential pressure, analysers, indicating transmitters with alarms, monitoring points."""
    density = InstrumentDensity()
    _write(h, instruments.differential_pressure(h.ctx, STYLE, _tee(h)))
    _write(h, instruments.analyser_point(h.ctx, STYLE, _tee(h)))
    for side in ("H", "L"):
        _write(h, instruments.indicating_transmitter(h.ctx, STYLE, host, "L", side))  # type: ignore[arg-type]
    column = h.equipment("ProcessColumn", "T")
    _write(h, instruments_extra.monitor_points(h.ctx, STYLE, density, column))
    _write(
        h,
        instruments_extra.temperature_points(h.ctx, STYLE, column, density.tray_temperature_points),
    )
    reactor = h.equipment("PressureVessel", "R")
    _write(h, instruments_extra.multivariable_controller(h.ctx, STYLE, reactor))


def _machines(h: TrimHarness) -> None:
    """Start/stop and status on every machine, speed control, and the four monitors."""
    convention = InstrumentConvention()
    pump = motor_machine(h, "CentrifugalPump")
    compressor = motor_machine(h, "CentrifugalCompressor")
    host = h.equipment("PressureVessel", "V")
    for machine in (pump, compressor):
        _write(h, instruments_extra.machine_start_stop(h.ctx, STYLE, convention, machine))
    _write(h, instruments_extra.speed_control_loop(h.ctx, STYLE, pump, host, "P"))
    for kind in ("speed", "vibration", "bearing_temperature", "motor_current"):
        _write(h, instruments.machine_monitor(h.ctx, STYLE, compressor, kind))  # type: ignore[arg-type]


def _alarms_and_pot(h: TrimHarness, host: str) -> None:
    """Point level alarms, and a drain pot with all three of its loops."""
    tank = h.equipment("Tank", "TK")
    for side in ("H", "L"):
        _write(h, instruments_extra.point_level_alarm(h.ctx, STYLE, tank, side))  # type: ignore[arg-type]
    h.ctx.config = h.ctx.config.model_copy(update={"condensate_mode_weights": {"drain_pot": 1.0}})
    heater = h.equipment("TubularHeatExchanger", "E")
    stub = h.write(trims_utility.utility_return_stub(h.ctx, STYLE, "LPS", heater))
    _write(h, instruments_extra.drain_pot_instruments(h.ctx, STYLE, stub))
