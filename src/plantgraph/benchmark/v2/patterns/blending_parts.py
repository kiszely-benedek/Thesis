"""The lines and instruments of the blending unit U8, one function per part (see `blending.py`).

Blending mixes a main liquid with a small, metered stream of an additive. The additive comes from
a day tank through a **dosing pump** (a reciprocating pump that moves a small fixed volume per
stroke). Every function closes its main line first (`assembly.close_run`).
"""

from __future__ import annotations

from plantgraph.benchmark.v2.instrument_draft import parsed_tag_of, part_of
from plantgraph.benchmark.v2.instruments import analyser_point, ratio_control_loop
from plantgraph.benchmark.v2.instruments_extra import ratio_speed_loop
from plantgraph.benchmark.v2.patterns.assembly import (
    block_valve_plan,
    close_run,
    part_plan,
    quiet,
    run_of,
    tee_plan,
    thermometer_tap,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.machines import with_line_end
from plantgraph.benchmark.v2.patterns.pump_set import PumpSet
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import dosing_isolation
from plantgraph.benchmark.v2.trims_valves import battery_limit, control_valve
from plantgraph.graph.schema import NodeClass

MAIN_METER = NodeClass.ELECTROMAGNETIC_FLOW_METER.value  # base 7.2: the main stream
ADDITIVE_METER = NodeClass.MASS_FLOW_MEASURING_ELEMENT.value  # a Coriolis meter on the additive


def flow_meter(ctx: PatternContext, node_class: str, role: str) -> TrimPlan:
    """A flow element of a fixed class tagged `FE-n`, inline (the open `run`, port `element`)."""
    draft = TrimDraft(ctx.trim, ctx.style)
    tag = ctx.trim.numbering.instrument_tag("FE")
    element = draft.tagged_part(node_class, role, tag)
    return draft.finish(run=(element,), element=element)


def main_line(ctx: PatternContext, meter: TrimPlan, mixer_id: str) -> TrimPlan:
    """The main liquid in-port line: [battery limit], flow meter, to the mixer."""
    run = run_of(battery_limit(ctx.trim, ctx.style), meter)
    return close_run(ctx, run, None, mixer_id)


def additive_fill_line(ctx: PatternContext, tank_id: str) -> TrimPlan:
    """The additive in-port line: [battery limit] and a fill valve, into the day tank."""
    run = run_of(battery_limit(ctx.trim, ctx.style), block_valve_plan(ctx, "tank_fill_block"))
    return close_run(ctx, run, None, tank_id)


def dosing_header(
    ctx: PatternContext, wild_element_id: str, meter: TrimPlan, injection: str, speed_drive: bool
) -> TrimPlan:
    """The dosing pumps' discharge header, as an open `run`: meter, ratio valve, isolation, mixer.

    The ratio controller `FFIC` compares the main flow (`FFT`, the *wild* flow it only measures)
    with the additive flow (`FT`) and moves the additive valve. With a variable-speed drive
    there is no valve; the pumps' speed is the final element (`dosing_speed_loops`).
    """
    isolation = dosing_isolation(ctx.trim, ctx.style)
    inline = [part_plan(ctx, injection, "additive_inline_mixer")] if injection != "plain" else []
    if speed_drive:
        control = meter
    else:
        valve = control_valve(ctx.trim, ctx.style, "F")
        control = ratio_control_loop(ctx.trim, ctx.style, wild_element_id, meter, valve)
    return quiet(run_of(control, isolation, *inline))


def dosing_speed_loops(
    ctx: PatternContext, wild_element_id: str, meter: TrimPlan, pump_ids: tuple[str, ...]
) -> TrimPlan:
    """One ratio loop per dosing pump, each acting on its pump's drive (`FFT, FT -> FFIC -> AEF`).

    The first loop takes the additive meter's number, as the valve variant does; one controller
    drives one machine (S8), so every pump of the set has its own.
    """
    element = part_of(meter, "element")
    first = parsed_tag_of(element, ctx.unit_no).sequence
    loops = [
        ratio_speed_loop(
            ctx.trim,
            ctx.style,
            wild_element_id,
            element.node_id,
            pump_id,
            first if index == 0 else None,
        )
        for index, pump_id in enumerate(pump_ids)
    ]
    return combine(*(quiet(loop) for loop in loops))


def join_pumps_to_mixer(pumps: PumpSet, mixer_id: str) -> TrimPlan:
    """The pump set's plan with its discharge line ended at the mixer instead of open."""
    return with_line_end(pumps.plan, pumps.discharge.line_number, mixer_id)


def blend_line(
    ctx: PatternContext, mixer_id: str, destination_id: str | None, analyser: bool
) -> tuple[TrimPlan, str]:
    """Mixer to `destination_id` (a vessel) or, if None, to the open out-port.

    The line holds a thermometer tee and, with `analyser`, a tee for an analyser (it measures
    the blend's composition). Returns the plan and the id of the thermometer tee.
    """
    thermometer = tee_plan(ctx, "blend_thermometer_tee")
    probe = tee_plan(ctx, "blend_analyser_tee") if analyser else None
    tail = [] if destination_id else [battery_limit(ctx.trim, ctx.style)]
    run = run_of(thermometer, *([probe] if probe else []), *tail)
    main = close_run(ctx, run, mixer_id, destination_id)
    taps = [thermometer_tap(ctx, thermometer.ports["tee"], "blend_ti")]
    if probe is not None:
        taps.append(quiet(analyser_point(ctx.trim, ctx.style, probe.ports["tee"])))
    return combine(main, *taps), thermometer.ports["tee"]
