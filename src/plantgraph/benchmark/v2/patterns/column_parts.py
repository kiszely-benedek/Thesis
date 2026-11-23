"""The lines and instruments of the column system U1, one function per part (see `column.py`).

Every function takes the ids of the equipment it connects and returns a `TrimPlan`. A line may only
end at a tee that an earlier line already holds, so each function closes its main line first and
the caller combines the plans in the order it wants them written.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.hidden_state import RefluxClass
from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.instruments import (
    analyser_point,
    control_loop,
    differential_pressure,
    flow_control_loop,
    transmitter_with_bubble,
)
from plantgraph.benchmark.v2.instruments_extra import (
    monitor_points,
    point_level_alarm,
    temperature_points,
)
from plantgraph.benchmark.v2.patterns.assembly import (
    block_valve_plan,
    close_run,
    flow_indicator_plan,
    local_gauge,
    quiet,
    run_of,
    tee_plan,
    thermometer_line,
    thermometer_tap,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.pump_set import PumpSet, build_pump_set
from plantgraph.benchmark.v2.patterns.separation import liquid_outlet_header
from plantgraph.benchmark.v2.patterns.vacuum import build_vacuum
from plantgraph.benchmark.v2.trim_context import LineStyle
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import sight_glass
from plantgraph.benchmark.v2.trims_valves import battery_limit, control_valve, flow_element
from plantgraph.benchmark.v2.trims_vessel import vessel_trims
from plantgraph.graph.schema import NodeClass

_VAPOUR_SERVICE = "PG"  # process gas


def gas_style(ctx: PatternContext) -> LineStyle:
    """The style of the overhead vapour lines."""
    return ctx.style.model_copy(update={"service": _VAPOUR_SERVICE})


# ---- feed and overhead --------------------------------------------------------------------------


def feed_lines(
    ctx: PatternContext, column_id: str, preheater_id: str | None
) -> tuple[TrimPlan, str]:
    """The feed in-port line and, with a preheater, the line from it to the column.

    Returns the plan and the id of the feed thermometer tee (the in-port's line holds it).
    """
    tee = tee_plan(ctx, "feed_thermometer_tee")
    run = run_of(battery_limit(ctx.trim, ctx.style), tee)
    main = close_run(ctx, run, None, preheater_id or column_id)
    parts = [main, thermometer_tap(ctx, tee.ports["tee"], "feed_ti")]
    if preheater_id is not None:
        parts.append(thermometer_line(ctx, preheater_id, column_id, "preheater_outlet"))
    return quiet(combine(*parts)), tee.ports["tee"]


def overhead_lines(
    ctx: PatternContext, column_id: str, condenser_id: str, drum_id: str
) -> TrimPlan:
    """Column top (trims, differential-pressure tap) to the condenser, then on to the drum."""
    style = gas_style(ctx)
    top_trims = vessel_trims(ctx.trim, style, column_id, NodeClass.PROCESS_COLUMN.value)
    dp_tee = tee_plan(ctx, "column_dp_tee")
    top = close_run(ctx, run_of(top_trims, dp_tee), column_id, condenser_id, style=style)
    dp = differential_pressure(ctx.trim, style, dp_tee.ports["tee"])
    condensate = thermometer_line(ctx, condenser_id, drum_id, "condenser_outlet")
    return combine(top, quiet(dp), condensate)


def reboiler_lines(ctx: PatternContext, column_id: str, reboiler_id: str) -> TrimPlan:
    """Sump to reboiler, and the heated return to the column with a thermometer on it."""
    down = close_run(ctx, combine(), column_id, reboiler_id)
    return combine(down, thermometer_line(ctx, reboiler_id, column_id, "reboiler_return"))


class Vapour(BaseModel):
    """The drum's vapour line: its plan, the equipment of a vacuum system, the valve body."""

    model_config = ConfigDict(frozen=True)

    plan: TrimPlan
    equipment_ids: tuple[str, ...]
    valve_body_id: str  # the pressure control valve: the line that holds it is the vapour port's


def vapour_lines(ctx: PatternContext, vacuum_kind: str, column_id: str, drum_id: str) -> Vapour:
    """Drum top tee (drum trims hang on it), the column-pressure valve, then open end or vacuum."""
    style = gas_style(ctx)
    trims = vessel_trims(ctx.trim, style, drum_id, NodeClass.PRESSURE_VESSEL.value)
    valve = control_valve(ctx.trim, style, "P")
    body = part_of(valve, "body")
    loop = control_loop(ctx.trim, style, body, column_id)  # the pressure is the column's
    open_run = combine(quiet(trims), quiet(valve), quiet(loop))
    if vacuum_kind == "none":
        return Vapour(
            plan=close_run(ctx, open_run, drum_id, None, style=style),
            equipment_ids=(),
            valve_body_id=body.node_id,
        )
    vacuum = build_vacuum(ctx, vacuum_kind, drum_id, open_run, style)
    return Vapour(plan=vacuum.plan, equipment_ids=vacuum.equipment_ids, valve_body_id=body.node_id)


# ---- pump sets ----------------------------------------------------------------------------------


def reflux_set(
    ctx: PatternContext, drum_id: str, column_id: str, with_sight_glass: bool
) -> tuple[PumpSet, TrimPlan]:
    """Reflux pumps; their discharge splits into reflux (to the column) and distillate (out).

    Which of the two streams is flow-controlled and which holds the drum level follows the hidden
    reflux class (`_reflux_class`). By default the distillate leaves through the level valve (a
    flow cascade with `p_cascade`) and, with `p_optional_instrument`, an analyser tap. Returns the
    pump set (its `discharge` is the distillate port) and the plan of the branch lines, to be
    written after the pump set.
    """
    reflux_class = _reflux_class(ctx)
    split = tee_plan(ctx, "reflux_split_tee")
    analyser = tee_plan(ctx, "distillate_analyser_tee") if _optional(ctx) else None
    taps = [quiet(analyser)] if analyser is not None else []
    distillate = _distillate_header(ctx, drum_id, reflux_class)
    header = combine(quiet(split), *taps, distillate)
    pumps = build_pump_set(ctx, drum_id, "CentrifugalPump", "reflux_pump", header=header)
    branches = [
        _reflux_line(ctx, split.ports["tee"], column_id, with_sight_glass, drum_id, reflux_class)
    ]
    if analyser is not None:
        branches.append(quiet(analyser_point(ctx.trim, ctx.style, analyser.ports["tee"])))
    hidden = {column_id: reflux_class} if ctx.trim.handbook else {}
    return pumps, combine(*branches).model_copy(update={"reflux": hidden})


def _reflux_class(ctx: PatternContext) -> RefluxClass:
    """The column's hidden reflux class; v2.1 and knobs-off plants always draw the low class."""
    if not ctx.trim.handbook:
        return RefluxClass.LOW
    # rule TOG309-SPLIT-PAIRING: flow on the smaller stream, level on the other (Toghraei p.309)
    weights = ctx.trim.handbook_knobs.reflux_class_weights
    return ctx.trim.handbook_choice("reflux_class", weights)


def _distillate_header(ctx: PatternContext, drum_id: str, reflux_class: RefluxClass) -> TrimPlan:
    """The distillate's valve and battery limit: the drum level valve, or a flow loop (high reflux).

    With a low reflux ratio the distillate is the larger stream, so it takes the level valve; with a
    high ratio it is the smaller one and takes flow control.
    """
    if reflux_class is RefluxClass.LOW:
        return liquid_outlet_header(ctx, drum_id)
    ctx.chance(ctx.instruments.p_cascade)  # drawn and ignored: the unit's stream stays aligned
    element = flow_element(ctx.trim, ctx.style, "liquid")
    valve = control_valve(ctx.trim, ctx.style, "F", letdown=True)
    loop = flow_control_loop(ctx.trim, ctx.style, element, valve)
    return quiet(combine(quiet(loop), quiet(battery_limit(ctx.trim, ctx.style))))


def _reflux_line(
    ctx: PatternContext,
    split_id: str,
    column_id: str,
    with_sight_glass: bool,
    drum_id: str,
    reflux_class: RefluxClass,
) -> TrimPlan:
    """`FE, FT -> FIC -> FV` (low reflux) or `LT -> LIC -> LV` (high); optional sight glass."""
    if reflux_class is RefluxClass.LOW:
        element = flow_element(ctx.trim, ctx.style, "liquid")
        valve = control_valve(ctx.trim, ctx.style, "F")
        control = flow_control_loop(ctx.trim, ctx.style, element, valve)
    else:
        valve = control_valve(ctx.trim, ctx.style, "L")
        control = combine(valve, control_loop(ctx.trim, ctx.style, part_of(valve, "body"), drum_id))
    glass = [quiet(sight_glass(ctx.trim, ctx.style))] if with_sight_glass else []
    return quiet(close_run(ctx, combine(control, *glass), split_id, column_id))


def bottoms_set(ctx: PatternContext, column_id: str) -> PumpSet:
    """Bottoms pumps and the sump-level valve on their discharge (no cascade: not a listed slot)."""
    header = liquid_outlet_header(ctx, column_id, allow_cascade=False)
    return build_pump_set(ctx, column_id, "CentrifugalPump", "bottoms_pump", header=header)


def side_draw_lines(ctx: PatternContext, column_id: str) -> tuple[TrimPlan, str]:
    """A tray draw: block valve, metered flow, open end. Returns the plan and the meter's id."""
    flow = flow_indicator_plan(ctx)
    run = run_of(block_valve_plan(ctx, "side_draw_block"), flow)
    return close_run(ctx, run, column_id, None), flow.ports["element"]


# ---- instruments --------------------------------------------------------------------------------


def column_instruments(ctx: PatternContext, column_id: str) -> TrimPlan:
    """Tray temperatures, bottom pressure, sump level glass and the column's monitoring points."""
    parts = [
        temperature_points(ctx.trim, ctx.style, column_id, ctx.density.tray_temperature_points),
        local_gauge(ctx, "PI", column_id, "bottom_pi"),
        local_gauge(ctx, "LG", column_id, "sump_level_gauge"),
        monitor_points(ctx.trim, ctx.style, ctx.density, column_id),
    ]
    return combine(*(quiet(part) for part in parts))


def drum_instruments(ctx: PatternContext, drum_id: str) -> TrimPlan:
    """Level glass, optional high-level alarm and level switch, and the drum's monitoring points."""
    parts = [local_gauge(ctx, "LG", drum_id, "level_gauge")]
    if _optional(ctx):
        parts.append(transmitter_with_bubble(ctx.trim, ctx.style, drum_id, "LSHH", "LAHH"))
    if ctx.chance(ctx.density.p_point_level_switch):
        parts.append(point_level_alarm(ctx.trim, ctx.style, drum_id, "H"))
    parts.append(monitor_points(ctx.trim, ctx.style, ctx.density, drum_id))
    return combine(*(quiet(part) for part in parts))


def _optional(ctx: PatternContext) -> bool:
    return ctx.chance(ctx.density.p_optional_instrument)
