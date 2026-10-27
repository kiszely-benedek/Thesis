"""The lines and instruments of the compressor stage U2, one function per part.

See `compression.py` for the stage as a whole.

Gas flows: inlet line, knock-out drum, [filter], compressor, aftercooler, [second drum], out. A
**knock-out (KO) drum** is a vessel that separates liquid droplets from the gas before they can
damage the compressor. The functions close their main line first (see `assembly.close_run`), so a
caller may combine the plans in the order it wants them written.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.instrument_draft import parsed_tag_of, part_of, with_part_number
from plantgraph.benchmark.v2.instruments import (
    control_loop,
    differential_pressure,
    machine_monitor,
    process_trip,
)
from plantgraph.benchmark.v2.instruments_extra import (
    machine_start_stop,
    monitor_points,
    speed_control_loop,
)
from plantgraph.benchmark.v2.patterns.assembly import (
    close_run,
    pressure_gauge_tap,
    quiet,
    run_of,
    tee_plan,
    thermometer_tap,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.trim_context import LineStyle
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims import compressor_discharge, compressor_suction
from plantgraph.benchmark.v2.trims_valves import (
    battery_limit,
    control_valve,
    flow_element,
    on_off_valve,
)
from plantgraph.benchmark.v2.trims_vessel import vessel_trims, vessel_vent_drain
from plantgraph.graph.schema import NodeClass

SCRUBBER = NodeClass.SCRUBBING_SEPARATOR.value


# ---- inlet and outlet ------------------------------------------------------------------------


def inlet_line(ctx: PatternContext, style: LineStyle, drum_id: str) -> tuple[TrimPlan, str]:
    """The gas in-port line to the first drum, with a thermometer and the recycle's return tee.

    Returns the plan and the id of the tee where the anti-surge recycle line comes back.
    """
    return_tee = tee_plan(ctx, "recycle_return_tee")
    thermometer = tee_plan(ctx, "inlet_thermometer_tee")
    run = run_of(battery_limit(ctx.trim, style), return_tee, thermometer)
    main = close_run(ctx, run, None, drum_id, style=style)
    tap = thermometer_tap(ctx, thermometer.ports["tee"], "inlet_ti")
    return combine(main, tap), return_tee.ports["tee"]


class Outlet(BaseModel):
    """The discharge side after the aftercooler: its plan and the two tees other lines use."""

    model_config = ConfigDict(frozen=True)

    plan: TrimPlan
    takeoff_tee: str  # the anti-surge recycle leaves here
    last_tee: str  # on the out-port's line: the line that leaves the stage


def outlet_lines(
    ctx: PatternContext, style: LineStyle, cooler_id: str, second_drum_id: str | None
) -> Outlet:
    """Cooler outlet (thermometer, recycle take-off), [second drum], gauge, battery limit."""
    thermometer = tee_plan(ctx, "cooler_outlet_tee")
    takeoff = tee_plan(ctx, "recycle_takeoff_tee")
    gauge = tee_plan(ctx, "discharge_gauge_tee")
    taps = [
        thermometer_tap(ctx, thermometer.ports["tee"], "cooler_outlet_ti"),
        pressure_gauge_tap(ctx, gauge.ports["tee"], "discharge_pi"),
    ]
    last_run = run_of(gauge, battery_limit(ctx.trim, style))
    if second_drum_id is None:
        mains = [
            close_run(ctx, run_of(thermometer, takeoff, last_run), cooler_id, None, style=style)
        ]
    else:
        top = vessel_trims(ctx.trim, style, second_drum_id, SCRUBBER)
        first = close_run(ctx, run_of(thermometer, takeoff), cooler_id, second_drum_id, style=style)
        last = close_run(ctx, run_of(top, last_run), second_drum_id, None, style=style)
        mains = [first, last]
    return Outlet(
        plan=combine(*mains, *taps), takeoff_tee=takeoff.ports["tee"], last_tee=gauge.ports["tee"]
    )


def recycle_line(
    ctx: PatternContext, style: LineStyle, valve: TrimPlan, takeoff_tee: str, return_tee: str
) -> TrimPlan:
    """The anti-surge recycle: cooler outlet tee, its control valve, back to the inlet tee."""
    return close_run(ctx, valve, takeoff_tee, return_tee, StreamKindV2.RECYCLE, style)


# ---- suction side ----------------------------------------------------------------------------


def anti_surge(ctx: PatternContext, style: LineStyle) -> tuple[TrimPlan, TrimPlan]:
    """The anti-surge loop `FE, FT -> FIC -> FV`, split in two parts.

    Surge is a flow reversal in a compressor that runs too far below its design flow; the loop
    opens a recycle valve to keep enough gas passing. Returns the flow element (it sits on the
    suction line) and the valve with its loop (it sits on the recycle line); one loop number.
    """
    element = flow_element(ctx.trim, style, "gas")
    valve = control_valve(ctx.trim, style, "F")
    body, flow = part_of(valve, "body"), part_of(element, "element")
    number = parsed_tag_of(body, ctx.unit_no).sequence
    renumbered = with_part_number(element, flow.node_id, number)
    loop = control_loop(ctx.trim, style, body, flow.node_id)
    return renumbered, combine(valve, loop)


def suction_lines(
    ctx: PatternContext,
    style: LineStyle,
    drum_id: str,
    filter_id: str | None,
    machine_id: str,
    flow_element_plan: TrimPlan,
    speed_drive: bool,
) -> TrimPlan:
    """Drum top (trims), [filter], trip valve, [pressure valve], flow element, block, strainer.

    The drum's high-level trip shuts the on-off valve. The suction pressure is held by a valve on
    the line, or by the compressor's speed when it has a variable-speed drive.
    """
    top = vessel_trims(ctx.trim, style, drum_id, SCRUBBER)
    trip_valve = on_off_valve(ctx.trim, style)
    trip = process_trip(ctx.trim, style, part_of(trip_valve, "valve"), drum_id, "L", "HH")
    pressure = _suction_pressure_valve(ctx, style, drum_id, speed_drive)
    tail = (trip_valve, trip, pressure, flow_element_plan, compressor_suction(ctx.trim, style))
    if filter_id is None:
        return close_run(ctx, run_of(top, *tail), drum_id, machine_id, style=style)
    dp_tee = tee_plan(ctx, "filter_dp_tee")
    before = close_run(ctx, run_of(top, dp_tee), drum_id, filter_id, style=style)
    dp = differential_pressure(ctx.trim, style, dp_tee.ports["tee"])
    drains = vessel_vent_drain(ctx.trim, style, filter_id)
    after = close_run(ctx, run_of(*tail), filter_id, machine_id, style=style)
    return combine(before, quiet(dp), quiet(drains), after)


def _suction_pressure_valve(
    ctx: PatternContext, style: LineStyle, drum_id: str, speed_drive: bool
) -> TrimPlan:
    if speed_drive:
        return combine()
    valve = control_valve(ctx.trim, style, "P")
    return combine(valve, control_loop(ctx.trim, style, part_of(valve, "body"), drum_id))


def discharge_line(
    ctx: PatternContext, style: LineStyle, machine_id: str, cooler_id: str
) -> TrimPlan:
    """Compressor to aftercooler: safety valve tee, check valve, block valve (L16)."""
    return close_run(ctx, compressor_discharge(ctx.trim, style), machine_id, cooler_id, style=style)


# ---- drums and the machine -------------------------------------------------------------------


def drum_liquid_outlet(ctx: PatternContext, drum_id: str) -> TrimPlan:
    """The knocked-out liquid leaves through a level valve (`LT -> LIC -> LV`) to a drain stub."""
    valve = control_valve(ctx.trim, ctx.style, "L", letdown=True)
    loop = control_loop(ctx.trim, ctx.style, part_of(valve, "body"), drum_id)
    return close_run(ctx, combine(valve, loop), drum_id, None)


def machine_instruments(
    ctx: PatternContext, style: LineStyle, machine_id: str, drum_id: str, speed_drive: bool
) -> TrimPlan:
    """Start/stop, speed and vibration, optional bearing temperature and motor current.

    With a variable-speed drive the suction pressure also sets the compressor speed
    (`PT -> PIC -> AEF`). Monitoring points of a major item follow.
    """
    parts = [
        machine_start_stop(ctx.trim, style, ctx.instruments, machine_id),
        machine_monitor(ctx.trim, style, machine_id, "speed"),
        machine_monitor(ctx.trim, style, machine_id, "vibration"),
    ]
    if ctx.chance(ctx.density.p_bearing_temperature):
        parts.append(machine_monitor(ctx.trim, style, machine_id, "bearing_temperature"))
    if ctx.chance(ctx.density.p_motor_current):
        parts.append(machine_monitor(ctx.trim, style, machine_id, "motor_current"))
    if speed_drive:
        parts.append(speed_control_loop(ctx.trim, style, machine_id, drum_id, "P"))
    parts.append(monitor_points(ctx.trim, style, ctx.density, machine_id))
    return combine(*(quiet(part) for part in parts))
