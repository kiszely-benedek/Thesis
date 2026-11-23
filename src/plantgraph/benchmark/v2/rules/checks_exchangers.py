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
from dataclasses import dataclass

import networkx as nx

from plantgraph.benchmark.v2.rules.checks_v21_plant import reach
from plantgraph.benchmark.v2.rules.control_graph import (
    EXCHANGER_CLASSES,
    HEAT_TRANSFER_CLASSES,
    LEVEL,
    STEAM_SERVICES,
    TEMPERATURE,
    UTILITY_SERVICES,
    bypassed_items,
    control_loops,
    controller_of,
    controllers_on,
    is_control_valve,
    sensed_items,
    service_of,
)
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.trims_valves import HX_MAIN_VALVE_ROLE
from plantgraph.graph.schema import EQUIPMENT_CLASSES

_BLOCK_VALVES = frozenset({"GateValve", "BallValve", "ButterflyValve", "PlugValve"})
#: a run of pipe that ends in one of these is a trim branch (vent, drain, tap), not a process line
_TRIM_END_CLASSES = frozenset({"BlindFlange", "Funnel", "VentilationDevice", "RuptureDisc"})
#: the hand bypass of a control-valve or trap station belongs to that station, not to the exchanger
_STATION_BYPASS_ROLES = frozenset({"cv_bypass_valve", "trap_bypass_valve"})
_CONDENSATE = "CD"
_FLARE_HEADER = "FL"  # the flare service: a relief line, not the process
_PSV_INLET_ROLE = "psv_inlet_block"


def _service_around(view: RuleView, node: str) -> str:
    """The service of the pipe a part sits on (read from either neighbour)."""
    piping = view.piping
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


def _nontarget_problem(view: RuleView, valve: str) -> str | None:
    service = _service_around(view, valve)
    if service in UTILITY_SERVICES:
        return None  # directly on the utility stream
    if bypassed_items(view, valve):
        return None  # on a bypass of a process stream
    if view.roles.get(valve) == HX_MAIN_VALVE_ROLE:
        return None  # the exchanger's own branch of a two-valve bypass: TOG322 judges it
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


# ---- TOG322-HX-BYPASS-VARIANT ------------------------------------------------------------------


def temperature_bypass_valves(view: RuleView) -> list[str]:
    """The temperature control valves on a branch that skips an exchanger or heater."""
    loops = [loop for loop in control_loops(view) if loop.variable == TEMPERATURE]
    return [loop.valve for loop in loops if bypassed_items(view, loop.valve)]


def _heat_transfer_items_beside(view: RuleView, valve: str) -> set[str]:
    """The exchangers and heaters met in series with `valve`, upstream or downstream."""
    piping, graph = view.piping, view.graph
    found = reach(piping, graph, valve, up=True)[1] | reach(piping, graph, valve, up=False)[1]
    return {n for n in found if graph.nodes[n]["node_class"] in HEAT_TRANSFER_CLASSES}


def _controlled_point(graph: nx.DiGraph[str], valve: str) -> list[str]:
    controller = controller_of(graph, valve)
    return sensed_items(graph, controller) if controller is not None else []


def _main_valve_problem(view: RuleView, main: str, bypass_valves: list[str]) -> str | None:
    """A valve on the exchanger's own branch needs a partner valve on the bypass, same sensor."""
    items = _heat_transfer_items_beside(view, main)
    point = _controlled_point(view.graph, main)
    partners = [
        valve for valve in bypass_valves
        if bypassed_items(view, valve) & items and _controlled_point(view.graph, valve) == point
    ]  # fmt: skip
    if point and partners:
        return None
    return (
        f"expected the main-branch valve {main} to be driven by a temperature loop and to pair "
        "with a bypass valve of the same loop point around the same exchanger, found "
        f"{len(partners)} partners (measuring {point})"
    )


def check_hx_bypass_variant(view: RuleView) -> CheckResult:
    """TOG322-HX-BYPASS-VARIANT: a bypass valve alone, or paired with one on the main branch."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    # rule TOG322-HX-BYPASS-VARIANT: bypass valve alone, or valves on both branches (Toghraei p.322)
    bypass_valves = temperature_bypass_valves(view)
    mains = sorted(n for n, role in view.roles.items() if role == HX_MAIN_VALVE_ROLE)
    violations = [
        Violation(rule_id="TOG322-HX-BYPASS-VARIANT", node_id=main, detail=problem)
        for main in mains
        if (problem := _main_valve_problem(view, main, bypass_valves))
    ]
    return CheckResult(checked=len(bypass_valves), violations=tuple(violations))


# ---- TOG207-HX-NO-ISOLATION --------------------------------------------------------------------


def _is_trim_run(view: RuleView, run: list[str]) -> bool:
    """A run with a safety valve, or ending in a cap, funnel or vent, is a branch (a trim)."""
    classes = [str(view.graph.nodes[n]["node_class"]) for n in run]
    return classes[-1] in _TRIM_END_CLASSES or any(c.endswith("SafetyValve") for c in classes)


def _is_isolation_valve(graph: nx.DiGraph[str], node: str) -> bool:
    """A block valve; a ball or butterfly body that a controller throttles is a control valve."""
    return graph.nodes[node]["node_class"] in _BLOCK_VALVES and not is_control_valve(graph, node)


@dataclass(frozen=True)
class NozzleRuns:
    """The runs of pipe on an exchanger's nozzles, sorted by what they carry."""

    process_in: list[list[str]]
    process_out: list[list[str]]
    utility: list[list[str]]


def _is_relief_run(view: RuleView, run: list[str]) -> bool:
    return any(view.roles.get(n) == _PSV_INLET_ROLE for n in run)


