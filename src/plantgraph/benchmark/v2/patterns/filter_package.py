"""U7, the filter package (design realism 7.2; pid-vocabulary 13.6 rule 3).

A **filter package** is two identical filters in parallel on a liquid line: one runs while the other
is cleaned or stands by, and valves on each filter's inlet and outlet switch between them. The
pressure drop across a filter (`PDT`/`PDI`) tells the operator when the running one is clogged. No
control loop is drawn by default; a flow controller on the outlet has chance
`p_optional_instrument`.

The package is its own unit and its own drawing group, and it never joins another unit's group
(pid-vocabulary 13.6 rule 3: one unit per sheet). There is no variant deck; the choices drawn are
whether the pressure drop is read across each filter or once across the pair, and the flow loop.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.instruments import differential_pressure, flow_control_loop
from plantgraph.benchmark.v2.patterns.assembly import (
    close_run,
    line_between,
    line_containing,
    part_plan,
    pressure_gauge_tap,
    quiet,
    spared_set,
    tee_plan,
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
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import P_OPTIONAL_ITEM
from plantgraph.benchmark.v2.trims_valves import battery_limit, control_valve, flow_element
from plantgraph.benchmark.v2.trims_vessel import vessel_vent_drain
from plantgraph.graph.schema import NodeClass

PATTERN_ID = "U7"
SYSTEM_CODE = "FIL"
_FILTER_TYPE_CODE = "F"
_FILTER_COUNT = 2  # A and B: one running, one spare


def build_filter_package(ctx: PatternContext) -> PatternInstance:
    """Two filters in parallel with their valves and gauges; ports `feed` and `filtered`."""
    filters = spared_set(ctx, NodeClass.LIQUID_FILTER.value, _FILTER_TYPE_CODE, _FILTER_COUNT)
    fa, fb = (item.node_id for item in filters)
    per_filter = ctx.chance(P_OPTIONAL_ITEM)  # pressure drop across each filter, or the pair
    flow_loop = ctx.chance(ctx.density.p_optional_instrument)
    inlet_gauge, split, merge, outlet_gauge = (
        tee_plan(ctx, role)
        for role in ("inlet_gauge_tee", "filter_split_tee", "filter_merge_tee", "outlet_gauge_tee")
    )
    dp_tees = [tee_plan(ctx, "filter_dp_tee") for _ in range(2 if per_filter else 1)]
    lines = combine(
        _inlet_main(ctx, fa, inlet_gauge, split, dp_tees, per_filter),
        _outlet_main(ctx, fa, merge, outlet_gauge, flow_loop),
        close_run(
            ctx, _run(_valve(ctx, "filter_inlet_block"), *(dp_tees[1:])), split.ports["tee"], fb
        ),
        close_run(ctx, _run(_valve(ctx, "filter_outlet_block")), fb, merge.ports["tee"]),
    )
    taps = [pressure_gauge_tap(ctx, inlet_gauge.ports["tee"], "inlet_pi")]
    taps.append(pressure_gauge_tap(ctx, outlet_gauge.ports["tee"], "outlet_pi"))
    taps += [differential_pressure(ctx.trim, ctx.style, tee.ports["tee"]) for tee in dp_tees]
    drains = [vessel_vent_drain(ctx.trim, ctx.style, filter_id) for filter_id in (fa, fb)]
    equipment = TrimPlan(equipment=tuple(filters), roles={fa: "filter", fb: "filter"})
    plan = combine(equipment, lines, *(quiet(part) for part in [*taps, *drains]))
    plan = with_stream_kinds(plan)
    groups = DrawingGroups()
    groups.put([fa, fb], "G1")
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=variant_label(dp="per_filter" if per_filter else "pair", flow_loop=flow_loop),
        plan=plan,
        ports=(
            open_end_port("feed", PortDirection.IN, Phase.LIQUID, line_between(plan, None, fa)),
            open_end_port(
                "filtered",
                PortDirection.OUT,
                Phase.LIQUID,
                line_containing(plan, merge.ports["tee"]),
            ),
        ),
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _run(*plans: TrimPlan) -> TrimPlan:
    """The plans joined in flow order, ports dropped: their parts form one line's run."""
    return combine(*(quiet(plan) for plan in plans))


def _valve(ctx: PatternContext, role: str) -> TrimPlan:
    """A block valve, gate or butterfly after the deck, as an open run."""
    return part_plan(ctx, ctx.trim.deal_class("block_valve"), role)


def _inlet_main(
    ctx: PatternContext,
    filter_a: str,
    gauge: TrimPlan,
    split: TrimPlan,
    dp_tees: list[TrimPlan],
    per_filter: bool,
) -> TrimPlan:
    """Feed line (an in-port): [battery limit], gauge tee, [pair DP tee], split tee, valve, A."""
    before_split = [] if per_filter else dp_tees
    after_valve = dp_tees[:1] if per_filter else []
    run = _run(
        battery_limit(ctx.trim, ctx.style),
        gauge,
        *before_split,
        split,
        _valve(ctx, "filter_inlet_block"),
        *after_valve,
    )
    return close_run(ctx, run, None, filter_a)


def _outlet_main(
    ctx: PatternContext, filter_a: str, merge: TrimPlan, gauge: TrimPlan, flow_loop: bool
) -> TrimPlan:
    """Outlet line (an out-port): valve, merge tee, gauge tee, [flow loop], [battery limit]."""
    control = _flow_loop(ctx) if flow_loop else combine()
    parts = [_valve(ctx, "filter_outlet_block"), merge, gauge, control]
    run = combine(*(quiet(plan) for plan in parts), quiet(battery_limit(ctx.trim, ctx.style)))
    return close_run(ctx, run, filter_a, None)


def _flow_loop(ctx: PatternContext) -> TrimPlan:
    """`FE, FT -> FIC -> FV`: the optional flow controller on the outlet."""
    element = flow_element(ctx.trim, ctx.style, "liquid")
    return flow_control_loop(ctx.trim, ctx.style, element, control_valve(ctx.trim, ctx.style, "F"))
