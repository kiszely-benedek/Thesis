"""Checks of the exchanger rules (Toghraei 2019 pp.207, 320, 326): how a heat exchanger is piped.

A **heat exchanger** moves heat between two streams without mixing them; a **utility** stream
(steam, cooling water, fuel gas) is the plant's own supply, a **process** stream is the product
being treated. The **target stream** is the one whose temperature a controller holds. A
**steam heater** warms a process stream with steam, which leaves as **condensate** (liquid water);
a **steam trap** lets condensate out but holds steam in.

Like the other plant-level checks these read the plan's graph on v2.1 and v2.2 plants alike.
"""

from __future__ import annotations

from collections.abc import Iterable

import networkx as nx

from plantgraph.benchmark.v2.rules.checks_v21_plant import flow, reach
from plantgraph.benchmark.v2.rules.control_graph import (
    LEVEL,
    STEAM_SERVICES,
    TEMPERATURE,
    UTILITY_SERVICES,
    control_loops,
    controllers_on,
    is_control_valve,
    service_of,
)
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import EQUIPMENT_CLASSES

#: exchangers proper; an air cooler or furnace also moves heat but has no steam or spare to speak of
_EXCHANGER_CLASSES = frozenset(
    {"TubularHeatExchanger", "HeatExchanger", "PlateHeatExchanger", "SpiralHeatExchanger"}
)
#: equipment through which a stream is heated or cooled: a bypass around one of these bypasses it
_HEAT_TRANSFER_CLASSES = _EXCHANGER_CLASSES | {"AirCoolingSystem", "Furnace", "Heater"}
_BLOCK_VALVES = frozenset({"GateValve", "BallValve", "ButterflyValve", "PlugValve"})
#: a run of pipe that ends in one of these is a trim branch (vent, drain, tap), not a process line
_TRIM_END_CLASSES = frozenset({"BlindFlange", "Funnel", "VentilationDevice", "RuptureDisc"})
#: the hand bypass of a control-valve or trap station belongs to that station, not to the exchanger
_STATION_BYPASS_ROLES = frozenset({"cv_bypass_valve", "trap_bypass_valve"})
_CONDENSATE = "CD"


def _service_around(view: RuleView, node: str) -> str:
    """The service of the pipe a part sits on (read from either neighbour)."""
    piping = flow(view.graph)
    for before in piping.predecessors(node):
        return service_of(view.graph, before, node)
    for after in piping.successors(node):
        return service_of(view.graph, node, after)
    return ""


def _is_junction(piping: nx.DiGraph[str], node: str) -> bool:
    """A tee: a pipe part with more than one way in or out."""
    return bool(piping.in_degree(node) + piping.out_degree(node) > 2)


def _run_to_junction(
    piping: nx.DiGraph[str], graph: nx.DiGraph[str], start: str, up: bool
) -> list[str]:
    """The single-file pipe parts from `start` outward, up to a tee, equipment or open end.

    The last element is where the run stops. `up` walks against the flow.
    """
    step = piping.predecessors if up else piping.successors
    run = [start]
    while True:
        last = run[-1]
        if graph.nodes[last]["node_class"] in EQUIPMENT_CLASSES or _is_junction(piping, last):
            break
        following = list(step(last))
        if len(following) != 1:
            break
        run.append(following[0])
    return run


# ---- TOG320-HX-NONTARGET -----------------------------------------------------------------------


def _bypasses_a_heat_transfer_item(view: RuleView, valve: str) -> bool:
    """True when the valve sits on a branch that skips an exchanger or heater.

    The exchanger then hangs off a part before the valve and returns to a part after it.
    """
    piping, graph = flow(view.graph), view.graph
    before, _ = reach(piping, graph, valve, up=True)
    after, _ = reach(piping, graph, valve, up=False)
    for part in before:
        for item in piping.successors(part):
            is_heater = graph.nodes[item]["node_class"] in _HEAT_TRANSFER_CLASSES
            if is_heater and any(back in after for back in piping.successors(item)):
                return True
    return False


def _nontarget_problem(view: RuleView, valve: str) -> str | None:
    service = _service_around(view, valve)
    if service in UTILITY_SERVICES:
        return None  # directly on the utility stream
    if _bypasses_a_heat_transfer_item(view, valve):
        return None  # on a bypass of a process stream
    return (
        f"temperature valve {valve} sits on a {service or 'unknown'} process line in series, "
        "not on a utility line or on a bypass around an exchanger"
    )


def check_hx_nontarget(view: RuleView) -> CheckResult:
    """TOG320-HX-NONTARGET: the temperature valve moves a utility, or bypasses a process stream."""
    # rule TOG320-HX-NONTARGET: the non-target stream is moved (Toghraei 2019 p.320–321)
    loops = [loop for loop in control_loops(view) if loop.variable == TEMPERATURE]
    violations = [
        Violation(rule_id="TOG320-HX-NONTARGET", node_id=loop.valve, detail=problem)
        for loop in loops
        if (problem := _nontarget_problem(view, loop.valve))
    ]
    return CheckResult(checked=len(loops), violations=tuple(violations))


# ---- TOG207-HX-NO-ISOLATION --------------------------------------------------------------------


def _is_trim_run(view: RuleView, run: list[str]) -> bool:
    """A run with a safety valve, or ending in a cap, funnel or vent, is a branch (a trim)."""
    classes = [str(view.graph.nodes[n]["node_class"]) for n in run]
    return classes[-1] in _TRIM_END_CLASSES or any(c.endswith("SafetyValve") for c in classes)


