"""Plant-boundary closure (v2.2, handbook on): a stream leaving the plant gets a battery limit.

A **battery limit** is the edge of the modelled region: a block valve and a line blind (Toghraei
2019 p.34). The flowsheet joins ports unit by unit, so whether a process stream really leaves the
plant is known only after the last unit is wired. This pass therefore runs once, over every unit,
before sheets are assigned, and closes each process end still open: an out-port nobody took (flash
vapour, a column's products), a farm receipt or an additive fill with no source, and a process line
that simply stops (a vacuum pump discharge).

Relief outlets and fuel-gas bleeds are not process lines (stream kind TRIM) and are left to T7's
networks. A reactor `recycle_gas` in-port whose compressor was never joined (a plant cut between
the two, or a reactor core without one) becomes **make-up gas**: gas fed from outside the plant.

The pass draws from the unit's own per-rule handbook streams (`TrimContext.handbook_choice`), after
the unit's pattern has made all its draws, so no existing draw moves (design 17.4).
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Port, PortDirection, PortKind
from plantgraph.benchmark.v2.plan_models import LineSpec, StreamKindV2
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.trims_valves import BATTERY_LIMIT_ROLES, battery_limit

#: where a line may end with nothing behind it: a blind or cap, an open drain funnel, a vent to
#: the atmosphere (breather, ventilation device, silencer, flame arrestor), a rupture disc
END_FITTINGS = frozenset(
    {
        "BlindFlange",
        "LineBlind",
        "Funnel",
        "VentilationDevice",
        "BreatherValve",
        "Silencer",
        "FlameArrestor",
        "RuptureDisc",
    }
)

#: the roles of an unpaired reactor recycle line once it is make-up gas
_MAKEUP_ROLES = {
    "recycle_gas_block": "makeup_gas_block",
    "recycle_gas_check": "makeup_gas_check",
}


class _End(str, Enum):
    """Which end of a line is open: where the stream enters or where it leaves."""

    SOURCE = "source"
    SINK = "sink"


def close_plant_boundary(
    instances: Sequence[PatternInstance], trims: Sequence[TrimContext], style: LineStyle
) -> list[PatternInstance]:
    """The instances with every process end still open closed by a battery limit.

    `trims[i]` is the trim context unit `i` was built with: its numbering continues, so the new
    parts never reuse a tag, and its handbook streams draw the battery-limit arrangement.
    """
    joined = _joined_nodes(instances)
    return [
        _close_unit(instance, trim, style, joined)
        for instance, trim in zip(instances, trims, strict=True)
    ]


def _joined_nodes(instances: Sequence[PatternInstance]) -> frozenset[str]:
    """The port nodes the flowsheet joined to another unit, from either side of the join.

    A join is stored on one line only: an in-port line starts at the out-port's node (`src_id`), but
    a recycle compressor's line ends at the reactor's in-port node (`dst_id`, T9c).
    """
    joined: set[str] = set()
    for instance in instances:
        for port, line in _port_lines(instance):
            end = line.src_id if port.direction is PortDirection.IN else line.dst_id
            if end is not None:
                joined.add(end)
    return frozenset(joined)


def _port_lines(instance: PatternInstance) -> list[tuple[Port, LineSpec]]:
    by_number = {line.line_number: line for line in instance.plan.lines}
    return [(port, by_number[port.line_number]) for port in instance.ports]


# ---- one unit ----------------------------------------------------------------------------------


def _close_unit(
    instance: PatternInstance, trim: TrimContext, style: LineStyle, joined: frozenset[str]
) -> PatternInstance:
    makeup = _unpaired_recycle_lines(instance, joined)
    plan = _as_makeup_gas(instance.plan, makeup)
    out_ports = {p.line_number: p for p in instance.ports if p.direction is PortDirection.OUT}
    roles = dict(plan.roles)
    lines: list[LineSpec] = []
    for line in plan.lines:
        for end in _open_ends(line, plan, out_ports, joined):
            line, group_roles = _with_battery_limit(line, end, trim, style)
            roles.update(group_roles)
        lines.append(line)
    closed = plan.model_copy(update={"lines": tuple(lines), "roles": roles})
    ports = _refreshed_ports(instance.ports, lines, makeup)
    return instance.model_copy(update={"plan": closed, "ports": ports})


def _unpaired_recycle_lines(instance: PatternInstance, joined: frozenset[str]) -> frozenset[str]:
    """Numbers of the `recycle_gas` in-port lines no compressor feeds."""
    return frozenset(
        port.line_number
        for port, line in _port_lines(instance)
        if port.direction is PortDirection.IN
        and port.kind is PortKind.RECYCLE
        and line.src_id is None
        and port.node_id not in joined
    )


def _as_makeup_gas(plan: TrimPlan, numbers: frozenset[str]) -> TrimPlan:
    """The plan with those lines re-labelled as process gas fed from outside."""
    # rule PLT-STREAM-CLOSURE: reactor gas with no compressor is make-up gas (Toghraei 2019 p.24)
    if not numbers:
        return plan
    renamed = {
        item.node_id: _MAKEUP_ROLES[plan.roles[item.node_id]]
        for line in plan.lines
        if line.line_number in numbers
        for item in line.items
        if plan.roles.get(item.node_id) in _MAKEUP_ROLES
    }
    kinds = {n: StreamKindV2.PROCESS if n in numbers else k for n, k in plan.stream_kinds.items()}
    return plan.model_copy(update={"roles": {**plan.roles, **renamed}, "stream_kinds": kinds})


def _open_ends(
    line: LineSpec, plan: TrimPlan, out_ports: dict[str, Port], joined: frozenset[str]
) -> list[_End]:
    """The ends of a process line that leave the plant and carry no battery limit yet."""
    if plan.stream_kinds.get(line.line_number) is not StreamKindV2.PROCESS:
        return []
    ends = []
    if line.src_id is None:
        ends.append(_End.SOURCE)
    if line.dst_id is None and not _declared_end(line, out_ports, joined):
        ends.append(_End.SINK)
    return [end for end in ends if not _has_battery_limit(line, end, plan.roles)]


def _declared_end(line: LineSpec, out_ports: dict[str, Port], joined: frozenset[str]) -> bool:
    """True when an open sink needs no battery limit: it ends at a vent or a unit takes it."""
    if line.items[-1].node_class in END_FITTINGS:
        return True  # a vacuum pump's discharge silencer: vented to the atmosphere, not a crossing
    port = out_ports.get(line.line_number)
    return port is not None and port.node_id in joined


def _has_battery_limit(line: LineSpec, end: _End, roles: dict[str, str]) -> bool:
    """True when the end part or its neighbour is a battery-limit part (the blind may be inside)."""
    nearby = line.items[:2] if end is _End.SOURCE else line.items[-2:]
    return any(roles.get(item.node_id) in BATTERY_LIMIT_ROLES for item in nearby)


def _with_battery_limit(
    line: LineSpec, end: _End, trim: TrimContext, style: LineStyle
) -> tuple[LineSpec, dict[str, str]]:
    """The line with a battery-limit group at `end`, and the roles of its parts."""
    # rule TOG34-BL-ISOLATION: a boundary crossing gets battery-limit isolation (Toghraei 2019 p.34)
    group = battery_limit(trim, style, forced=True)
    items = (*group.run, *line.items) if end is _End.SOURCE else (*line.items, *group.run)
    return line.model_copy(update={"items": items}), group.roles


def _refreshed_ports(
    ports: tuple[Port, ...], lines: Sequence[LineSpec], makeup: frozenset[str]
) -> tuple[Port, ...]:
    """The ports with `node_id` at the (possibly new) open end and make-up gas marked as process."""
    by_number = {line.line_number: line for line in lines}
    refreshed = []
    for port in ports:
        items = by_number[port.line_number].items
        node = items[0] if port.direction is PortDirection.IN else items[-1]
        kind = PortKind.PROCESS if port.line_number in makeup else port.kind
        refreshed.append(port.model_copy(update={"node_id": node.node_id, "kind": kind}))
    return tuple(refreshed)
