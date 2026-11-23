"""Gives every valve of a v2.2 plan its normal position and its actuator's fail action (design 8).

A valve's **normal position** (open, closed, car-sealed open) says how it stands during ordinary
operation; a **fail action** says what an automatic valve does when its air or signal is lost
(fail open, fail closed, fail in last position). Both are properties of the *design*, not of the
drawing's topology, so they are drawn into the DEXPI file and the hidden plan but never reach the
graph the system reads (decision D1 = A, design 10).

Nothing here is random. The role of a valve decides its position (`valve_roles.py`) and its
service decides its fail action through the declared `HandbookKnobs.fail_action_table`, so no
random stream is consumed and no existing draw can shift.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from plantgraph.benchmark.v2.config_v22 import FailAction, HandbookKnobs
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import (
    InstrumentSpec,
    LineItemSpec,
    LineSpec,
    OperatingPosition,
    StreamKindV2,
)
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.valve_roles import (
    fail_action_service,
    is_positioned_role,
    operating_position_of,
)
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind
from plantgraph.graph.schema import CLASS_SPECS, NodeClass, Relation

_AUTOMATIC_KINDS = (ItemKind.CONTROL_VALVE, ItemKind.ON_OFF_VALVE)
_ACTUATOR = NodeClass.ACTUATING_FUNCTION.value


def with_valve_positions(instance: PatternInstance, knobs: HandbookKnobs) -> PatternInstance:
    """The instance with every valve positioned and every valve actuator given a fail action."""
    plan = instance.plan
    lines = tuple(_positioned_line(line, plan.roles) for line in plan.lines)
    positioned = plan.model_copy(update={"lines": lines})
    instruments = _actuators_with_fail_action(positioned, knobs.fail_action_table)
    return instance.model_copy(
        update={"plan": positioned.model_copy(update={"instruments": instruments})}
    )


# ---- normal positions ---------------------------------------------------------------------------


def _positioned_line(line: LineSpec, roles: Mapping[str, str]) -> LineSpec:
    items = tuple(_positioned_item(item, roles[item.node_id]) for item in line.items)
    return line.model_copy(update={"items": items})


def _positioned_item(item: LineItemSpec, role: str) -> LineItemSpec:
    position = operating_position_of(role)
    if position is None:
        _require_known_manual_valve(item, role)
        return item
    return item.model_copy(update={"operating_position": position})


def _require_known_manual_valve(item: LineItemSpec, role: str) -> None:
    """A manual valve of a role the tables do not know is a gap in the rules: stop, never skip."""
    if _is_manual_valve(item) and not is_positioned_role(role):
        raise ValueError(
            f"expected a position rule for the manual valve role {role!r} "
            f"({item.node_id}, {item.node_class}); add it to valve_roles.py"
        )


def _is_manual_valve(item: LineItemSpec) -> bool:
    is_operated = CLASS_SPECS[NodeClass(item.node_class)].piping_kind == "operated"
    return is_operated and _automatic_kind(item) is None


def _automatic_kind(item: LineItemSpec) -> ItemKind | None:
    """CONTROL_VALVE or ON_OFF_VALVE for a valve that has an actuator tag, else None."""
    parsed = parse_tag(item.tag or "")
    if parsed is None:
        return None
    kind = item_kind(item.node_class, parsed.letters)
    return kind if kind in _AUTOMATIC_KINDS else None


# ---- fail actions -------------------------------------------------------------------------------


def _actuators_with_fail_action(
    plan: TrimPlan, table: Mapping[str, FailAction]
) -> tuple[InstrumentSpec, ...]:
    valve_of = {
        link.source_id: link.target_id for link in plan.links if link.relation is Relation.CONTROL
    }
    places = _valve_places(plan)
    updated = []
    for spec in plan.instruments:
        valve_id = valve_of.get(spec.node_id)
        if spec.node_class != _ACTUATOR or valve_id is None:
            updated.append(spec)
            continue
        service = _service_of(valve_id, places, plan)
        updated.append(spec.model_copy(update={"fail_action": _table_entry(table, service, spec)}))
    return tuple(updated)


def _valve_places(plan: TrimPlan) -> dict[str, tuple[LineItemSpec, LineSpec]]:
    """Every inline part with the line it sits on, by node id."""
    return {item.node_id: (item, line) for line in plan.lines for item in line.items}


def _service_of(
    valve_id: str, places: Mapping[str, tuple[LineItemSpec, LineSpec]], plan: TrimPlan
) -> str:
    if valve_id not in places:
        raise ValueError(f"expected the valve {valve_id!r} of an actuator on a line of its plan")
    item, line = places[valve_id]
    kind = _automatic_kind(item)
    if kind is None:
        raise ValueError(f"expected {valve_id!r} to be a control or on-off valve, got a manual one")
    stream_kind: StreamKindV2 | None = plan.stream_kinds.get(line.line_number)
    return fail_action_service(plan.roles[valve_id], kind, line.fluid_code, stream_kind)


def _table_entry(
    table: Mapping[str, FailAction], service: str, actuator: InstrumentSpec
) -> FailAction:
    if service not in table:
        raise ValueError(
            f"expected fail_action_table to have the service {service!r} "
            f"(needed by actuator {actuator.node_id}); it has {sorted(table)}"
        )
    return table[service]


# ---- reading them back (checks and the DEXPI writer) --------------------------------------------


def positions_of(plans: Iterable[TrimPlan]) -> dict[str, OperatingPosition]:
    """Node id -> normal position of every positioned valve of the plans."""
    return {
        item.node_id: item.operating_position
        for plan in plans
        for line in plan.lines
        for item in line.items
        if item.operating_position is not None
    }


def fail_actions_of(plans: Iterable[TrimPlan]) -> dict[str, FailAction]:
    """Valve node id -> fail action of its actuator, for every valve whose actuator has one."""
    found: dict[str, FailAction] = {}
    for plan in plans:
        actions = {s.node_id: s.fail_action for s in plan.instruments if s.fail_action is not None}
        for link in plan.links:
            if link.relation is Relation.CONTROL and link.source_id in actions:
                found[link.target_id] = actions[link.source_id]
    return found
