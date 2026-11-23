"""The safety-device pass of the planner (v2.2, handbook on): API 14C checklist and TOG236.

Runs once, after the plant boundary is closed and before the networks, because a new relief valve
ends open on a flare line and the network pass ties it into the flare sub-header. It only *adds*:
switches with their alarms (`protection_switches.py`), a tee at the end of each compressor suction
line (the one existing line it lengthens) and safety valves (`protection_valves.py`). It draws
from no random stream, so no existing draw moves; the new parts take their numbers from the unit's
own counters, after everything the pattern numbered.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.v2.instruments import transmitter_with_bubble
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.protection_scope import compressors, furnaces, tank_fluids
from plantgraph.benchmark.v2.protection_switches import (
    FUEL_PRESSURE_TEE_ROLE,
    SUCTION_TEE_ROLE,
    Switch,
    switch_additions,
)
from plantgraph.benchmark.v2.protection_valves import PRIORITY, valve_additions
from plantgraph.benchmark.v2.sac_structure import facts_of_plan
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import tee_part

#: the valve additions in force; shortened by the measured stop (design 17.13 R8 point 3)
ENABLED_VALVE_ADDITIONS: tuple[str, ...] = PRIORITY
_SUCTION_BLOCK_ROLE = "compressor_suction_block"


def add_protection(
    instances: Sequence[PatternInstance], trims: Sequence[TrimContext], style: LineStyle
) -> list[PatternInstance]:
    """The instances with the checklist devices a unit is missing.

    `trims[i]` is the trim context unit `i` was built with: its numbering continues.
    """
    pairs = zip(instances, trims, strict=True)
    return [_protect(instance, trim, style) for instance, trim in pairs]


def _protect(instance: PatternInstance, trim: TrimContext, style: LineStyle) -> PatternInstance:
    plan = _with_fuel_tees(_with_suction_tees(instance.plan, trim, style), trim, style)
    facts = facts_of_plan(plan)
    fluids = tank_fluids(instance)
    switches = [_draw_switch(trim, style, s) for s in switch_additions(facts, fluids)]
    valves = valve_additions(trim, style, facts, fluids, ENABLED_VALVE_ADDITIONS)
    return instance.model_copy(update={"plan": combine(plan, *switches, *valves)})


def _draw_switch(ctx: TrimContext, style: LineStyle, switch: Switch) -> TrimPlan:
    drawn = transmitter_with_bubble(ctx, style, switch.location, switch.sensor, switch.alarm)
    return drawn.model_copy(update={"ports": {}})  # the loop's ports are not wired further


def _with_suction_tees(plan: TrimPlan, ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """The plan with a tee ending each compressor suction line (sensors and a PSV hang on it)."""
    machines = compressors(facts_of_plan(plan))
    if not machines:
        return plan
    draft = TrimDraft(ctx, style)
    lines = list(plan.lines)
    for machine in machines:
        index = _suction_line_index(plan, machine)
        tee = tee_part(draft, SUCTION_TEE_ROLE)
        lines[index] = lines[index].model_copy(update={"items": (*lines[index].items, tee)})
    return combine(plan.model_copy(update={"lines": tuple(lines)}), draft.finish())


def _suction_line_index(plan: TrimPlan, machine: str) -> int:
    for index, line in enumerate(plan.lines):
        roles = {plan.roles.get(item.node_id) for item in line.items}
        if line.dst_id == machine and _SUCTION_BLOCK_ROLE in roles:
            return index
    raise ValueError(f"expected a suction line with a block valve into {machine!r}, found none")


#: the parts that open a control-valve station in front of its body: the tee, block, drain, reducer
_STATION_ENTRY_ROLES = frozenset({"cv_tee_in", "cv_block_in", "cv_drain_tee", "cv_reducer"})
_FUEL_LINE_MARK = "fuel_gas_pressure_tee"


def _with_fuel_tees(plan: TrimPlan, ctx: TrimContext, style: LineStyle) -> TrimPlan:
    """The plan with a tee on each fuel line between the pressure valve and the temperature valve.

    API 14C A.6.3.3 (p.33) puts the fuel PSH after the last pressure regulator and before the fuel
    control valve; the tee goes in front of the temperature valve's station.
    """
    if not furnaces(facts_of_plan(plan)):
        return plan
    draft = TrimDraft(ctx, style)
    lines = list(plan.lines)
    for index, line in enumerate(lines):
        if any(plan.roles.get(i.node_id) == _FUEL_LINE_MARK for i in line.items):
            tee = tee_part(draft, FUEL_PRESSURE_TEE_ROLE)
            at = _temperature_station_start(plan, line)
            items = (*line.items[:at], tee, *line.items[at:])
            lines[index] = line.model_copy(update={"items": items})
    return combine(plan.model_copy(update={"lines": tuple(lines)}), draft.finish())


def _temperature_station_start(plan: TrimPlan, line: LineSpec) -> int:
    """Index of the first part of the temperature valve's station on a fuel line."""
    items = line.items
    body = next(i for i, item in enumerate(items) if (item.tag or "").startswith("TV"))
    start = body
    while start > 0 and plan.roles.get(items[start - 1].node_id) in _STATION_ENTRY_ROLES:
        start -= 1
    return start
