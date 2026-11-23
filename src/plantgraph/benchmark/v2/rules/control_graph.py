"""Reading control loops and containers off the oracle graph, shared by the plant-level checks.

Terms a reader outside process engineering needs. A **container** is a vessel, tank or column: a
place where liquid or gas is held. A **control valve** is a valve a controller throttles to hold a
quantity (flow, level, pressure, temperature); an on-off valve is only open or shut and does not
count. A **loop** is sensor, controller and valve working together. A **service** is the fluid code
printed on a pipe (`P` process liquid, `PG` process gas, `LPS` low-pressure steam, ...).

Everything here reads the graph the plan was written to (`RuleView.graph`) and the plan's roles.
No function raises on an unusual plant; it just finds fewer loops.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import networkx as nx

from plantgraph.benchmark.v2.rules.checks_v21_plant import flow, reach
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import CONTROL_VALVE_BODY_CLASSES, EQUIPMENT_CLASSES, Relation

#: services whose pipes are full of liquid; the others (gas, steam, flare) are not
LIQUID_SERVICES = frozenset({"P", "CD", "CWS", "CWR"})
#: services of a utility network: steam, cooling water, condensate, fuel gas
UTILITY_SERVICES = frozenset({"LPS", "MPS", "CWS", "CWR", "CD", "FG"})
STEAM_SERVICES = frozenset({"LPS", "MPS"})
GAS_SERVICES = frozenset({"PG", "FG"})

CONTAINER_CLASSES = frozenset(
    {
        "Tank",
        "PressureVessel",
        "ProcessColumn",
        "Vessel",
        "GravitationalSeparator",
        "ElectricalSeparator",
        "ScrubbingSeparator",
        "Separator",
    }
)
#: exchangers proper; an air cooler or furnace also moves heat but has no steam or spare to speak of
EXCHANGER_CLASSES = frozenset(
    {"TubularHeatExchanger", "HeatExchanger", "PlateHeatExchanger", "SpiralHeatExchanger"}
)
#: equipment through which a stream is heated or cooled: a bypass around one of these bypasses it
HEAT_TRANSFER_CLASSES = EXCHANGER_CLASSES | {"AirCoolingSystem", "Furnace", "Heater"}
#: containers whose job needs a held pressure (Toghraei p.270 rule 8: flash drums, separators, ...)
PRESSURE_DEPENDENT_ROLES = frozenset({"flash_drum", "separator", "suction_ko_drum"})
#: roles of containers that run liquid-full: no free surface, so they count as pipe (TOG p.271)
FLOODED_CONTAINER_ROLES = frozenset({"reactor"})
#: a controller's measured variable, as the graph stores it
FLOW, LEVEL, PRESSURE, TEMPERATURE = "F", "L", "P", "T"
#: a hand control valve (HCV) is throttled by an operator, not by a loop; its tag starts so
_HAND_CONTROL_LETTERS = ("HV", "HCV")


@dataclass(frozen=True)
class ControlLoop:
    """One loop that moves a control valve."""

    valve: str
    controller: str
    variable: str  # FLOW, LEVEL, PRESSURE, TEMPERATURE or `U` (multivariable)


def service_of(graph: nx.DiGraph[str], upstream: str, downstream: str) -> str:
    """The fluid code of the pipe between two neighbouring parts."""
    return str(graph.edges[upstream, downstream].get("fluid_code", ""))


def is_container(view: RuleView, node: str) -> bool:
    """True for a vessel, tank or column that has a free liquid or gas space."""
    return (
        view.graph.nodes[node]["node_class"] in CONTAINER_CLASSES
        and view.roles.get(node) not in FLOODED_CONTAINER_ROLES
    )


def _sources(graph: nx.DiGraph[str], node: str, relation: Relation) -> list[str]:
    """The nodes with an edge of `relation` into `node`, sorted."""
    edges = graph.in_edges(node, data=True)
    return sorted(s for s, _, data in edges if data["relation"] == relation.value)


def _targets(graph: nx.DiGraph[str], node: str, relation: Relation) -> list[str]:
    """The nodes `node` has an edge of `relation` to, sorted."""
    edges = graph.out_edges(node, data=True)
    return sorted(t for _, t, data in edges if data["relation"] == relation.value)


def _is_controller(graph: nx.DiGraph[str], node: str) -> bool:
    return bool(graph.nodes[node]["node_class"] == "ProcessControlFunction")


def controller_of(graph: nx.DiGraph[str], valve: str) -> str | None:
    """The controller that drives `valve` through its actuator, or None (on-off valve, manual)."""
    for actuator in _sources(graph, valve, Relation.CONTROL):
        for source in _sources(graph, actuator, Relation.SEND_SIGNAL_TO):
            if _is_controller(graph, source):
                return source
    return None


def is_control_valve(graph: nx.DiGraph[str], node: str) -> bool:
    """True for a throttling valve: driven by a controller, or a hand control valve (HCV)."""
    data = graph.nodes[node]
    if data["node_class"] not in CONTROL_VALVE_BODY_CLASSES:
        return False
    is_hand_valve = str(data.get("tag", "")).startswith(_HAND_CONTROL_LETTERS)
    return controller_of(graph, node) is not None or is_hand_valve


def loop_of(graph: nx.DiGraph[str], valve: str) -> ControlLoop | None:
    """The loop behind a control valve; None for an HCV, a speed-driven pump or any other node."""
    controller = controller_of(graph, valve)
    if controller is None or graph.nodes[valve]["node_class"] not in CONTROL_VALVE_BODY_CLASSES:
        return None
    variable = str(graph.nodes[controller].get("measured_variable", ""))
    return ControlLoop(valve=valve, controller=controller, variable=variable)


def control_loops(view: RuleView) -> list[ControlLoop]:
    """Every loop-driven control valve of the plant, sorted by valve id."""
    loops = (loop_of(view.graph, node) for node in sorted(view.graph.nodes))
    return [loop for loop in loops if loop is not None]


def sensed_items(graph: nx.DiGraph[str], controller: str) -> list[str]:
    """What the controller's sensors measure: the equipment or pipe part each sensor sits on."""
    items: list[str] = []
    for sensor in _sources(graph, controller, Relation.SEND_SIGNAL_TO):
        items += _sources(graph, sensor, Relation.MEASURED_BY)
    return sorted(set(items))


