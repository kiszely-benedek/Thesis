"""Instruments every process vessel of the newer patterns (U2, U3, U8) carries.

One shared function so a drum, a separator and a blending vessel are instrumented alike.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.instruments import transmitter_with_bubble
from plantgraph.benchmark.v2.instruments_extra import monitor_points, point_level_alarm
from plantgraph.benchmark.v2.patterns.assembly import local_gauge, quiet
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine


def level_instruments(ctx: PatternContext, vessel_id: str, low_low: bool = False) -> TrimPlan:
    """Level gauge, [low-low level alarm], [high point-level switch] and the monitoring points.

    The low-low alarm (`LSLL -> LALL`, drawn with `p_optional_instrument`) is for vessels that
    feed a pump, which must not run dry; the switch follows `p_point_level_switch`.
    """
    parts = [local_gauge(ctx, "LG", vessel_id, "level_gauge")]
    if low_low and ctx.chance(ctx.density.p_optional_instrument):
        parts.append(transmitter_with_bubble(ctx.trim, ctx.style, vessel_id, "LSLL", "LALL"))
    if ctx.chance(ctx.density.p_point_level_switch):
        parts.append(point_level_alarm(ctx.trim, ctx.style, vessel_id, "H"))
    parts.append(monitor_points(ctx.trim, ctx.style, ctx.density, vessel_id))
    return combine(*(quiet(part) for part in parts))
