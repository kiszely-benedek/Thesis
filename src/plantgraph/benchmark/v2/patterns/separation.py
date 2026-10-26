"""U6, the flash / separation drum (design realism 7.2; pid-vocabulary 13.3).

A **flash drum** is a vessel where a feed that is part liquid, part vapour separates: the vapour
leaves at the top, the liquid at the bottom through a pump set. Two control loops keep it steady:
the drum pressure (`PIC`) moves the valve on the vapour outlet, the liquid level (`LIC`) moves the
valve on the pump discharge. The control schemes are common textbook practice, not taken from a
source (design 7: marked [U]). A high-level trip (`LSHH`) shuts an on-off valve on the feed so the
drum cannot fill and carry liquid into the vapour line.

Variant drawn here: the vessel class (deck `U6.vessel`). The pump set draws its own variants.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.instrument_draft import node_with_role, part_of
from plantgraph.benchmark.v2.instruments import (
    control_loop,
    flow_control_loop,
    process_trip,
    transmitter_with_bubble,
)
from plantgraph.benchmark.v2.instruments_extra import (
    cascade_master,
    monitor_points,
    point_level_alarm,
)
from plantgraph.benchmark.v2.patterns.assembly import (
    close_run,
    equipment_plan,
    line_between,
    line_containing,
    local_gauge,
    quiet,
    tee_plan,
    thermometer_tap,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    PortDirection,
    open_end_port,
)
from plantgraph.benchmark.v2.patterns.pump_set import build_pump_set
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims_valves import (
    battery_limit,
    control_valve,
    flow_element,
    on_off_valve,
)
from plantgraph.benchmark.v2.trims_vessel import vessel_trims

PATTERN_ID = "U6"
SYSTEM_CODE = "FLS"
_VESSEL_DECK = "U6.vessel"
_VAPOUR_SERVICE = "PG"  # process gas


def build_flash_drum(ctx: PatternContext) -> PatternInstance:
    """One flash drum with trims, loops and a liquid pump set; ports `feed`, `vapour`, `liquid`."""
    vessel_class = ctx.deal(_VESSEL_DECK)
    drum_plan = equipment_plan(ctx, vessel_class, "V", "flash_drum")
    drum = drum_plan.ports["equipment"]
    pumps = build_pump_set(
        ctx, drum, "CentrifugalPump", "liquid_pump", header=_liquid_outlet_header(ctx, drum)
    )
    feed = _feed_plan(ctx, drum)
    vapour = _vapour_plan(ctx, drum, vessel_class)
    plan = combine(drum_plan, feed, vapour, pumps.plan, _drum_instruments(ctx, drum))
    plan = with_stream_kinds(plan)
    groups = DrawingGroups()
    groups.put([drum], "G1")
    groups.put(pumps.pump_ids, "G2" if pumps.own_sheet else "G1", pinned=pumps.own_sheet)
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=f"{variant_label(vessel=vessel_class)}|{pumps.variant}",
        plan=plan,
        ports=(
            open_end_port("feed", PortDirection.IN, Phase.LIQUID, line_between(plan, None, drum)),
            open_end_port(
                "vapour",
                PortDirection.OUT,
                Phase.GAS,
                line_containing(plan, node_with_role(plan, "top_outlet_tee")),
            ),
            pumps.discharge.model_copy(update={"name": "liquid"}),
        ),
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _feed_plan(ctx: PatternContext, drum: str) -> TrimPlan:
    """Feed line: [battery limit], a thermometer tee, the trip valve, into the drum (an in-port).

    The thermometer is the "TI on the inlet" of the design; the `LT -> LSHH` trip shuts the valve.
    """
    inlet_tee = tee_plan(ctx, "inlet_thermometer_tee")
    trip_valve = on_off_valve(ctx.trim, ctx.style)
    run = combine(quiet(battery_limit(ctx.trim, ctx.style)), quiet(inlet_tee), quiet(trip_valve))
    main = close_run(ctx, run, None, drum)
    thermometer = thermometer_tap(ctx, inlet_tee.ports["tee"], "inlet_ti")
    trip = process_trip(ctx.trim, ctx.style, part_of(trip_valve, "valve"), drum, "L", "HH")
    return combine(main, thermometer, quiet(trip))


def _vapour_plan(ctx: PatternContext, drum: str, vessel_class: str) -> TrimPlan:
    """The vapour outlet: top tee (drum trims hang on it), pressure control valve, open end."""
    style = ctx.style.model_copy(update={"service": _VAPOUR_SERVICE})
    trims = vessel_trims(ctx.trim, style, drum, vessel_class)
    valve = control_valve(ctx.trim, style, "P")
    loop = control_loop(ctx.trim, style, part_of(valve, "body"), drum)
    return close_run(ctx, combine(quiet(trims), quiet(valve), quiet(loop)), drum, None, style=style)


def _liquid_outlet_header(ctx: PatternContext, drum: str) -> TrimPlan:
    """The valve that holds the drum level, on the pump discharge; a flow cascade with `p_cascade`.

    Cascade: the level controller sets the set point of a flow controller (level over flow).
    The body is a letdown valve (angle body: the liquid drops pressure across it).
    """
    style = ctx.style
    if ctx.chance(ctx.instruments.p_cascade):
        element = flow_element(ctx.trim, style, "liquid")
        valve = control_valve(ctx.trim, style, "F", letdown=True)
        loop = flow_control_loop(ctx.trim, style, element, valve)
        control = combine(loop, cascade_master(ctx.trim, style, loop, "L", drum))
    else:
        valve = control_valve(ctx.trim, style, "L", letdown=True)
        control = combine(valve, control_loop(ctx.trim, style, part_of(valve, "body"), drum))
    return quiet(combine(quiet(control), quiet(battery_limit(ctx.trim, style))))


def _drum_instruments(ctx: PatternContext, drum: str) -> TrimPlan:
    """Level gauge, optional low-low and point-level alarms, and the drum's monitoring points."""
    style = ctx.style
    parts = [local_gauge(ctx, "LG", drum, "level_gauge")]
    if ctx.chance(ctx.density.p_optional_instrument):
        parts.append(transmitter_with_bubble(ctx.trim, style, drum, "LSLL", "LALL"))
    if ctx.chance(ctx.density.p_point_level_switch):
        parts.append(point_level_alarm(ctx.trim, style, drum, "H"))
    parts.append(monitor_points(ctx.trim, style, ctx.density, drum))
    return combine(*(quiet(part) for part in parts))
