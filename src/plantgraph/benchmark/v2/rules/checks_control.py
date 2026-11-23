"""Checks of the flow-control rules (Toghraei 2019 pp.267, 271), design 6.3.

They look at the whole plant, on v2.1 and v2.2 alike: where the valves of a plant's loops sit
relative to its vessels and sensors. A **route** is the pipe path between two items; branches in
parallel are separate routes. No full degrees-of-freedom analysis is done: the checks stop at
"no stream throttled twice in series, each flow element before its valve".
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.rules.checks_v21_plant import comes_before, flow
from plantgraph.benchmark.v2.rules.control_graph import (
    FLOW,
    LIQUID_SERVICES,
    ControlLoop,
    control_loops,
    is_control_valve,
    routes_between_containers,
    sensed_items,
    service_of,
)
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView

# ---- TOG271-ONE-CV-LIQUID ----------------------------------------------------------------------


def _is_liquid_route(view: RuleView, route: tuple[str, ...]) -> bool:
    pipes = zip(route, route[1:], strict=False)
    return all(service_of(view.graph, a, b) in LIQUID_SERVICES for a, b in pipes)


def check_one_cv_liquid(view: RuleView) -> CheckResult:
    """TOG271-ONE-CV-LIQUID: at most one control valve in series between two containers."""
    # rule TOG271-ONE-CV-LIQUID: one control valve per liquid line between vessels (Toghraei p.271)
    routes = [r for r in routes_between_containers(view) if _is_liquid_route(view, r)]
    reported: set[tuple[str, ...]] = set()  # parallel spare pumps repeat the same valve pair
    violations = []
    for route in routes:
        valves = tuple(n for n in route[1:-1] if is_control_valve(view.graph, n))
        if len(valves) < 2 or valves in reported:
            continue
        reported.add(valves)
        detail = f"{len(valves)} control valves {list(valves)} in series, {route[0]} to {route[-1]}"
        violations.append(
            Violation(rule_id="TOG271-ONE-CV-LIQUID", node_id=valves[0], detail=detail)
        )
    return CheckResult(checked=len(routes), violations=tuple(violations))


# ---- TOG267-FE-UPSTREAM-FV ---------------------------------------------------------------------


def _has_path(piping: nx.DiGraph[str], source: str, target: str) -> bool:
    return source in piping and target in piping and nx.has_path(piping, source, target)


def _is_upstream(view: RuleView, element: str, valve: str) -> bool:
    """A pipe path leads from the element to the valve, and none leads back without equipment."""
    piping = flow(view.graph)
    leads_to_valve = _has_path(piping, element, valve)
    return leads_to_valve and not comes_before(piping, view.graph, valve, element)


def _element_problem(view: RuleView, loop: ControlLoop) -> str | None:
    """A ratio loop senses a second element on another stream, so one upstream element suffices."""
    elements = sensed_items(view.graph, loop.controller)
    if not elements:
        return f"expected a flow element sensed by {loop.controller}, found none"
    if any(_is_upstream(view, element, loop.valve) for element in elements):
        return None
    return f"none of the flow elements {elements} is upstream of valve {loop.valve}"


def check_fe_upstream_fv(view: RuleView) -> CheckResult:
    """TOG267-FE-UPSTREAM-FV: a flow element lies upstream of the flow valve of its loop.

    The path from element to valve may cross equipment: an anti-surge element sits on the
    compressor suction, its valve on the discharge recycle. A path back that crosses equipment is
    that recycle itself and is allowed.
    """
    # rule TOG267-FE-UPSTREAM-FV: the flow element comes before its valve (Toghraei 2019 p.267)
    flow_loops = [loop for loop in control_loops(view) if loop.variable == FLOW]
    violations = [
        Violation(rule_id="TOG267-FE-UPSTREAM-FV", node_id=loop.valve, detail=problem)
        for loop in flow_loops
        if (problem := _element_problem(view, loop))
    ]
    return CheckResult(checked=len(flow_loops), violations=tuple(violations))
