"""Small trims shared by the others, and the trims the real samples added (pid-vocabulary 5.4).

A **flange** is the bolted joint between two pipe parts; fittings such as a strainer sit between a
pair of them so they can be unbolted and cleaned. A **blind flange** is a solid plate that caps an
open end. Most trims here are a few parts in a row: each function says which.

Functions named `*_items` return parts for the caller's run; the others return a `TrimPlan`.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.class_decks import ON_OFF_VALVE, PLUG_DRAIN, PURGE_METER_ROLE
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.graph.schema import NodeClass

#: An optional item in a trim is present at even odds (Rule V, pid-vocabulary 13.1).
P_OPTIONAL_ITEM = 0.5


# ---- groups of parts reused inside other trims ------------------------------------------------


def flex_connector_items(draft: TrimDraft) -> tuple[LineItemSpec, ...]:
    """A `Compensator` (a bellows that absorbs pipe movement) with chance `p_flex_connector`."""
    if not draft.ctx.chance(draft.ctx.config.p_flex_connector):
        return ()
    return (draft.part(NodeClass.COMPENSATOR.value, "flex_connector"),)


def removable_spool_items(draft: TrimDraft, strainer: LineItemSpec) -> tuple[LineItemSpec, ...]:
    """The strainer between two flanged connections, so the screen can be pulled and cleaned."""
    before = draft.part(NodeClass.FLANGED_CONNECTION.value, "spool_flange")
    after = draft.part(NodeClass.FLANGED_CONNECTION.value, "spool_flange")
    return (before, strainer, after)


def orifice_flange_set_items(draft: TrimDraft) -> tuple[LineItemSpec, ...]:
    """A `RestrictionOrifice` held between two flanges (DEXPI C03: every orifice is drawn so)."""
    return (
        draft.part(NodeClass.FLANGE.value, "orifice_flange"),
        draft.part(NodeClass.RESTRICTION_ORIFICE.value, "restriction_orifice"),
        draft.part(NodeClass.FLANGE.value, "orifice_flange"),
    )


def on_off_valve_part(draft: TrimDraft, role: str) -> LineItemSpec:
    """An on-off valve body tagged `XV-…` or `YV-…` after the train's convention."""
    letters = draft.ctx.conventions.on_off_valve_letters
    tag = draft.ctx.numbering.instrument_tag(letters)
    return draft.tagged_part(ON_OFF_VALVE, role, tag)


def tee_part(draft: TrimDraft, role: str) -> LineItemSpec:
    """A `PipeTee`: the junction where a branch leaves (or joins) the run."""
    return draft.part(NodeClass.PIPE_TEE.value, role)


def pressure_tap(draft: TrimDraft, tee_id: str, role: str) -> str:
    """A local pressure gauge on a branch: `tee -> root valve -> blind flange`, `PI` on the flange.

    The root valve (the valve that isolates the gauge) is a ball or needle valve. Returns the `PI`.
    """
    root = draft.dealt_part("pressure_tap_root", f"{role}_root")
    flange = draft.part(NodeClass.BLIND_FLANGE.value, f"{role}_flange")
    draft.line(tee_id, [root, flange], None, style=draft.style.branch())
    return draft.local_indicator("PI", flange.node_id, role)


def temperature_tap(draft: TrimDraft, tee_id: str, role: str) -> str:
    """A local thermometer on a branch: `tee -> blind flange`, `TI` on the flange (no root valve).

    Returns the `TI`.
    """
    flange = draft.part(NodeClass.BLIND_FLANGE.value, f"{role}_flange")
    draft.line(tee_id, [flange], None, style=draft.style.branch())
    return draft.local_indicator("TI", flange.node_id, role)


def capped_branch(
    draft: TrimDraft,
    src_id: str,
    kind: str,
    role: str,
    valve: LineItemSpec | None = None,
    valve_deck: str = "vent_drain_valve",
) -> LineItemSpec:
    """A vent or drain: `src -> valve -> cap`; returns the valve.

    The cap is a blind flange or, for an open drain (chance `p_open_drain`, drains only), a
    `Funnel`. The valve is `valve` when given, else the next card of `valve_deck`.
    """
    block = valve or draft.dealt_part(valve_deck, f"{role}_valve")
    is_open = kind == "drain" and draft.ctx.chance(draft.ctx.config.p_open_drain)
    cap_class = NodeClass.FUNNEL if is_open else NodeClass.BLIND_FLANGE
    cap = draft.part(cap_class.value, f"{role}_open_drain" if is_open else f"{role}_cap")
    draft.line(src_id, [block, cap], None, style=draft.style.branch())
    return block


