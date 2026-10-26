"""Trims on a line: control-valve stations, on-off valves, battery limits, flow elements.

A **control valve** (CV) throttles flow under a controller's command. A **station** wraps it in
isolation: block valves either side so it can be removed, and a bypass so the line can run by hand
meanwhile (L9). An **on-off valve** (XV) is fully open or fully shut, usually by a trip. A **battery
limit** is where a unit meets the rest of the plant: a block valve and a line blind (a plate that
can be swung into the pipe) let the unit be cut off.

Loop-numbered parts (the CV body, the XV, the flow element) are numbered here from the unit's
shared counter, so the loop's other members (transmitter, controller) take the same number later.
"""

from __future__ import annotations

from typing import Literal

from plantgraph.benchmark.v2.class_decks import CV_STATION_BYPASS
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.tags import format_instrument_tag, parse_tag
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.benchmark.v2.trims_extra import capped_branch, on_off_valve_part, tee_part
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind
from plantgraph.graph.schema import NodeClass

# ---- 6.7 control-valve station, 6.8 bare control valve ----------------------------------------


def control_valve(
    ctx: TrimContext, style: LineStyle, variable: str, letdown: bool = False
) -> TrimPlan:
    """A station with chance `p_cv_station`, else a bare control valve (6.7, 6.8).

    `variable` is the first ISA letter of the loop (`F`, `P`, `L`, `T`); the body is tagged
    `<variable>V-…`. `letdown` picks the angle-body deck used where a drum or separator's liquid
    outlet drops pressure (pid-vocabulary 13.4).
    """
    if ctx.chance(ctx.config.p_cv_station):
        return control_valve_station(ctx, style, variable, letdown)
    return bare_control_valve(ctx, style, variable, letdown)


def bare_control_valve(
    ctx: TrimContext, style: LineStyle, variable: str, letdown: bool = False
) -> TrimPlan:
    """6.8: the control valve body inline with no blocks (L9 says "in general", not always)."""
    draft = TrimDraft(ctx, style)
    body = _body(draft, variable, letdown)
    return draft.finish(run=(body,), body=body)


def control_valve_station(
    ctx: TrimContext, style: LineStyle, variable: str, letdown: bool = False
) -> TrimPlan:
    """6.7: `tee, block, [drain tee], [reducer], body, [reducer], block, tee` and a bypass (L9).

    The bypass is a branch from the first tee to the second one. The two reducers come as a pair
    (the valve is a size smaller than the line), chance `p_cv_reducers`; the drain between the
    upstream block and the body has chance `p_cv_drain`.
    """
    draft = TrimDraft(ctx, style)
    tee_in = tee_part(draft, "cv_tee_in")
    block_in = draft.dealt_part("block_valve", "cv_block_in")
    drain_tee = tee_part(draft, "cv_drain_tee") if ctx.chance(ctx.config.p_cv_drain) else None
    reducers = ctx.chance(ctx.config.p_cv_reducers)
    body = _body(draft, variable, letdown)
    block_out = draft.dealt_part("block_valve", "cv_block_out")
    tee_out = tee_part(draft, "cv_tee_out")

    run = [tee_in, block_in]
    run += [drain_tee] if drain_tee is not None else []
    run += _reducer_pair(draft, body, reducers)
    run += [block_out, tee_out]
    bypass = draft.part(CV_STATION_BYPASS, "cv_bypass_valve")
    draft.line(tee_in.node_id, [bypass], tee_out.node_id, style=style.branch())
    if drain_tee is not None:
        capped_branch(draft, drain_tee.node_id, "drain", "cv_drain")
    return draft.finish(
        run=tuple(run),
        body=body,
        tee_in=tee_in,
        tee_out=tee_out,
        block_in=block_in,
        block_out=block_out,
        bypass_valve=bypass,
    )


