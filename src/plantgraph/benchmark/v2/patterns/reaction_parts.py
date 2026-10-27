"""The lines and instruments of the heater-reactor-separator U3, one function per part.

Process flow of U3 (see `reaction.py`): the feed is warmed by the reactor's hot effluent in a
**feed/effluent exchanger**, heated further in a **fired heater** (a furnace), reacts in the
reactor, gives its heat up in the exchanger, is cooled and splits into gas and liquid in the
separator. Every function closes its main line first (`assembly.close_run`); the caller combines
the plans in the order it wants them written.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.class_decks import COMPRESSOR_CHECK
from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.instruments import (
    control_loop,
    differential_pressure,
    flame_failure_trip,
    hand_switch,
    process_trip,
)
from plantgraph.benchmark.v2.instruments_extra import (
    monitor_points,
    multivariable_controller,
    temperature_points,
)
from plantgraph.benchmark.v2.patterns.assembly import (
    block_valve_plan,
    close_run,
    local_gauge,
    part_plan,
    quiet,
    run_of,
    tee_plan,
    thermometer_tap,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import skillet_blind, spec_break
from plantgraph.benchmark.v2.trims_valves import (
    battery_limit,
    control_valve,
    double_block_and_bleed,
    on_off_valve,
)
from plantgraph.benchmark.v2.trims_vessel import vessel_trims
from plantgraph.graph.schema import NodeClass

GAS_SERVICE = "PG"  # process gas
FUEL_GAS_SERVICE = "FG"
_RUPTURE_DISC = NodeClass.RUPTURE_DISC.value


class FeedSide(BaseModel):
    """The plans of the feed side and the tee where recycle gas joins the feed."""

    model_config = ConfigDict(frozen=True)

    plan: TrimPlan
    recycle_tee: str


def feed_side(ctx: PatternContext, exchanger_id: str, furnace_id: str, reactor_id: str) -> FeedSide:
    """Feed line to the exchanger, the exchanger's cold outlet to the furnace, and the bypass.

    The **bypass** is a line around the exchanger's feed side: its valve (`TT -> TIC -> TV`, the
    temperature read at the reactor inlet) decides how much feed skips the heat exchange.
    """
    recycle, thermometer, split = (
        tee_plan(ctx, role)
        for role in ("recycle_merge_tee", "feed_thermometer_tee", "bypass_split_tee")
    )
    merge, outlet = tee_plan(ctx, "bypass_merge_tee"), tee_plan(ctx, "exchanger_outlet_tee")
    feed_run = run_of(battery_limit(ctx.trim, ctx.style), recycle, thermometer, split)
    to_furnace = run_of(merge, outlet, skillet_blind(ctx.trim, ctx.style))
    mains = [
        close_run(ctx, feed_run, None, exchanger_id),
        close_run(ctx, to_furnace, exchanger_id, furnace_id),
    ]
    taps = [
        thermometer_tap(ctx, thermometer.ports["tee"], "feed_ti"),
        thermometer_tap(ctx, outlet.ports["tee"], "exchanger_cold_outlet_ti"),
    ]
    bypass = _bypass_line(ctx, split.ports["tee"], merge.ports["tee"], reactor_id)
    return FeedSide(plan=combine(*mains, *taps, bypass), recycle_tee=recycle.ports["tee"])


def _bypass_line(ctx: PatternContext, split_id: str, merge_id: str, reactor_id: str) -> TrimPlan:
    valve = control_valve(ctx.trim, ctx.style, "T")
    loop = control_loop(ctx.trim, ctx.style, part_of(valve, "body"), reactor_id)
    return quiet(close_run(ctx, combine(valve, loop), split_id, merge_id))


def recycle_gas_line(ctx: PatternContext, recycle_tee: str) -> TrimPlan:
    """The optional gas in-port: an open start, a block valve and a check valve, to the feed tee.

    The check valve stops feed flowing backwards out of the recycle line.
    """
    style = ctx.style.model_copy(update={"service": GAS_SERVICE})
    check = part_plan(ctx, COMPRESSOR_CHECK, "recycle_gas_check")
    run = run_of(block_valve_plan(ctx, "recycle_gas_block"), check)
    return close_run(ctx, run, None, recycle_tee, StreamKindV2.RECYCLE, style)


# ---- heater ----------------------------------------------------------------------------------


def heater_to_reactor(ctx: PatternContext, furnace_id: str, reactor_id: str) -> TrimPlan:
    """Furnace to reactor with the pressure-drop tap, and a local gauge on the heater outlet."""
    dp_tee = tee_plan(ctx, "reactor_dp_tee")
    run = run_of(skillet_blind(ctx.trim, ctx.style), dp_tee)
    main = close_run(ctx, run, furnace_id, reactor_id)
    dp = differential_pressure(ctx.trim, ctx.style, dp_tee.ports["tee"])
    return combine(main, quiet(dp), local_gauge(ctx, "PI", furnace_id, "heater_outlet_pi"))


def fuel_gas_line(ctx: PatternContext, furnace_id: str) -> TrimPlan:
    """The fuel-gas stub to the furnace, with its two control valves and its isolation.

    Order along the line: block, pressure valve (`PIC`), temperature valve (`TIC` on the heater
    outlet), then a **double block and bleed**: two on-off valves in series and a vent between
    them, so the furnace can be proven isolated. One valve has one driver, so the first block
    shuts on the flame-failure trip (`BE -> BSL`), the second and the bleed are hand-operated.
    """
    style = ctx.style.branch(service=FUEL_GAS_SERVICE)
    block = block_valve_plan(ctx, "fuel_gas_block")
    pressure = control_valve(ctx.trim, style, "P")
    pressure_loop = control_loop(ctx.trim, style, part_of(pressure, "body"), furnace_id)
    temperature = control_valve(ctx.trim, style, "T")
    temperature_loop = control_loop(ctx.trim, style, part_of(temperature, "body"), furnace_id)
    dbb = double_block_and_bleed(ctx.trim, style)
    drivers = [
        flame_failure_trip(ctx.trim, style, part_of(dbb, "first"), furnace_id),
        hand_switch(ctx.trim, style, part_of(dbb, "second")),
        hand_switch(ctx.trim, style, part_of(dbb, "bleed")),
    ]
    run = run_of(block, pressure, pressure_loop, temperature, temperature_loop, dbb, *drivers)
    return close_run(ctx, run, None, furnace_id, StreamKindV2.UTILITY_STUB, style)


# ---- reactor ---------------------------------------------------------------------------------


def reactor_to_exchanger(ctx: PatternContext, reactor_id: str, exchanger_id: str) -> TrimPlan:
    """The hot effluent line: reactor top (trims) to the exchanger's hot side.

    The reactor's trims include its safety valve; a rupture disc (a thin plate that bursts at a
    set pressure) on its own line to the flare backs it up.
    """
    top = vessel_trims(ctx.trim, ctx.style, reactor_id, NodeClass.PRESSURE_VESSEL.value)
    main = close_run(ctx, run_of(top), reactor_id, exchanger_id)
    return combine(main, _rupture_disc_line(ctx, reactor_id))


def _rupture_disc_line(ctx: PatternContext, reactor_id: str) -> TrimPlan:
    draft = TrimDraft(ctx.trim, ctx.style)
    disc = draft.part(_RUPTURE_DISC, "reactor_rupture_disc")
    draft.line(reactor_id, [disc], None, style=ctx.style.branch(service="FL"))
    return draft.finish(rupture_disc=disc)


def reactor_instruments(ctx: PatternContext, reactor_id: str) -> TrimPlan:
    """Bed temperatures, an optional multivariable controller, the monitoring points."""
    points = ctx.density.reactor_temperature_points
    parts = [temperature_points(ctx.trim, ctx.style, reactor_id, points)]
    if ctx.chance(ctx.density.p_multivariable):
        parts.append(multivariable_controller(ctx.trim, ctx.style, reactor_id))
    parts.append(monitor_points(ctx.trim, ctx.style, ctx.density, reactor_id))
    return combine(*(quiet(part) for part in parts))


# ---- cooler and separator --------------------------------------------------------------------


def exchanger_to_cooler(ctx: PatternContext, exchanger_id: str, cooler_id: str) -> TrimPlan:
    """The cooled-down effluent: exchanger hot outlet (thermometer) to the effluent cooler."""
    outlet = tee_plan(ctx, "exchanger_hot_outlet_tee")
    main = close_run(ctx, run_of(outlet), exchanger_id, cooler_id)
    return combine(main, thermometer_tap(ctx, outlet.ports["tee"], "exchanger_hot_outlet_ti"))


def cooler_to_separator(ctx: PatternContext, cooler_id: str, separator_id: str) -> TrimPlan:
    """Cooler outlet (thermometer), then the separator's inlet valve, shut by high pressure."""
    outlet = tee_plan(ctx, "cooler_outlet_tee")
    valve = on_off_valve(ctx.trim, ctx.style)
    trip = process_trip(ctx.trim, ctx.style, part_of(valve, "valve"), separator_id, "P", "HH")
    main = close_run(ctx, run_of(outlet, valve, trip), cooler_id, separator_id)
    return combine(main, thermometer_tap(ctx, outlet.ports["tee"], "cooler_outlet_ti"))


def separator_gas_outlet(
    ctx: PatternContext, separator_id: str, vessel_class: str
) -> tuple[TrimPlan, str]:
    """Separator top (trims), the pressure valve (`PT -> PIC -> PV`), then the gas out-port.

    Returns the plan and the valve body's id (the out-port's line holds it).
    """
    style = ctx.style.model_copy(update={"service": GAS_SERVICE})
    trims = vessel_trims(ctx.trim, style, separator_id, vessel_class)
    valve = control_valve(ctx.trim, style, "P")
    loop = control_loop(ctx.trim, style, part_of(valve, "body"), separator_id)
    plan = close_run(ctx, run_of(trims, valve, loop), separator_id, None, style=style)
    return plan, valve.ports["body"]


def letdown_header(ctx: PatternContext, level_valve: TrimPlan) -> TrimPlan:
    """The separator liquid's discharge header: level valve, **spec break**, block valve.

    The level valve drops the liquid's pressure, so the pipe after it is a lighter class: the
    `PropertyBreak` marks where the line number changes (rule L20). The block valve after it
    keeps the break from being the last part of the line.
    """
    after = block_valve_plan(ctx, "letdown_outlet_block")
    return quiet(run_of(level_valve, spec_break(ctx.trim, ctx.style), after))