# ---- trims added by the real samples ------------------------------------------------------------


def flush_connection(ctx: TrimContext, style: LineStyle, equipment_id: str) -> TrimPlan:
    """A purge or flushing tap: valve, [rotameter], quick-connect coupling, cap.

    Drawn with chance `p_flush_connection`, on vessels and pump casings.
    """
    draft = TrimDraft(ctx, style)
    if not ctx.chance(ctx.config.p_flush_connection):
        return draft.finish()
    parts = [draft.part(NodeClass.GATE_VALVE.value, "flush_valve")]
    if ctx.deal_class(PURGE_METER_ROLE) != "plain":  # the deck holds "plain" twice, the meter once
        tag = ctx.numbering.instrument_tag("FI")
        parts.append(
            draft.tagged_part(NodeClass.VARIABLE_AREA_FLOW_METER.value, "purge_meter", tag)
        )
    parts.append(draft.part(NodeClass.PIPE_COUPLING.value, "flush_coupling"))
    parts.append(draft.part(NodeClass.BLIND_FLANGE.value, "flush_cap"))
    draft.line(equipment_id, parts, None, style=style.branch())
    return draft.finish()


def skillet_blind(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """A skillet blind (a plate that isolates a reactor or furnace inlet), chance `p_skillet`.

    One deck card says whether it is drawn closed (`PipeFlangeSpade`) or open (`PipeFlangeSpacer`).
    """
    draft = TrimDraft(ctx, style)
    if not ctx.chance(ctx.config.p_skillet):
        return draft.finish()
    blind = draft.dealt_part("skillet", "skillet_blind")
    return draft.finish(run=(blind,), skillet=blind)


def spec_break(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """A `PropertyBreak` inline: the pipe spec changes here (spec-break flag on real sheets).

    It is untagged and nothing may be located on it (pyDEXPI cannot sense a break).
    """
    draft = TrimDraft(ctx, style)
    spec_change = draft.part(NodeClass.PROPERTY_BREAK.value, "spec_break")
    return draft.finish(run=(spec_change,), spec_break=spec_change)


def dosing_isolation(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """The isolation valve of a dosing line: gate, or a diaphragm-type `StraightwayValve`."""
    draft = TrimDraft(ctx, style)
    valve = draft.dealt_part("dosing_isolation", "dosing_isolation_valve")
    return draft.finish(run=(valve,), valve=valve)


def sight_glass(ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """A sight glass (a window on the pipe), plain or illuminated, inline."""
    draft = TrimDraft(ctx, style)
    glass = draft.dealt_part("sight_glass", "sight_glass")
    return draft.finish(run=(glass,), sight_glass=glass)


def tank_bottom_drain(
    ctx: TrimContext, style: LineStyle, tank_id: str, viscous: bool = False
) -> TrimPlan:
    """The valved drain on a tank bottom: gate or angle ball; angle plug for viscous service."""
    draft = TrimDraft(ctx, style)
    if viscous:
        plug = draft.part(PLUG_DRAIN, "tank_drain_valve")
        valve = capped_branch(draft, tank_id, "drain", "tank_drain", valve=plug)
    else:
        valve = capped_branch(draft, tank_id, "drain", "tank_drain", valve_deck="tank_bottom_drain")
    return draft.finish(valve=valve)


def header_pressure_tap(ctx: TrimContext, style: LineStyle, tee_id: str) -> TrimPlan:
    """A pump header's pressure transmitter `PT` and indicator `PI`, instead of a gauge per pump.

    The branch is `tee -> root valve -> blind flange`, the transmitter located on the flange.
    """
    draft = TrimDraft(ctx, style)
    root = draft.dealt_part("pressure_tap_root", "header_pressure_root")
    flange = draft.part(NodeClass.BLIND_FLANGE.value, "header_pressure_flange")
    draft.line(tee_id, [root, flange], None, style=style.branch())
    indicator_tag = ctx.numbering.instrument_tag("PI")
    transmitter_tag = "PT-" + indicator_tag.partition("-")[2]  # loop members share the number
    sensor = draft.sensor(transmitter_tag, indicator_tag, flange.node_id, "header_pressure_pt")
    draft.bubble(indicator_tag, sensor, "header_pressure_pi")
    return draft.finish(transmitter=sensor)