def _body(draft: TrimDraft, variable: str, letdown: bool) -> LineItemSpec:
    """The valve body, tagged `<variable>V-n` and checked to be a control valve."""
    deck = "letdown_control_valve_body" if letdown else "control_valve_body"
    body_class = draft.ctx.deal_class(deck)
    tag = draft.ctx.numbering.instrument_tag(f"{variable}V")
    parsed = parse_tag(tag)
    if parsed is None or item_kind(body_class, parsed.letters) is not ItemKind.CONTROL_VALVE:
        raise ValueError(
            f"expected a control-valve tag such as FV-12014 for {body_class}, got {tag!r}"
        )
    return draft.tagged_part(body_class, "control_valve_body", tag)


def _reducer_pair(draft: TrimDraft, body: LineItemSpec, reducers: bool) -> list[LineItemSpec]:
    """The body, with a reducer on each side when `reducers`."""
    if not reducers:
        return [body]
    narrow = draft.part(NodeClass.PIPE_REDUCER.value, "cv_reducer")
    widen = draft.part(NodeClass.PIPE_REDUCER.value, "cv_reducer")
    return [narrow, body, widen]


# ---- 6.9 on-off valve -------------------------------------------------------------------------


def on_off_valve(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """6.9: a ball valve tagged `XV-…` or `YV-…` (the train's letter), with limit switches.

    The limit switches `ZSO` (open) and `ZSC` (closed) are sensors on the valve, chance
    `p_limit_switches` for the pair, and share the valve's number. The valve's actuator and the
    trip or hand switch that drives it belong to the instrument templates.
    """
    draft = TrimDraft(ctx, style)
    valve = on_off_valve_part(draft, "on_off_valve")
    if ctx.chance(ctx.config.p_limit_switches):
        _add_limit_switches(draft, valve)
    return draft.finish(run=(valve,), valve=valve)


def _add_limit_switches(draft: TrimDraft, valve: LineItemSpec) -> None:
    parsed = parse_tag(valve.tag or "")
    if parsed is None:
        raise ValueError(f"expected a tagged on-off valve, got tag {valve.tag!r}")
    for letters, role in (("ZSO", "limit_switch_open"), ("ZSC", "limit_switch_closed")):
        tag = format_instrument_tag(letters, parsed.unit, parsed.sequence)
        draft.sensor(tag, tag, valve.node_id, role)


# ---- 6.17 battery limit, 6.18 flow measurement, double block and bleed --------------------------


def battery_limit(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """6.17: a block valve then a line blind at a unit's first inlet or last outlet.

    Drawn with chance `p_battery_limit`; the planner calls it once per unit end.
    """
    draft = TrimDraft(ctx, style)
    if not ctx.chance(ctx.config.p_battery_limit):
        return draft.finish()
    block = draft.dealt_part("block_valve", "battery_limit_block")
    blind = draft.part(NodeClass.LINE_BLIND.value, "battery_limit_blind")
    return draft.finish(run=(block, blind), block=block, blind=blind)


def flow_element(ctx: TrimContext, style: LineStyle, service: Literal["liquid", "gas"]) -> TrimPlan:
    """6.18: a flow element inline, tagged `FE-n`; liquid and gas services deal different decks.

    The transmitter `FT-n` that reads it is added by the loop template.
    """
    draft = TrimDraft(ctx, style)
    element_class = ctx.deal_class(f"flow_element_{service}")
    tag = ctx.numbering.instrument_tag("FE")
    element = draft.tagged_part(element_class, "flow_element", tag)
    return draft.finish(run=(element,), element=element)


def double_block_and_bleed(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """Fuel-gas isolation: on-off valve, tee, on-off valve, and a bleed valve on the tee's branch.

    Closing both blocks and opening the bleed proves the furnace is isolated. The bleed line
    ends open (a vent to a safe place).
    """
    draft = TrimDraft(ctx, style)
    first = on_off_valve_part(draft, "dbb_block_first")
    tee = tee_part(draft, "dbb_tee")
    second = on_off_valve_part(draft, "dbb_block_second")
    bleed = on_off_valve_part(draft, "dbb_bleed_valve")
    draft.line(tee.node_id, [bleed], None, style=style.branch())
    return draft.finish(run=(first, tee, second), first=first, second=second, bleed=bleed)
