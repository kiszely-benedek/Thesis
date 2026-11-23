"""Check of the one-loop-per-inventory rule (Toghraei 2019 p.295 Table 15.1, rule 8 on p.270).

An **inventory** is the amount of liquid or gas a container holds. A **level loop** keeps the
liquid amount constant; a **pressure loop** keeps the gas amount (its pressure) constant. Two
loops on one inventory would fight, none would let it drift. Exceptions the check derives itself
(the generator writes none of these codes) from the plan's roles and the piping:
- `storage_tank_batch`: an atmospheric tank with a level transmitter but no level loop (p.305);
- `pressure_floating_on:<id>`: a drum piped by gas, with no valve, to a neighbour that holds the
  pressure;
- `pressure_optional`: a vessel with no process-gas line and no pressure-dependent role has no
  pressure loop; p.270 makes it a choice, so one at most is allowed.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.rules.checks_v21_plant import flow
from plantgraph.benchmark.v2.rules.control_graph import (
    CONTAINER_CLASSES,
    FLOODED_CONTAINER_ROLES,
    GAS_SERVICES,
    LEVEL,
    LIQUID_SERVICES,
    PRESSURE,
    PRESSURE_DEPENDENT_ROLES,
    controllers_on,
    is_control_valve,
    routes_between_containers,
    sensors_on,
    service_of,
)
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView

_ATMOSPHERIC_CLASS = "Tank"  # vents through a breather: no pressure loop to look for


def _attached_services(view: RuleView, container: str, skip_trims: bool = False) -> set[str]:
    """The services of the pipes that touch the container directly.

    A trim line (a vent with a cap, a thermometer tee) carries no process stream; `skip_trims`
    leaves those out, so a capped vent does not make a vessel a gas container.
    """
    piping = flow(view.graph)
    if container not in piping:
        return set()
    edges = [*piping.in_edges(container), *piping.out_edges(container)]
    if skip_trims:
        edges = [(a, b) for a, b in edges if not _is_trim_line(view, a, b)]
    return {service_of(view.graph, a, b) for a, b in edges}


def _is_trim_line(view: RuleView, upstream: str, downstream: str) -> bool:
    number = view.graph.edges[upstream, downstream].get("line_number", "")
    return view.stream_kind_of(number) is StreamKindV2.TRIM


def _is_gas_route_without_valve(view: RuleView, route: tuple[str, ...]) -> bool:
    pipes = zip(route, route[1:], strict=False)
    has_gas = any(service_of(view.graph, a, b) in GAS_SERVICES for a, b in pipes)
    return has_gas and not any(is_control_valve(view.graph, n) for n in route[1:-1])


def _floats_on(view: RuleView, container: str, routes: list[tuple[str, ...]]) -> str | None:
    """A neighbour with a pressure loop, joined to `container` by gas pipe and no control valve."""
    for route in routes:
        ends = {route[0], route[-1]}
        if container not in ends or len(ends) != 2:
            continue
        (partner,) = ends - {container}
        if _is_gas_route_without_valve(view, route) and controllers_on(
            view.graph, partner, PRESSURE
        ):
            return partner
    return None


def _count(exceptions: dict[str, int], code: str) -> None:
    exceptions[code] = exceptions.get(code, 0) + 1


def _level_problem(view: RuleView, container: str, exceptions: dict[str, int]) -> str | None:
    levels = controllers_on(view.graph, container, LEVEL)
    if len(levels) == 1 or not _attached_services(view, container) & LIQUID_SERVICES:
        return None
    if not levels and _is_watched_storage_tank(view, container):
        _count(exceptions, "storage_tank_batch")
        return None
    return f"expected one level loop, found {len(levels)}"


def _is_watched_storage_tank(view: RuleView, container: str) -> bool:
    """An atmospheric tank with a level transmitter: the operator watches it, no loop needed.

    Batch and storage flows often need no control (Toghraei p.305; p.270: a storage tank's
    controlled variable is level). The transmitter stays mandatory so no tank goes unwatched.
    """
    is_tank = view.graph.nodes[container]["node_class"] == _ATMOSPHERIC_CLASS
    return is_tank and bool(sensors_on(view.graph, container, LEVEL))


def _is_pressure_dependent(view: RuleView, container: str) -> bool:
    """A real process-gas line touches it, or its role needs a held pressure (p.270 rule 8)."""
    gas = _attached_services(view, container, skip_trims=True) & GAS_SERVICES
    return bool(gas) or view.roles.get(container) in PRESSURE_DEPENDENT_ROLES


def _pressure_problem(
    view: RuleView, container: str, routes: list[tuple[str, ...]], exceptions: dict[str, int]
) -> str | None:
    pressures = controllers_on(view.graph, container, PRESSURE)
    if view.graph.nodes[container]["node_class"] == _ATMOSPHERIC_CLASS:
        return None
    if not _is_pressure_dependent(view, container):
        if len(pressures) > 1:  # p.270: on other vessels pressure control is a choice, once at most
            return f"expected at most one pressure loop, found {len(pressures)}"
        if not pressures:
            _count(exceptions, "pressure_optional")
        return None
    if len(pressures) == 1:
        return None
    partner = None if pressures else _floats_on(view, container, routes)
    if partner is None:
        return f"expected one pressure loop, found {len(pressures)}"
    _count(exceptions, f"pressure_floating_on:{partner}")
    return None


def _flooded_problem(view: RuleView, container: str) -> str | None:
    graph = view.graph
    loops = controllers_on(graph, container, LEVEL) + controllers_on(graph, container, PRESSURE)
    return f"a flooded container has loops {loops}" if loops else None


def _problems(
    view: RuleView, container: str, routes: list[tuple[str, ...]], exceptions: dict[str, int]
) -> list[str | None]:
    if view.roles.get(container) in FLOODED_CONTAINER_ROLES:
        return [_flooded_problem(view, container)]
    return [
        _level_problem(view, container, exceptions),
        _pressure_problem(view, container, routes, exceptions),
    ]


def check_inventory_once(view: RuleView) -> CheckResult:
    """TOG295-INVENTORY-ONCE: one level loop per liquid container, one pressure loop per gas one."""
    # rule TOG295-INVENTORY-ONCE: one loop per inventory (Toghraei 2019 p.295)
    nodes = view.graph.nodes(data=True)
    containers = sorted(n for n, d in nodes if d["node_class"] in CONTAINER_CLASSES)
    routes = routes_between_containers(view)
    exceptions: dict[str, int] = {}
    violations = []
    for container in containers:
        detail = "; ".join(p for p in _problems(view, container, routes, exceptions) if p)
        if detail:
            violations.append(
                Violation(rule_id="TOG295-INVENTORY-ONCE", node_id=container, detail=detail)
            )
    return CheckResult(checked=len(containers), violations=tuple(violations), exceptions=exceptions)
