"""Checks of the v2.2 pump rules (Toghraei 2019 pp.177, 192, 314): what a pump's discharge has.

A **positive-displacement (PD) pump** (reciprocating or rotary) moves a fixed volume per stroke or
turn: shutting its outlet raises the pressure without limit, and a valve throttling its outlet does
not change its flow. A **min-flow line** (also spillback or recirculation) lets a centrifugal
pump return liquid to its suction vessel so it never runs against a closed valve.

These rules are v2.2 behaviours. On a v2.1 plant (or with the handbook off) every check here
reports `checked=0`: v2.1 draws these parts the old way, and its goldens are pinned.
Roles (`discharge_check`, `min_flow_tee`...) are the plan's answer key; see `checks_v21_plant`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from plantgraph.benchmark.v2.rules.checks_v21_plant import (
    CENTRIFUGAL_PUMP,
    POSITIVE_DISPLACEMENT_PUMPS,
    comes_before,
    reach,
)
from plantgraph.benchmark.v2.rules.control_graph import FLOW, loop_of
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView

_PUMP_CLASSES = POSITIVE_DISPLACEMENT_PUMPS | {CENTRIFUGAL_PUMP}
_MIN_FLOW_ROLES = ("min_flow_tee", "min_flow_check", "min_flow_block")


def pumps_of_classes(view: RuleView, classes: Iterable[str]) -> list[str]:
    """Node ids of the pumps whose class is in `classes`, sorted."""
    wanted = set(classes)
    return sorted(n for n, d in view.graph.nodes(data=True) if d["node_class"] in wanted)


def _downstream(view: RuleView, pump: str) -> set[str]:
    """The pipe parts after the pump, up to the next equipment item."""
    return reach(view.piping, view.graph, pump, up=False)[0]


def nodes_with_role(view: RuleView, nodes: Iterable[str], roles: Iterable[str]) -> list[str]:
    """The nodes among `nodes` whose role (the plan's answer key) is one of `roles`, sorted."""
    wanted = set(roles)
    return sorted(n for n in nodes if view.roles.get(n) in wanted)


def _for_each_pump(
    rule_id: str,
    view: RuleView,
    classes: Iterable[str],
    problem_of: Callable[[RuleView, str], str | None],
) -> CheckResult:
    """Run `problem_of(view, pump)` on every pump of `classes`; a text answer is a violation."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    pumps = pumps_of_classes(view, classes)
    violations = [
        Violation(rule_id=rule_id, node_id=pump, detail=problem)
        for pump in pumps
        if (problem := problem_of(view, pump))
    ]
    return CheckResult(checked=len(pumps), violations=tuple(violations))


# ---- TOG192-RECIP-NO-CHECK ---------------------------------------------------------------------


def _check_problem(view: RuleView, pump: str) -> str | None:
    """A reciprocating pump has no check valve on its discharge; the other classes have one."""
    checks = nodes_with_role(view, _downstream(view, pump), ["discharge_check"])
    reciprocating = view.graph.nodes[pump]["node_class"] == "ReciprocatingPump"
    if reciprocating and checks:
        return f"reciprocating pump has an external check valve {checks[0]}"
    if not reciprocating and not checks:
        return "expected a check valve on a centrifugal or rotary pump discharge, found none"
    return None


def check_recip_no_check(view: RuleView) -> CheckResult:
    """TOG192-RECIP-NO-CHECK: no external check valve on a reciprocating pump, one on the others."""
    return _for_each_pump("TOG192-RECIP-NO-CHECK", view, _PUMP_CLASSES, _check_problem)


# ---- TOG192-PD-NO-MINFLOW ----------------------------------------------------------------------


def _min_flow_problem(view: RuleView, pump: str) -> str | None:
    parts = nodes_with_role(view, _downstream(view, pump), _MIN_FLOW_ROLES)
    return f"PD pump has min-flow parts {parts}" if parts else None


def check_pd_no_minflow(view: RuleView) -> CheckResult:
    """TOG192-PD-NO-MINFLOW: no min-flow line on a reciprocating or rotary pump."""
    return _for_each_pump(
        "TOG192-PD-NO-MINFLOW", view, POSITIVE_DISPLACEMENT_PUMPS, _min_flow_problem
    )


# ---- TOG314-PD-NO-THROTTLE ---------------------------------------------------------------------


def _throttle_problem(view: RuleView, pump: str) -> str | None:
    loops = (loop_of(view.graph, node) for node in sorted(_downstream(view, pump)))
    valves = [loop.valve for loop in loops if loop is not None and loop.variable == FLOW]
    return f"flow control valve {valves[0]} throttles a PD pump discharge" if valves else None


def check_pd_no_throttle(view: RuleView) -> CheckResult:
    """TOG314-PD-NO-THROTTLE: no flow control valve in series on a PD pump's discharge."""
    return _for_each_pump(
        "TOG314-PD-NO-THROTTLE", view, POSITIVE_DISPLACEMENT_PUMPS, _throttle_problem
    )


# ---- TOG177-MINFLOW-TAKEOFF --------------------------------------------------------------------


def _takeoff_problems(view: RuleView, pump: str) -> list[str]:
    """One text per min-flow tee that lies between the pump's check valve and its block valve."""
    piping, graph = view.piping, view.graph
    parts = _downstream(view, pump)
    checks = nodes_with_role(view, parts, ["discharge_check"])
    blocks = nodes_with_role(view, parts, ["discharge_block"])
    between = {
        tee
        for tee in nodes_with_role(view, parts, ["min_flow_tee"])
        for check in checks
        for block in blocks
        if comes_before(piping, graph, check, tee) and comes_before(piping, graph, tee, block)
    }
    return [
        f"min-flow line leaves at {tee}, between check and block valve" for tee in sorted(between)
    ]


def check_minflow_takeoff(view: RuleView) -> CheckResult:
    """TOG177-MINFLOW-TAKEOFF: a min-flow line never leaves between check and block valve."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    checked, violations = 0, []
    for pump in pumps_of_classes(view, _PUMP_CLASSES):
        checked += len(nodes_with_role(view, _downstream(view, pump), ["min_flow_tee"]))
        violations += [
            Violation(rule_id="TOG177-MINFLOW-TAKEOFF", node_id=pump, detail=text)
            for text in _takeoff_problems(view, pump)
        ]
    return CheckResult(checked=checked, violations=tuple(violations))