def controllers_on(graph: nx.DiGraph[str], item: str, variable: str) -> list[str]:
    """The controllers of `variable` whose sensor measures `item`; a cascade master counts."""
    found = {
        controller
        for sensor in _targets(graph, item, Relation.MEASURED_BY)
        for controller in graph.successors(sensor)
        if _is_controller(graph, controller)
        and graph.nodes[controller].get("measured_variable") == variable
    }
    return sorted(found)


def sensors_on(graph: nx.DiGraph[str], item: str, variable: str) -> list[str]:
    """The sensors of `variable` that measure `item` (a level transmitter on a tank, say)."""
    sensors = _targets(graph, item, Relation.MEASURED_BY)
    return [s for s in sensors if graph.nodes[s].get("measured_variable") == variable]


def drives_speed(graph: nx.DiGraph[str], machine: str) -> bool:
    """True when a controller sets the machine's speed (a variable-speed drive, not start-stop)."""
    return any(
        _is_controller(graph, source)
        for actuator in _sources(graph, machine, Relation.CONTROL)
        for source in _sources(graph, actuator, Relation.SEND_SIGNAL_TO)
    )


# ---- bypasses around heat-transfer items -------------------------------------------------------


def _item_down_the_branch(view: RuleView, start: str) -> str:
    """The first equipment item along single-file pipe from `start`, else the last part reached.

    A valve between a tee and the exchanger (the main-branch valve of TOG322) is walked past.
    """
    piping, graph = flow(view.graph), view.graph
    node = start
    while graph.nodes[node]["node_class"] not in EQUIPMENT_CLASSES:
        following = list(piping.successors(node))
        if len(following) != 1:
            break
        node = following[0]
    return node


def bypassed_items(view: RuleView, valve: str) -> set[str]:
    """The exchangers and heaters the branch of `valve` skips (none: it is not on a bypass).

    An item is skipped when a branch from a part before the valve leads to it and returns to a part
    after the valve.
    """
    piping, graph = flow(view.graph), view.graph
    before, _ = reach(piping, graph, valve, up=True)
    after, _ = reach(piping, graph, valve, up=False)
    skipped: set[str] = set()
    for part in before:
        for branch in piping.successors(part):
            item = _item_down_the_branch(view, branch)
            is_heater = graph.nodes[item]["node_class"] in HEAT_TRANSFER_CLASSES
            if is_heater and any(back in after for back in piping.successors(item)):
                skipped.add(item)
    return skipped


def split_valves(view: RuleView) -> frozenset[str]:
    """The valves of a temperature split around a heat-transfer item (TOG p.321-322).

    That is every temperature valve that measures the same point as a valve on a bypass: the bypass
    valve alone, or the pair of TOG322 (bypass valve plus main-branch valve, two controllers on one
    outlet sensor). They set how the flow divides between the two branches, not how much flows, so
    they do not throttle the line.
    """
    by_point: dict[tuple[str, ...], list[str]] = {}
    for loop in control_loops(view):
        point = tuple(sensed_items(view.graph, loop.controller))
        if loop.variable == TEMPERATURE and point:  # no sensor, no known split partner
            by_point.setdefault(point, []).append(loop.valve)
    return frozenset(
        valve
        for valves in by_point.values()
        if any(bypassed_items(view, valve) for valve in valves)
        for valve in valves
    )


# ---- routes along the piping -------------------------------------------------------------------


def routes_from(
    piping: nx.DiGraph[str], start: str, is_end: Callable[[str], bool]
) -> list[tuple[str, ...]]:
    """Every simple route from `start` with the flow to a node where `is_end` holds.

    A route is the tuple of nodes from `start` to that end, both included. A route stops at its end
    and is dropped when the pipe runs out first (an open end). Branches in parallel give separate
    routes; no node repeats within one route (bar a return to `start`), so a loop ends.
    """
    found: list[tuple[str, ...]] = []
    stack: list[tuple[str, ...]] = [(start,)]
    while stack:
        path = stack.pop()
        for following in piping.successors(path[-1]):
            if is_end(following):  # may be `start` itself: a recycle returns to its own vessel
                found.append((*path, following))
            elif following not in path:
                stack.append((*path, following))
    return found


def routes_between_containers(view: RuleView) -> list[tuple[str, ...]]:
    """Every pipe route from a container to the next one; flooded items and pumps count as pipe."""
    piping = flow(view.graph)
    starts = [n for n in sorted(piping) if is_container(view, n)]
    found = (routes_from(piping, start, lambda n: is_container(view, n)) for start in starts)
    return [route for routes in found for route in routes]