def nozzle_runs(view: RuleView, exchanger: str) -> NozzleRuns:
    """Split the single-file pipe on the exchanger's nozzles into process and utility runs.

    Vent and drain branches, relief branches and flare (FL) runs belong to other rules and
    are left out. Also read by the pressure-safety check (T10) to find utility-side blocks.
    """
    piping, graph = view.piping, view.graph
    found = NozzleRuns(process_in=[], process_out=[], utility=[])
    for up, neighbours in (
        (True, piping.predecessors(exchanger)),
        (False, piping.successors(exchanger)),
    ):
        for start in neighbours:
            run = _run_to_junction(piping, graph, start, up)
            if _is_trim_run(view, run) or _is_relief_run(view, run):
                continue
            ends = (start, exchanger) if up else (exchanger, start)  # the pipe at the nozzle
            service = service_of(graph, *ends)
            if service in UTILITY_SERVICES or service == _FLARE_HEADER:
                found.utility.append(run)
            else:
                (found.process_in if up else found.process_out).append(run)
    return found


def _holds_block(view: RuleView, run: list[str]) -> bool:
    return any(_is_isolation_valve(view.graph, n) for n in run)


def has_utility_side_block(view: RuleView, exchanger: str) -> bool:
    """True when a block valve stands on a utility nozzle (the usual supply isolation)."""
    return any(_holds_block(view, run) for run in nozzle_runs(view, exchanger).utility)


def _is_process_isolated(view: RuleView, exchanger: str) -> bool:
    """Every process inlet run and every process outlet run holds a block valve."""
    runs = nozzle_runs(view, exchanger)
    sides = (runs.process_in, runs.process_out)
    return all(side and all(_holds_block(view, run) for run in side) for side in sides)


def _line_parts(view: RuleView, neighbours: Iterable[str], up: bool) -> set[str]:
    """The pipe parts of the lines that touch an item: each neighbour and what lies beyond it."""
    piping, graph = view.piping, view.graph
    parts: set[str] = set()
    for node in neighbours:
        if graph.nodes[node]["node_class"] not in EQUIPMENT_CLASSES:
            parts |= {node, *reach(piping, graph, node, up)[0]}
    return parts


def _open_pipe_graph(view: RuleView) -> nx.DiGraph[str]:
    """The piping without equipment, control valves and station bypasses: hand pipe only."""
    graph = view.graph
    open_pipe = [
        n for n in view.piping
        if graph.nodes[n]["node_class"] not in EQUIPMENT_CLASSES
        and not is_control_valve(graph, n)
        and view.roles.get(n) not in _STATION_BYPASS_ROLES
    ]  # fmt: skip
    return view.piping.subgraph(open_pipe)


def _manual_bypass(view: RuleView, exchanger: str) -> bool:
    """True when pipe alone leads around the exchanger with no control valve on the way.

    Start from the parts that feed the exchanger and the parts it feeds; a path between the two
    that crosses no equipment skips the exchanger. A control valve on it (the temperature bypass
    of TOG320) makes it a control branch, not an isolation bypass.
    """
    piping = view.piping
    feeding = _line_parts(view, piping.predecessors(exchanger), up=True)
    fed = _line_parts(view, piping.successors(exchanger), up=False)
    around = view.cached("open_pipe_graph", lambda: _open_pipe_graph(view))
    # `n in around` is O(1); `set(around)` would walk the whole plant for every exchanger
    starts = {n for n in feeding if n in around}
    ends = {n for n in fed if n in around}
    return any(nx.has_path(around, start, end) for start in starts for end in ends - {start})


def _isolation_problem(view: RuleView, exchanger: str) -> str | None:
    if _is_process_isolated(view, exchanger):
        return "block valves on every process inlet and outlet, so the exchanger can be shut in"
    if _manual_bypass(view, exchanger):
        return "a bypass without a control valve around the process side of the exchanger"
    return None


def check_hx_no_isolation(view: RuleView) -> CheckResult:
    """TOG207-HX-NO-ISOLATION: the process side is not isolated on both sides, has no hand bypass.

    Isolation is company policy (p.207), so v2.2 follows the "none" policy; a spare or a cleaning
    system would excuse it. Utility-side blocks are outside the rule and only counted.
    """
    # rule TOG207-HX-NO-ISOLATION: no isolation on an exchanger's process side (Toghraei 2019 p.207)
    spared = {n for record in view.generated.record.spare_sets for n in record.node_ids}
    graph = view.graph
    exchangers = sorted(
        n for n, d in graph.nodes(data=True) if d["node_class"] in EXCHANGER_CLASSES
    )
    violations = [
        Violation(rule_id="TOG207-HX-NO-ISOLATION", node_id=exchanger, detail=problem)
        for exchanger in exchangers
        if exchanger not in spared and (problem := _isolation_problem(view, exchanger))
    ]
    exceptions = {
        "has_spare": sum(e in spared for e in exchangers),
        "utility_side_block": sum(has_utility_side_block(view, e) for e in exchangers),
    }
    exceptions = {code: count for code, count in exceptions.items() if count}
    return CheckResult(checked=len(exchangers), violations=tuple(violations), exceptions=exceptions)


# ---- TOG326-STEAM-CONDENSATE -------------------------------------------------------------------


def _steam_heaters(view: RuleView) -> list[str]:
    """Exchangers a steam pipe feeds directly."""
    piping = view.piping
    return sorted(
        n
        for n, d in view.graph.nodes(data=True)
        if d["node_class"] in EXCHANGER_CLASSES
        and any(service_of(view.graph, a, n) in STEAM_SERVICES for a in piping.predecessors(n))
    )


def _condensate_mode(view: RuleView, heater: str) -> str | None:
    """How the heater's condensate line ends: `trap`, `trap_station`, `drain_pot`, or None."""
    piping, graph = view.piping, view.graph
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
