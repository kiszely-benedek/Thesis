"""The parts of the tank farm (U4): tank fittings, tank inlet chains, the transfer header.

Split from `storage.py` so each file stays short. Every function returns a `TrimPlan`; the ones that
make lines return them with the main line first (see `assembly.close_run`).
"""

from __future__ import annotations

from plantgraph.benchmark.v2.instrument_draft import parsed_tag_of, part_of
from plantgraph.benchmark.v2.instruments import (
    flow_control_loop,
    hand_switch,
    indicating_transmitter,
    process_trip,
    totaliser,
    transmitter_with_bubble,
)
from plantgraph.benchmark.v2.instruments_extra import (
    alarm_side,
    point_level_alarm,
    speed_control_loop,
)
from plantgraph.benchmark.v2.patterns.assembly import local_gauge, part_plan, quiet
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import tank_bottom_drain
from plantgraph.benchmark.v2.trims_valves import (
    battery_limit,
    control_valve,
    flow_element,
    on_off_valve,
)
from plantgraph.benchmark.v2.trims_vessel import tank_vent


def tank_fittings(ctx: PatternContext, tank_id: str, flammable: bool, viscous: bool) -> TrimPlan:
    """Roof vent, bottom drain and the tank's instruments.

    A flammable tank has a flame arrestor and breather valve, another a plain vent opening. The
    drain valve is an angle plug valve when the contents are viscous (a rotary-pump farm).
    """
    return combine(
        quiet(tank_vent(ctx.trim, ctx.style, tank_id, flammable)),
        quiet(tank_bottom_drain(ctx.trim, ctx.style, tank_id, viscous)),
        _tank_instruments(ctx, tank_id),
    )


def _tank_instruments(ctx: PatternContext, tank_id: str) -> TrimPlan:
    """`LT -> LI`, a local `TI`, an optional `LSLL` alarm and the point-level switches."""
    style = ctx.style
    parts = [
        indicating_transmitter(
            ctx.trim, style, tank_id, "L", alarm_side(ctx.trim, ctx.density, "H")
        ),
        local_gauge(ctx, "TI", tank_id, "tank_ti"),
    ]
    if ctx.chance(ctx.density.p_optional_instrument):
        parts.append(transmitter_with_bubble(ctx.trim, style, tank_id, "LSLL", "LALL"))
    for side in ("H", "L"):
        if ctx.chance(ctx.density.p_point_level_switch):
            parts.append(point_level_alarm(ctx.trim, style, tank_id, side))
    return combine(*(quiet(part) for part in parts))


def tank_inlet_chain(ctx: PatternContext, tank_id: str, manifold_class: str) -> TrimPlan:
    """The receipt valves of one tank as an open run: block valve, hand-switch valve, trip valve.

    Two on-off valves in series, because one valve has one driver: the first is opened and shut
    from the control room (`HS`), the second shuts on the overfill trip (`LT -> LSHH`).
    """
    block = part_plan(ctx, manifold_class, "tank_inlet_block")
    by_hand = on_off_valve(ctx.trim, ctx.style)
    by_trip = on_off_valve(ctx.trim, ctx.style)
    switch = hand_switch(ctx.trim, ctx.style, part_of(by_hand, "valve"))
    trip = process_trip(ctx.trim, ctx.style, part_of(by_trip, "valve"), tank_id, "L", "HH")
    return combine(*(quiet(plan) for plan in (block, by_hand, by_trip, switch, trip)))


def transfer_header(ctx: PatternContext, metering_class: str) -> TrimPlan:
    """The valves on the transfer pumps' discharge header, as an open run.

    A flow loop `FE, FT -> FIC -> FV`, then [a metering element with `FT -> FQI`, a totaliser
    that adds up the volume sent], then the unit's [battery limit].
    """
    element = flow_element(ctx.trim, ctx.style, "liquid")
    loop = flow_control_loop(ctx.trim, ctx.style, element, control_valve(ctx.trim, ctx.style, "F"))
    return _header_with(ctx, loop, metering_class)


def transfer_header_for_speed_drive(
    ctx: PatternContext, metering_class: str
) -> tuple[TrimPlan, LineItemSpec]:
    """The same header with no control valve: the flow element only, read by the pumps' loops.

    Returns the header and the flow element, which `transfer_speed_loops` needs.
    """
    element_plan = flow_element(ctx.trim, ctx.style, "liquid")
    return _header_with(ctx, quiet(element_plan), metering_class), part_of(element_plan, "element")


def transfer_speed_loops(
    ctx: PatternContext, element: LineItemSpec, pump_ids: tuple[str, ...]
) -> TrimPlan:
    """One flow loop `FT -> FIC -> AEF` per transfer pump, each setting its pump's speed.

    A positive-displacement pump's flow follows its speed; a valve in series would not change it
    (Toghraei 2019 p.314). One controller drives one machine (S8), so every pump has its own; the
    first takes the flow element's loop number.
    """
    first = parsed_tag_of(element, ctx.unit_no).sequence
    loops = [
        speed_control_loop(
            ctx.trim, ctx.style, pump_id, element.node_id, "F", first if index == 0 else None
        )
        for index, pump_id in enumerate(pump_ids)
    ]
    return combine(*(quiet(loop) for loop in loops))


def _header_with(ctx: PatternContext, control: TrimPlan, metering_class: str) -> TrimPlan:
    """`control`, then the optional metering element, then the battery limit, ports dropped."""
    parts = [control]
    if metering_class != "none":
        parts.append(_metering(ctx, metering_class))
    parts.append(battery_limit(ctx.trim, ctx.style))
    return combine(*(quiet(plan) for plan in parts))


def _metering(ctx: PatternContext, metering_class: str) -> TrimPlan:
    """A metering element tagged `FE-n` inline, with `FT-n` and a totaliser `FQI-n`."""
    draft = TrimDraft(ctx.trim, ctx.style)
    tag = ctx.trim.numbering.instrument_tag("FE")
    element = draft.tagged_part(metering_class, "metering_element", tag)
    meter = draft.finish(run=(element,))
    return combine(meter, quiet(totaliser(ctx.trim, ctx.style, element)))
