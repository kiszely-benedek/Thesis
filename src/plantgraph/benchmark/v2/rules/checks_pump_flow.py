"""Check of the pump-flow rule (Toghraei 2019 p.270): every pump set's flow is controlled once.

A **pump set** is one pump or an installed A/B(/C) group (one runs, the rest are spare). Its flow
is fixed by exactly one of: a flow loop on its discharge, a variable-speed drive (a controller
sets the motor speed), or a level loop's valve on the discharge. The check follows every
**discharge route** (the pipe from the pump to the next equipment item, or to the open end where a
product leaves the plant) and counts such devices on it. Side routes are no process route and are
skipped: the spillback to the suction vessel, a relief line, and the hand bypass of a valve
station.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.rules.checks_v21_plant import flow
from plantgraph.benchmark.v2.rules.control_graph import (
    FLOW,
    LEVEL,
    drives_speed,
    loop_of,
    routes_from,
)
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import EQUIPMENT_CLASSES

_PUMP_CLASSES = frozenset({"CentrifugalPump", "ReciprocatingPump", "RotaryPump"})
_VACUUM_PUMP_ROLE = "liquid_ring_pump"  # draws a vacuum, moves no liquid between containers
#: parts only a side branch has: the spillback to the suction vessel (min-flow), a PD relief line,
#: or the hand bypass of a control-valve station; the min-flow tee is not listed, it sits on the
#: main discharge line
_SIDE_ROUTE_ROLES = frozenset(
    {
        "min_flow_check",
        "min_flow_block",
        "min_flow_switch_valve",
        "min_flow_control_valve",
        "restriction_orifice",
        "pd_relief_valve",
        "cv_bypass_valve",
    }
)
#: where a trim branch (vent, drain, tap, relief) ends; a main line never ends in one of these
_TRIM_END_CLASSES = frozenset(
    {"BlindFlange", "Funnel", "VentilationDevice", "BreatherValve", "Silencer", "RuptureDisc"}
)


def _pump_set_leaders(view: RuleView) -> list[str]:
    """One pump per installed set (the first member), plus every pump that stands alone."""
    spares = {n for record in view.generated.record.spare_sets for n in record.node_ids[1:]}
    pumps = [
        n
        for n, d in view.graph.nodes(data=True)
        if d["node_class"] in _PUMP_CLASSES and view.roles.get(n) != _VACUUM_PUMP_ROLE
    ]
    return sorted(set(pumps) - spares)


def _ends_a_process_route(view: RuleView, piping: nx.DiGraph[str], node: str) -> bool:
    """True at an equipment item, or at the open end of a main line (a product leaving)."""
    node_class = str(view.graph.nodes[node]["node_class"])
    if node_class in EQUIPMENT_CLASSES:
        return True
    is_trim_end = node_class in _TRIM_END_CLASSES or node_class.endswith("SafetyValve")
    return piping.out_degree(node) == 0 and not is_trim_end


def _parts_on(view: RuleView, route: tuple[str, ...]) -> tuple[str, ...]:
    """The route without its pump; an equipment end is dropped, an open end's last part stays."""
    ends_at_equipment = view.graph.nodes[route[-1]]["node_class"] in EQUIPMENT_CLASSES
    return route[1:-1] if ends_at_equipment else route[1:]


def _is_process_route(view: RuleView, route: tuple[str, ...]) -> bool:
    return not any(view.roles.get(n) in _SIDE_ROUTE_ROLES for n in _parts_on(view, route))


def _flow_devices(view: RuleView, pump: str, route: tuple[str, ...]) -> list[str]:
    """What fixes the flow along a route: a flow or level valve, or the pump's variable speed."""
    valves = [
        n
        for n in _parts_on(view, route)
        if (loop := loop_of(view.graph, n)) is not None and loop.variable in (FLOW, LEVEL)
    ]
    return [*valves, pump] if drives_speed(view.graph, pump) else valves


def _pump_problem(view: RuleView, pump: str) -> str | None:
    piping = flow(view.graph)
    every_route = routes_from(piping, pump, lambda n: _ends_a_process_route(view, piping, n))
    routes = [r for r in every_route if _is_process_route(view, r)]
    if not routes:
        return "expected a discharge route to a process item, found none"
    wrong = [(r, d) for r in routes if len(d := _flow_devices(view, pump, r)) != 1]
    if not wrong:
        return None
    route, devices = wrong[0]
    return (
        f"{len(wrong)} of {len(routes)} discharge routes do not fix the flow exactly once; "
        f"for example the route to {route[-1]} has {devices or 'no flow device'}"
    )


def check_pump_flow_controlled(view: RuleView) -> CheckResult:
    """TOG270-PUMP-FLOW-CONTROLLED: every process route of a pump set has one flow device."""
    # rule TOG270-PUMP-FLOW-CONTROLLED: each pump flow is fixed once (Toghraei 2019 p.270)
    pumps = _pump_set_leaders(view)
    violations = [
        Violation(rule_id="TOG270-PUMP-FLOW-CONTROLLED", node_id=pump, detail=problem)
        for pump in pumps
        if (problem := _pump_problem(view, pump))
    ]
    return CheckResult(checked=len(pumps), violations=tuple(violations))
