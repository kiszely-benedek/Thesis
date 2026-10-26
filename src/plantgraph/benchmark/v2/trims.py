"""Trims around pumps and compressors (design generator-v2-realism.md 6.1 to 6.6 and 6.16).

Rules, named as in the design's table of sources: L1 a check valve sits between pump and block
valve; L2 a pump's suction has a block valve and a strainer; L3 a local pressure gauge sits between
the pump nozzle and the check; L4 casings have a vent and a drain; L5 a positive-displacement (PD)
pump has an external relief valve from discharge back to suction (it would burst against a closed
valve otherwise); L6 a minimum-flow line returns liquid to the suction vessel so the pump never
runs dry; L16 compressors have suction and discharge valves, a suction strainer and a discharge
check. Flow order in every `run` is from source to target.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.benchmark.v2.class_decks import (
    COMPRESSOR_CHECK,
    COMPRESSOR_SUCTION_BLOCK,
    MIN_FLOW_CHECK,
    PD_RELIEF,
    PUMP_CHECK,
)
from plantgraph.benchmark.v2.config import PumpPressureMode
from plantgraph.benchmark.v2.plan_models import LineItemSpec, StreamKindV2
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine, main_line
from plantgraph.benchmark.v2.trims_extra import (
    capped_branch,
    flex_connector_items,
    flush_connection,
    orifice_flange_set_items,
    pressure_tap,
    removable_spool_items,
    tee_part,
)
from plantgraph.graph.schema import NodeClass

#: pumps that push a fixed volume per stroke; they need the relief path of 6.5
PD_PUMP_CLASSES = frozenset({NodeClass.RECIPROCATING_PUMP.value, NodeClass.ROTARY_PUMP.value})

SuctionTrim = Callable[[TrimContext, LineStyle, bool], TrimPlan]


def needs_external_relief(pump_class: str) -> bool:
    """True for a PD pump: its discharge must be able to relieve back to suction (L5)."""
    return pump_class in PD_PUMP_CLASSES


# ---- 6.1, 6.2 suction -------------------------------------------------------------------------


def centrifugal_suction(
    ctx: TrimContext, style: LineStyle, relief_return: bool = False
) -> TrimPlan:
    """6.1: block valve, a temporary conical strainer between two flanges, then the pump (L2).

    `relief_return` adds the `PipeTee` where a PD-style relief line would come back (port
    `relief_return_tee`).
    """
    draft = TrimDraft(ctx, style)
    strainer = draft.part(NodeClass.CONICAL_STRAINER.value, "suction_strainer")
    return _suction(draft, strainer, removable_spool_items(draft, strainer), relief_return)


def positive_displacement_suction(
    ctx: TrimContext, style: LineStyle, relief_return: bool = True
) -> TrimPlan:
    """6.2: as 6.1 but with a permanent `Strainer`, which needs no spool (L2)."""
    draft = TrimDraft(ctx, style)
    strainer = draft.part(NodeClass.STRAINER.value, "suction_strainer")
    return _suction(draft, strainer, (strainer,), relief_return)


def suction_for(pump_class: str) -> SuctionTrim:
    """The suction trim for a pump class: 6.1 for centrifugal, 6.2 for PD pumps."""
    if pump_class == NodeClass.CENTRIFUGAL_PUMP.value:
        return centrifugal_suction
    if needs_external_relief(pump_class):
        return positive_displacement_suction
    raise ValueError(f"expected a centrifugal, reciprocating or rotary pump, got {pump_class!r}")


def _suction(
    draft: TrimDraft,
    strainer: LineItemSpec,
    strainer_group: tuple[LineItemSpec, ...],
    relief_return: bool,
) -> TrimPlan:
    block = draft.dealt_part("block_valve", "suction_block")
    run = [block, *strainer_group]
    ports = {"block": block, "strainer": strainer}
    if relief_return:
        tee = tee_part(draft, "relief_return_tee")
        run.append(tee)
        ports["relief_return_tee"] = tee
    run.extend(flex_connector_items(draft))
    return draft.finish_with_ports(ports, tuple(run))


# ---- 6.3 discharge ----------------------------------------------------------------------------


def pump_discharge(
    ctx: TrimContext,
    style: LineStyle,
    pressure_gauge: bool,
    relief_tap: bool,
    min_flow_tap: bool,
) -> TrimPlan:
    """6.3: nozzle, [gauge tap], [relief tap], check valve, [min-flow tap], block valve (L1, L3).

    The gauge tap is a `PipeTee` whose branch ends in a root valve and a blind flange carrying a
    local `PI`; it comes before the check. The relief and min-flow taps are bare `PipeTee`s for
    6.5 and 6.6 (ports `relief_tee`, `min_flow_tee`); the min-flow tee is after the check.
    """
    draft = TrimDraft(ctx, style)
    run = list(flex_connector_items(draft))
    ports: dict[str, LineItemSpec | str] = {}
    if pressure_gauge:
        gauge_tee = tee_part(draft, "pressure_gauge_tee")
        run.append(gauge_tee)
        ports["pressure_gauge"] = pressure_tap(draft, gauge_tee.node_id, "discharge_pi")
    if relief_tap:
        ports["relief_tee"] = _append_tee(draft, run, "relief_tee")
    check = draft.part(PUMP_CHECK, "discharge_check")
    run.append(check)
    if min_flow_tap:
        ports["min_flow_tee"] = _append_tee(draft, run, "min_flow_tee")
    block = draft.dealt_part("block_valve", "discharge_block")
    run.append(block)
    return draft.finish_with_ports({"check": check, "block": block, **ports}, tuple(run))


def _append_tee(draft: TrimDraft, run: list[LineItemSpec], role: str) -> LineItemSpec:
    tee = tee_part(draft, role)
    run.append(tee)
    return tee


# ---- 6.4 vent and drain -----------------------------------------------------------------------


def pump_vent_drain(ctx: TrimContext, style: LineStyle, pump_id: str) -> TrimPlan:
    """6.4: a casing vent and a casing drain, each a valve and a cap (L4).

    Drawn with chance `p_pump_vent_drain`. One vent plus one drain per pump is the design's reading
    of "vent / drain" (arithmetic 13.7).
    """
    draft = TrimDraft(ctx, style)
    if not ctx.chance(ctx.config.p_pump_vent_drain):
        return draft.finish()
    vent = capped_branch(draft, pump_id, "vent", "pump_vent")
    drain = capped_branch(draft, pump_id, "drain", "pump_drain")
    return draft.finish(vent_valve=vent, drain_valve=drain)


# ---- 6.5 relief, 6.6 minimum flow -------------------------------------------------------------


def pd_pump_relief(
    ctx: TrimContext, style: LineStyle, discharge_tee_id: str, suction_tee_id: str
) -> TrimPlan:
    """6.5: a relief valve from the discharge tee, before the check, to the suction tee (L5)."""
    draft = TrimDraft(ctx, style)
    valve = draft.part(PD_RELIEF, "pd_relief_valve")
    draft.line(discharge_tee_id, [valve], suction_tee_id, style=style.branch())
    return draft.finish(relief_valve=valve)


def min_flow_bypass(
    ctx: TrimContext, style: LineStyle, discharge_tee_id: str, vessel_id: str
) -> TrimPlan:
    """6.6: orifice between flanges, check valve, gate valve, back to the suction vessel (L6).

    The line leaves the discharge after the check and before the block valve and is a recycle.
    """
    draft = TrimDraft(ctx, style)
    parts = list(orifice_flange_set_items(draft))
    parts.append(draft.part(MIN_FLOW_CHECK, "min_flow_check"))
    parts.append(draft.part(NodeClass.GATE_VALVE.value, "min_flow_block"))
    draft.line(discharge_tee_id, parts, vessel_id, StreamKindV2.RECYCLE, style.branch())
    return draft.finish()


# ---- the whole pump -----------------------------------------------------------------------------


def pump_trims(
    ctx: TrimContext,
    style: LineStyle,
    pump_id: str,
    pump_class: str,
    vessel_id: str,
    dst_id: str | None,
    pressure_mode: PumpPressureMode = "per_pump_pi",
    suction_head: tuple[LineItemSpec, ...] = (),
    suction_src_id: str | None = None,
    discharge_tail: tuple[LineItemSpec, ...] = (),
) -> TrimPlan:
    """Every trim of one pump, with its suction and discharge lines: vessel -> pump -> `dst_id`.

    Draws the optional parts (min-flow line, vent and drain, flush tap) in a fixed order so the
    result depends only on the unit's stream. A pump inside a spared set takes its line ends from
    the set: `suction_head` parts come first on the suction line, `suction_src_id` replaces the
    vessel as its source (a pump that branches off a header tee), and `discharge_tail` parts
    close the discharge line (the header's merge tees). The min-flow line still returns to
    `vessel_id`.
    """
    pd_pump = needs_external_relief(pump_class)
    min_flow = ctx.chance(ctx.config.p_min_flow)
    suction = suction_for(pump_class)(ctx, style, pd_pump)
    discharge = pump_discharge(ctx, style, pressure_mode == "per_pump_pi", pd_pump, min_flow)
    suction_run = (*suction_head, *suction.run)
    suction_line = main_line(ctx, style, suction_src_id or vessel_id, suction_run, pump_id)
    discharge_line = main_line(ctx, style, pump_id, (*discharge.run, *discharge_tail), dst_id)
    parts = [  # the two main lines come first: every branch below starts at one of their tees
        suction.with_main_line(suction_line).with_port_prefix("suction"),
        discharge.with_main_line(discharge_line).with_port_prefix("discharge"),
    ]
    if pd_pump:
        relief_taps = (discharge.ports["relief_tee"], suction.ports["relief_return_tee"])
        parts.append(pd_pump_relief(ctx, style, *relief_taps))
    if min_flow:
        parts.append(min_flow_bypass(ctx, style, discharge.ports["min_flow_tee"], vessel_id))
    parts.append(pump_vent_drain(ctx, style, pump_id))
    parts.append(flush_connection(ctx, style, pump_id))
    return combine(*parts)


# ---- 6.16 compressor --------------------------------------------------------------------------


def compressor_suction(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """6.16: a butterfly block valve, then a temporary strainer between two flanges (L16)."""
    draft = TrimDraft(ctx, style)
    block = draft.part(COMPRESSOR_SUCTION_BLOCK, "compressor_suction_block")
    strainer = draft.part(NodeClass.CONICAL_STRAINER.value, "suction_strainer")
    run = (block, *removable_spool_items(draft, strainer))
    return draft.finish(run=run, block=block, strainer=strainer)


def compressor_discharge(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """6.16: nozzle, tee with a safety valve to the flare, check valve, block valve (L16).

    The safety valve line is a flare (`FL`) line that ends open, as on a real sheet where the
    flare header is on another drawing.
    """
    draft = TrimDraft(ctx, style)
    tee = tee_part(draft, "discharge_psv_tee")
    check = draft.part(COMPRESSOR_CHECK, "compressor_discharge_check")
    block = draft.dealt_part("block_valve", "compressor_discharge_block")
    psv = draft.dealt_part("vessel_psv", "compressor_discharge_psv")
    draft.line(tee.node_id, [psv], None, style=style.branch(service="FL"))
    return draft.finish(run=(tee, check, block), check=check, block=block, psv=psv)
