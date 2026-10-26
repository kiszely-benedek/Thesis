"""Trims on heat exchangers and their utility lines (design 6.13 to 6.15, pid-vocabulary 5.4).

A **utility** is a service stream the plant makes for everyone: cooling water (`CWS` supply,
`CWR` return), steam (`LPS` low pressure, `MPS` medium pressure) and the condensate (`CD`) that
steam leaves behind. A heat exchanger on a sheet shows only a short **stub** of each utility line:
it starts or ends at the sheet edge with a note naming the header (C4), so the stub has an open
end. A **steam trap** lets condensate out but holds steam back. Rules: L12 a cooler's cooling-water
return has a thermal relief valve (water trapped between closed valves would burst the pipe as it
warms); L15 steam-heated exchangers have a pressure gauge on the steam and the condensate lines.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.class_decks import CV_STATION_BYPASS
from plantgraph.benchmark.v2.config import CondensateMode
from plantgraph.benchmark.v2.plan_models import LineItemSpec, StreamKindV2
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.benchmark.v2.trims_extra import (
    P_OPTIONAL_ITEM,
    capped_branch,
    on_off_valve_part,
    pressure_tap,
    tee_part,
    temperature_tap,
)
from plantgraph.graph.schema import NodeClass

COOLING_WATER_SERVICES = frozenset({"CWS", "CWR"})
STEAM_SERVICES = frozenset({"LPS", "MPS"})
#: services whose pipe is hot to touch and so insulated for personnel protection or heat (`H`)
_HOT_SERVICES = frozenset({"LPS", "MPS", "CD"})


def _utility_style(style: LineStyle, service: str) -> LineStyle:
    insulation = "H" if service in _HOT_SERVICES else "N"
    return style.model_copy(update={"service": service, "insulation": insulation})


def _require(service: str, allowed: frozenset[str], what: str) -> None:
    if service not in allowed:
        raise ValueError(f"expected {what} in {sorted(allowed)}, got {service!r}")


# ---- 6.13 supply ------------------------------------------------------------------------------


def utility_supply_stub(
    ctx: TrimContext,
    style: LineStyle,
    service: str,
    exchanger_id: str,
    relief_tee: bool = False,
) -> TrimPlan:
    """6.13: `open start -> block valve -> [gauge tap] -> utility inlet nozzle` (C4).

    Cooling water gets a thermometer tap with even odds; steam always gets a pressure gauge (L15).
    `relief_tee` adds a `PipeTee` for an atmospheric steam relief (port `relief_tee`).
    """
    _require(service, COOLING_WATER_SERVICES | STEAM_SERVICES, "a supply service")
    stub_style = _utility_style(style, service)
    draft = TrimDraft(ctx, stub_style)
    block = draft.dealt_part("block_valve", "utility_supply_block")
    tap_tee = tee_part(draft, "supply_tap_tee") if _wants_supply_tap(ctx, service) else None
    relief = tee_part(draft, "steam_relief_tee") if relief_tee else None
    parts = [block, *[tee for tee in (tap_tee, relief) if tee is not None]]
    draft.line(None, parts, exchanger_id, StreamKindV2.UTILITY_STUB)
    if tap_tee is not None:
        _supply_gauge(draft, tap_tee, service)
    ports = {"block": block} | ({"relief_tee": relief} if relief is not None else {})
    return draft.finish_with_ports(ports)


def _wants_supply_tap(ctx: TrimContext, service: str) -> bool:
    return service in STEAM_SERVICES or ctx.chance(P_OPTIONAL_ITEM)


def _supply_gauge(draft: TrimDraft, tee: LineItemSpec, service: str) -> None:
    if service in STEAM_SERVICES:
        pressure_tap(draft, tee.node_id, "steam_supply_pi")
    else:
        temperature_tap(draft, tee.node_id, "supply_ti")


# ---- 6.14 return ------------------------------------------------------------------------------


def utility_return_stub(
    ctx: TrimContext, style: LineStyle, service: str, exchanger_id: str
) -> TrimPlan:
    """6.14: `utility outlet nozzle -> ... -> block valve -> open end`.

    `service` is the *supply* service: `CWS` gives a cooling-water return (`CWR`), `LPS` or `MPS`
    a condensate return (`CD`).
    """
    _require(service, COOLING_WATER_SERVICES | STEAM_SERVICES, "a supply service")
    if service in COOLING_WATER_SERVICES:
        return _cooling_water_return(ctx, _utility_style(style, "CWR"), exchanger_id)
    return _condensate_return(ctx, _utility_style(style, "CD"), exchanger_id)


def _cooling_water_return(ctx: TrimContext, style: LineStyle, exchanger_id: str) -> TrimPlan:
    """Outlet, [thermometer tap], [thermal relief], block valve, open end (L12)."""
    draft = TrimDraft(ctx, style)
    tap_tee = tee_part(draft, "return_tap_tee") if ctx.chance(P_OPTIONAL_ITEM) else None
    relief_tee = (
        tee_part(draft, "thermal_relief_tee") if ctx.chance(ctx.config.p_thermal_relief) else None
    )
    block = draft.dealt_part("block_valve", "utility_return_block")
    parts = [tee for tee in (tap_tee, relief_tee) if tee is not None] + [block]
    draft.line(exchanger_id, parts, None, StreamKindV2.UTILITY_STUB)
    if tap_tee is not None:
        temperature_tap(draft, tap_tee.node_id, "return_ti")
    if relief_tee is not None:
        relief = draft.dealt_part("vessel_psv", "thermal_relief_valve")
        draft.line(relief_tee.node_id, [relief], None, style=style.branch())
    return draft.finish(block=block)


def _condensate_return(ctx: TrimContext, style: LineStyle, exchanger_id: str) -> TrimPlan:
    """Outlet, pressure gauge tap (L15), then one of three ways to remove condensate."""
    draft = TrimDraft(ctx, style)
    gauge_tee = tee_part(draft, "condensate_gauge_tee")
    mode = _draw_condensate_mode(ctx)
    if mode == "drain_pot":
        _drain_pot(draft, exchanger_id, gauge_tee)
    else:
        _trap_run(draft, exchanger_id, gauge_tee, with_station=mode == "trap_station")
    pressure_tap(draft, gauge_tee.node_id, "condensate_pi")
    return draft.finish()


def _draw_condensate_mode(ctx: TrimContext) -> CondensateMode:
    weights = ctx.config.condensate_mode_weights
    modes = list(weights)
    return ctx.rng.choices(modes, weights=[weights[mode] for mode in modes])[0]


def _trap_run(
    draft: TrimDraft, exchanger_id: str, gauge_tee: LineItemSpec, with_station: bool
) -> None:
    """The `trap` mode is a steam trap then a block valve.

    The `trap_station` mode puts the trap between two blocks with a bypass valve around the lot,
    so the trap can be serviced while the line runs.
    """
    trap = draft.part(NodeClass.STEAM_TRAP.value, "condensate_trap")
    if not with_station:
        block = draft.dealt_part("block_valve", "condensate_block")
        draft.line(exchanger_id, [gauge_tee, trap, block], None, StreamKindV2.UTILITY_STUB)
        return
    tee_in = tee_part(draft, "trap_tee_in")
    block_in = draft.dealt_part("block_valve", "trap_block_in")
    block_out = draft.dealt_part("block_valve", "trap_block_out")
    tee_out = tee_part(draft, "trap_tee_out")
    parts = [gauge_tee, tee_in, block_in, trap, block_out, tee_out]
    draft.line(exchanger_id, parts, None, StreamKindV2.UTILITY_STUB)
    bypass = draft.part(CV_STATION_BYPASS, "trap_bypass_valve")
    draft.line(tee_in.node_id, [bypass], tee_out.node_id, style=draft.style.branch())


def _drain_pot(draft: TrimDraft, exchanger_id: str, gauge_tee: LineItemSpec) -> None:
    """Condensate collects in a small vessel (the **drain pot**), then leaves through a level valve.

    A trip valve follows (it shuts on high conductivity, i.e. a tube leak). The level and
    conductivity instruments belong to the instrument templates, which find the valves by role.
    """
    pot = draft.equipment(NodeClass.PRESSURE_VESSEL.value, "V", "condensate_drain_pot")
    inlet_block = draft.dealt_part("block_valve", "pot_inlet_block")
    draft.line(exchanger_id, [gauge_tee, inlet_block], pot.node_id, StreamKindV2.UTILITY_STUB)
    level_class = draft.ctx.deal_class("control_valve_body")
    level_tag = draft.ctx.numbering.instrument_tag("LV")
    level_valve = draft.tagged_part(level_class, "pot_level_valve", level_tag)
    trip_valve = on_off_valve_part(draft, "pot_trip_valve")
    outlet_block = draft.dealt_part("block_valve", "pot_outlet_block")
    draft.line(
        pot.node_id, [level_valve, trip_valve, outlet_block], None, StreamKindV2.UTILITY_STUB
    )


# ---- 6.15 vents and drains --------------------------------------------------------------------


def exchanger_vent_drain(ctx: TrimContext, style: LineStyle, exchanger_id: str) -> TrimPlan:
    """6.15: a shell drain and a channel vent, each a valve and a cap (L15).

    The pair is drawn together, with chance `p_exchanger_vent_drain`.
    """
    draft = TrimDraft(ctx, style)
    if not ctx.chance(ctx.config.p_exchanger_vent_drain):
        return draft.finish()
    drain = capped_branch(draft, exchanger_id, "drain", "shell_drain")
    vent = capped_branch(draft, exchanger_id, "vent", "channel_vent")
    return draft.finish(drain_valve=drain, vent_valve=vent)


# ---- small steam trims ------------------------------------------------------------------------


def steam_stub_relief(ctx: TrimContext, style: LineStyle, tee_id: str) -> TrimPlan:
    """A PSV on a steam supply stub that discharges to the atmosphere (open end)."""
    draft = TrimDraft(ctx, _utility_style(style, "LPS"))
    valve = draft.dealt_part("vessel_psv", "steam_stub_psv")
    draft.line(tee_id, [valve], None, style=draft.style.branch())
    return draft.finish(psv=valve)


def ejector_discharge_silencer(ctx: TrimContext, style: LineStyle, ejector_id: str) -> TrimPlan:
    """An ejector's exhaust passes a `Silencer` and ends open to the atmosphere."""
    draft = TrimDraft(ctx, style)
    silencer = draft.part(NodeClass.SILENCER.value, "ejector_silencer")
    draft.line(ejector_id, [silencer], None, style=style.branch(service="PG"))
    return draft.finish(silencer=silencer)
