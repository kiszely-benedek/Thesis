"""Checks of the valve-position rules of v2.2 (Toghraei 2019 p.114, p.120, p.224) and fail actions.

A **normal position** says how a valve stands in ordinary operation (normally open, normally
closed, car-sealed open); a **fail action** says what an automatic valve does when its air or
signal is lost. Both are design data of the plan, not edges of the graph, so the checks read the
plan (`positions_of`, `fail_actions_of`) and use the graph only to find which valves exist.

Every check reports `checked=0` on a v2.1 plant and on a v2.2 plant with the handbook off: those
draw no positions, and their goldens are pinned.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.config_v22 import FailAction
from plantgraph.benchmark.v2.plan_models import OperatingPosition
from plantgraph.benchmark.v2.rules.control_graph import (
    TEMPERATURE,
    control_loops,
    controller_of,
    sensed_items,
)
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.valve_positions import fail_actions_of, positions_of
from plantgraph.benchmark.v2.valve_roles import (
    BLOCKING_ROLES,
    CV_BYPASS_ROLES,
    MIN_FLOW_VALVE_ROLES,
    PSV_BLOCK_ROLES,
    VENT_DRAIN_ROLES,
)
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind
from plantgraph.graph.schema import CLASS_SPECS, NodeClass

_NOT_APPLICABLE = CheckResult(checked=0)
_MAIN_BRANCH_ROLE = "hx_main_control_valve"
_HAND_CONTROL_LETTERS = ("HV", "HCV")  # an operator throttles it, so it has no actuator


def _positions(view: RuleView) -> dict[str, OperatingPosition]:
    return view.cached(
        "valve_positions", lambda: positions_of(u.instance.plan for u in view.plan.units)
    )


def _fail_actions(view: RuleView) -> dict[str, FailAction]:
    return view.cached(
        "valve_fail_actions", lambda: fail_actions_of(u.instance.plan for u in view.plan.units)
    )


def _nodes_with_roles(view: RuleView, roles: frozenset[str]) -> list[str]:
    return sorted(n for n in view.graph.nodes if view.roles.get(n) in roles)


def _position_check(
    view: RuleView, rule_id: str, roles: frozenset[str], expected: OperatingPosition
) -> CheckResult:
    """Every valve of `roles` stands in the `expected` position."""
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    positions = _positions(view)
    nodes = _nodes_with_roles(view, roles)
    violations = tuple(
        Violation(
            rule_id=rule_id,
            node_id=node,
            detail=f"expected position {expected}, found {positions.get(node)}"
            f" on role {view.roles[node]}",
        )
        for node in nodes
        if positions.get(node) != expected
    )
    return CheckResult(checked=len(nodes), violations=violations)


def check_block_default_no(view: RuleView) -> CheckResult:
    """TOG114-BLOCK-DEFAULT-NO: a blocking valve is normally open."""
    # rule TOG114-BLOCK-DEFAULT-NO: blocking valves are normally open (Toghraei 2019 p.114)
    return _position_check(view, "TOG114-BLOCK-DEFAULT-NO", BLOCKING_ROLES, "NO")


def check_vent_drain_nc(view: RuleView) -> CheckResult:
    """TOG114-VENT-DRAIN-NC: vent and drain valves are normally closed."""
    # rule TOG114-VENT-DRAIN-NC: vent and drain valves are normally closed (Toghraei 2019 p.114)
    return _position_check(view, "TOG114-VENT-DRAIN-NC", VENT_DRAIN_ROLES, "NC")


def check_cv_bypass_nc(view: RuleView) -> CheckResult:
    """TOG120-CV-BYPASS-NC: the bypass valve of a control-valve station is closed."""
    # rule TOG120-CV-BYPASS-NC: a CV bypass is closed in operation (Toghraei 2019 p.120)
    return _position_check(view, "TOG120-CV-BYPASS-NC", CV_BYPASS_ROLES, "NC")


def check_psv_blocks_cso(view: RuleView) -> CheckResult:
    """TOG224-PSV-BLOCKS-CSO: the manual valves under and over a PSV are car-sealed open."""
    # rule TOG224-PSV-BLOCKS-CSO: the blocks at a PSV are car-sealed open (Toghraei 2019 p.224)
    return _position_check(view, "TOG224-PSV-BLOCKS-CSO", PSV_BLOCK_ROLES, "CSO")


# ---- TOG114-FAIL-ACTION -------------------------------------------------------------------------


def _is_automatic_valve(view: RuleView, node: str) -> bool:
    """True for a control or on-off valve (a hand control valve has no actuator)."""
    data = view.graph.nodes[node]
    if CLASS_SPECS[NodeClass(data["node_class"])].piping_kind != "operated":
        return False
    parsed = parse_tag(str(data.get("tag") or ""))
    if parsed is None or parsed.letters.startswith(_HAND_CONTROL_LETTERS):
        return False
    return item_kind(data["node_class"], parsed.letters) in (
        ItemKind.CONTROL_VALVE,
        ItemKind.ON_OFF_VALVE,
    )


def automatic_valves(view: RuleView) -> list[str]:
    """The control and on-off valves of the plant, sorted."""
    return sorted(n for n in view.graph.nodes if _is_automatic_valve(view, n))


def _fail_action_problem(view: RuleView, valve: str, actions: dict[str, FailAction]) -> str | None:
    action = actions.get(valve)
    if action is None:
        return "expected a fail action on every automatic valve, found none"
    if view.roles.get(valve) in MIN_FLOW_VALVE_ROLES and action != "FO":
        return f"expected a min-flow valve to fail open (FO), found {action}"
    return None


def split_partners(view: RuleView, main_valve: str) -> list[str]:
    """The other temperature valves that read the point `main_valve`'s controller reads."""
    controller = controller_of(view.graph, main_valve)
    point = tuple(sensed_items(view.graph, controller)) if controller else ()
    return [
        loop.valve
        for loop in control_loops(view)
        if loop.variable == TEMPERATURE
        and loop.valve != main_valve
        and point
        and tuple(sensed_items(view.graph, loop.controller)) == point
    ]


def _violation(node: str, detail: str) -> Violation:
    return Violation(rule_id="TOG114-FAIL-ACTION", node_id=node, detail=detail)


def _pair_problems(view: RuleView, actions: dict[str, FailAction]) -> list[Violation]:
    """The two valves of a TOG322 pair move in opposite directions, so they fail oppositely."""
    problems = []
    for main in _nodes_with_roles(view, frozenset({_MAIN_BRANCH_ROLE})):
        partners = split_partners(view, main)
        if not partners:
            problems.append(_violation(main, "expected a bypass valve on the same outlet sensor"))
        for partner in partners:
            if actions.get(main) == actions.get(partner):
                found = actions.get(main)
                problems.append(
                    _violation(main, f"expected opposite fail actions with {partner}, both {found}")
                )
    return problems


def check_fail_action(view: RuleView) -> CheckResult:
    """TOG114-FAIL-ACTION: every automatic valve has a fail action; min-flow valves fail open."""
    # rule TOG114-FAIL-ACTION: every automatic valve has a fail action (Toghraei 2019 p.114–115)
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    actions = _fail_actions(view)
    valves = automatic_valves(view)
    violations = [
        _violation(valve, problem)
        for valve in valves
        if (problem := _fail_action_problem(view, valve, actions)) is not None
    ]
    violations += _pair_problems(view, actions)
    return CheckResult(checked=len(valves), violations=tuple(violations))