def _isolation_valves(view: RuleView, exchanger: str) -> list[str]:
    """The block valves on the exchanger's own nozzle lines (vent and drain branches excluded)."""
    piping, graph = flow(view.graph), view.graph
    valves: list[str] = []
    for up, neighbours in (
        (True, piping.predecessors(exchanger)),
        (False, piping.successors(exchanger)),
    ):
        for start in neighbours:
            run = _run_to_junction(piping, graph, start, up)
            if not _is_trim_run(view, run):
                valves += [n for n in run if graph.nodes[n]["node_class"] in _BLOCK_VALVES]
    return sorted(set(valves))


def _line_parts(view: RuleView, neighbours: Iterable[str], up: bool) -> set[str]:
    """The pipe parts of the lines that touch an item: each neighbour and what lies beyond it."""
    piping, graph = flow(view.graph), view.graph
    parts: set[str] = set()
    for node in neighbours:
        if graph.nodes[node]["node_class"] not in EQUIPMENT_CLASSES:
            parts |= {node, *reach(piping, graph, node, up)[0]}
    return parts


def _manual_bypass(view: RuleView, exchanger: str) -> bool:
    """True when pipe alone leads around the exchanger with no control valve on the way.

    Start from the parts that feed the exchanger and the parts it feeds; a path between the two
    that crosses no equipment skips the exchanger. A control valve on it (the temperature bypass
    of TOG320) makes it a control branch, not an isolation bypass.
    """
    piping, graph = flow(view.graph), view.graph
    feeding = _line_parts(view, piping.predecessors(exchanger), up=True)
    fed = _line_parts(view, piping.successors(exchanger), up=False)
    open_pipe = [
        n for n in piping
        if graph.nodes[n]["node_class"] not in EQUIPMENT_CLASSES
        and not is_control_valve(graph, n)
        and view.roles.get(n) not in _STATION_BYPASS_ROLES
    ]  # fmt: skip
    around = piping.subgraph(open_pipe)
    return any(
        nx.has_path(around, start, end)
        for start in feeding & set(around)
        for end in (fed & set(around)) - {start}
    )


def _isolation_problem(view: RuleView, exchanger: str) -> str | None:
    valves = _isolation_valves(view, exchanger)
    if valves:
        roles = sorted({view.roles.get(v, "?") for v in valves})
        return f"isolation valves {valves} (roles {roles}) around the exchanger"
    if _manual_bypass(view, exchanger):
        return "a bypass without a control valve around the exchanger"
    return None


def check_hx_no_isolation(view: RuleView) -> CheckResult:
    """TOG207-HX-NO-ISOLATION: no isolation valves and no bypass, unless a spare is installed."""
    # rule TOG207-HX-NO-ISOLATION: no isolation valves around an exchanger (Toghraei 2019 p.207)
    spared = {n for record in view.generated.record.spare_sets for n in record.node_ids}
    graph = view.graph
    exchangers = sorted(
        n for n, d in graph.nodes(data=True) if d["node_class"] in _EXCHANGER_CLASSES
    )
    violations = [
        Violation(rule_id="TOG207-HX-NO-ISOLATION", node_id=exchanger, detail=problem)
        for exchanger in exchangers
        if exchanger not in spared and (problem := _isolation_problem(view, exchanger))
    ]
    n_spared = sum(e in spared for e in exchangers)
    exceptions = {"has_spare": n_spared} if n_spared else {}
    return CheckResult(checked=len(exchangers), violations=tuple(violations), exceptions=exceptions)


# ---- TOG326-STEAM-CONDENSATE -------------------------------------------------------------------


def _steam_heaters(view: RuleView) -> list[str]:
    """Exchangers a steam pipe feeds directly."""
    piping = flow(view.graph)
    return sorted(
        n
        for n, d in view.graph.nodes(data=True)
        if d["node_class"] in _EXCHANGER_CLASSES
        and any(service_of(view.graph, a, n) in STEAM_SERVICES for a in piping.predecessors(n))
    )


def _condensate_mode(view: RuleView, heater: str) -> str | None:
    """How the heater's condensate line ends: `trap`, `trap_station`, `drain_pot`, or None."""
    piping, graph = flow(view.graph), view.graph
    starts = [b for b in piping.successors(heater) if service_of(graph, heater, b) == _CONDENSATE]
    for start in starts:
        parts, equipment = reach(piping, graph, start, up=False)
        parts |= {start}
        if any(view.roles.get(n) == "trap_tee_in" for n in parts):
            return "trap_station"
        if any(graph.nodes[n]["node_class"] == "SteamTrap" for n in parts):
            return "trap"
        pots = [e for e in equipment if view.roles.get(e) == "condensate_drain_pot"]
        if any(controllers_on(graph, pot, LEVEL) for pot in pots):
            return "drain_pot"
    return None


def check_steam_condensate(view: RuleView) -> CheckResult:
    """TOG326-STEAM-CONDENSATE: condensate leaves by a trap, a trap station or a controlled pot."""
    # rule TOG326-STEAM-CONDENSATE: trap, trap station or controlled pot (Toghraei 2019 p.326–327)
    heaters = _steam_heaters(view)
    detail = (
        "expected a trap, a trap station or a level-controlled pot on the condensate, found none"
    )
    violations = [
        Violation(rule_id="TOG326-STEAM-CONDENSATE", node_id=heater, detail=detail)
        for heater in heaters
        if _condensate_mode(view, heater) is None
    ]
    return CheckResult(checked=len(heaters), violations=tuple(violations))
