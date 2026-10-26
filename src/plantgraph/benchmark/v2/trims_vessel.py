"""Trims on vessels and tanks (design generator-v2-realism.md 6.10, 6.11, 6.12 and 6.19).

A **PSV** (pressure safety valve) opens when the vessel pressure is too high and vents the excess to
a **flare** (a safe burn-off stack); on a sheet its line just ends with a note, because the flare
header is drawn elsewhere. A **nozzle** is a flanged opening on a vessel wall. Rules: L10 a PSV may
have block valves that are locked open, and a drain between block and PSV; L11 it sits on the
vessel's top outlet or directly on it; L13 vessels have a drain, a vent, a local pressure gauge on
top and a local thermometer on the top outlet line.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.config import VentDrainConvention
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import (
    capped_branch,
    flush_connection,
    tee_part,
    temperature_tap,
)
from plantgraph.graph.schema import NodeClass

#: vessels that must have a safety device reachable from them (invariant S6)
PSV_VESSEL_CLASSES = frozenset(
    {
        NodeClass.PRESSURE_VESSEL.value,
        NodeClass.PROCESS_COLUMN.value,
        NodeClass.GRAVITATIONAL_SEPARATOR.value,
        NodeClass.SCRUBBING_SEPARATOR.value,
    }
)


def vessel_psv(ctx: TrimContext, style: LineStyle, vessel_id: str) -> TrimPlan:
    """6.10: `vessel -> [block] -> [drain tee] -> PSV -> [block] -> open end` on a flare line.

    Both blocks come together with chance `p_psv_blocks` (car-sealed open: locked so nobody
    shuts the safety path by mistake); the drain with `p_psv_drain`.
    """
    draft = TrimDraft(ctx, style)
    blocks = ctx.chance(ctx.config.p_psv_blocks)
    inlet = [draft.dealt_part("block_valve", "psv_inlet_block")] if blocks else []
    drain_tee = tee_part(draft, "psv_drain_tee") if ctx.chance(ctx.config.p_psv_drain) else None
    psv = draft.dealt_part("vessel_psv", "psv")
    outlet = [draft.dealt_part("block_valve", "psv_outlet_block")] if blocks else []
    parts = [*inlet, *([drain_tee] if drain_tee else []), psv, *outlet]
    draft.line(vessel_id, parts, None, style=style.branch(service="FL"))  # main line first
    if drain_tee is not None:
        capped_branch(draft, drain_tee.node_id, "drain", "psv_drain")
    return draft.finish(psv=psv)


def vessel_vent_drain(ctx: TrimContext, style: LineStyle, vessel_id: str) -> TrimPlan:
    """6.11: a drain on the bottom nozzle and a vent on the top one, each a valve and a cap (L13).

    The sources disagree. `klm_all`: both always. `hnf_closed`: each only with chance
    `p_hnf_vent_drain`, since the second source drains only to a closed system.
    """
    draft = TrimDraft(ctx, style)
    ports: dict[str, LineItemSpec] = {}
    for kind in ("drain", "vent"):
        if _is_drawn(ctx):
            ports[f"{kind}_valve"] = capped_branch(draft, vessel_id, kind, f"vessel_{kind}")
    return draft.finish_with_ports(ports)


def _is_drawn(ctx: TrimContext) -> bool:
    if ctx.config.vent_drain_convention is VentDrainConvention.KLM_ALL:
        return True
    return ctx.chance(ctx.config.p_hnf_vent_drain)


def vessel_top_instruments(ctx: TrimContext, style: LineStyle, vessel_id: str) -> TrimPlan:
    """6.12: a local `PI` on its own top nozzle, and a local `TI` on the top outlet line.

    The plan's `run` is the `PipeTee` the caller must put into the top outlet line (port
    `top_outlet_tee`); the thermometer hangs on a branch from it.
    """
    draft = TrimDraft(ctx, style)
    draft.local_indicator("PI", vessel_id, "vessel_top_pi")
    tee = tee_part(draft, "top_outlet_tee")
    temperature_tap(draft, tee.node_id, "vessel_top_ti")
    return draft.finish(run=(tee,), top_outlet_tee=tee)


def vessel_trims(ctx: TrimContext, style: LineStyle, vessel_id: str, vessel_class: str) -> TrimPlan:
    """Every trim of one vessel: PSV (where S6 asks for one), vent and drain, top gauges, flush tap.

    The result still has a `run` (the top outlet tee); close it with `with_main_line`.
    """
    parts = [
        vessel_vent_drain(ctx, style, vessel_id),
        vessel_top_instruments(ctx, style, vessel_id),
    ]
    if vessel_class in PSV_VESSEL_CLASSES:
        parts.insert(0, vessel_psv(ctx, style, vessel_id))
    parts.append(flush_connection(ctx, style, vessel_id))
    return combine(*parts)


def tank_vent(ctx: TrimContext, style: LineStyle, tank_id: str, flammable: bool) -> TrimPlan:
    """6.19: a roof vent that ends open: arrestor and breather valve, or a `VentilationDevice`.

    Flammable contents get the flame arrestor, then the breather valve. Otherwise a plain
    `VentilationDevice` (a screened opening) is enough. A **breather valve** lets a tank breathe
    within small pressure limits; a **flame arrestor** stops a flame travelling back into it.
    """
    draft = TrimDraft(ctx, style)
    if flammable:
        parts = [
            draft.part(NodeClass.FLAME_ARRESTOR.value, "tank_flame_arrestor"),
            draft.part(NodeClass.BREATHER_VALVE.value, "tank_breather_valve"),
        ]
    else:
        parts = [draft.part(NodeClass.VENTILATION_DEVICE.value, "tank_ventilation_device")]
    draft.line(tank_id, parts, None, style=style.branch(service="PG"))
    return draft.finish(vent_device=parts[-1])
