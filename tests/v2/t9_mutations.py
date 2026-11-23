"""Plants broken on purpose, one break per T9 rule (design 3.3 (b)): graph surgery on a `RuleView`.

Not a test module (no `test_` prefix). Each `break_*` takes a v2.2 view and returns a copy with one
change that the rule forbids, plus the id of the node it changed so the test can insist the
violation names it. The input view is never modified.
"""

from __future__ import annotations

from dataclasses import replace

import networkx as nx

from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.rules.checks_v21_plant import flow, reach
from plantgraph.benchmark.v2.rules.control_graph import (
    FLOW,
    LEVEL,
    LIQUID_SERVICES,
    TEMPERATURE,
    UTILITY_SERVICES,
    control_loops,
    controllers_on,
    drives_speed,
    is_control_valve,
    routes_between_containers,
    sensed_items,
    service_of,
)
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation

Broken = tuple[RuleView, str]  # the broken view and the node the break is about
_SEND_TO = Relation.SEND_TO.value
_LINE = {"relation": _SEND_TO, "line_number": "x", "fluid_code": "P"}


# ---- graph surgery -----------------------------------------------------------------------------
def _copy(view: RuleView) -> tuple[nx.DiGraph[str], dict[str, str]]:
    return view.graph.copy(), dict(view.roles)


def _splice_into_pipe(
    graph: nx.DiGraph[str], before: str, after: str, node: str, **attrs: str
) -> None:
    """Put a new part `node` on the pipe between `before` and `after`."""
    data = dict(graph.edges[before, after])
    graph.remove_edge(before, after)
    graph.add_node(node, unit_id="1", **attrs)
    graph.add_edge(before, node, **data)
    graph.add_edge(node, after, **data)


def _first_successor(graph: nx.DiGraph[str], node: str) -> str:
    return sorted(flow(graph).successors(node))[0]


def _add_control_valve(graph: nx.DiGraph[str], before: str, after: str, controller: str) -> str:
    """Put a new control valve, driven by `controller`, on the pipe; returns its id."""
    valve, actuator = f"mut-valve-{before}", f"mut-actuator-{before}"
    _splice_into_pipe(graph, before, after, valve, node_class="GlobeValve", tag="FV-99999")
    graph.add_node(actuator, node_class="ActuatingFunction", unit_id="1")
    graph.add_edge(controller, actuator, relation=Relation.SEND_SIGNAL_TO.value)
    graph.add_edge(actuator, valve, relation=Relation.CONTROL.value)
    return valve


def _with_graph(
    view: RuleView, graph: nx.DiGraph[str], roles: dict[str, str] | None = None
) -> RuleView:
    return replace(view, graph=graph, roles=view.roles if roles is None else roles)


# ---- TOG271, TOG267, TOG295, TOG270 ------------------------------------------------------------
def break_one_cv_liquid(view: RuleView) -> Broken:
    """A second control valve straight after one that already sits between two vessels."""
    graph, _ = _copy(view)
    for route in routes_between_containers(view):
        valves = [n for n in route[1:-1] if is_control_valve(graph, n)]
        liquid = all(
            service_of(graph, a, b) in LIQUID_SERVICES
            for a, b in zip(route, route[1:], strict=False)
        )
        if valves and liquid:
            valve = valves[0]
            controller = next(c.controller for c in control_loops(view) if c.valve == valve)
            new = _add_control_valve(graph, valve, _first_successor(graph, valve), controller)
            return _with_graph(view, graph), new
    raise AssertionError("no liquid route with a control valve found to break")


def break_fe_upstream_fv(view: RuleView) -> Broken:
    """Move a flow element from in front of its valve to behind it."""
    graph, _ = _copy(view)
    piping = flow(graph)
    for loop in (c for c in control_loops(view) if c.variable == FLOW):
        elements = sensed_items(graph, loop.controller)
        if len(elements) != 1 or graph.nodes[elements[0]]["node_class"] in EQUIPMENT_CLASSES:
            continue
        (element,) = elements
        before, after = list(piping.predecessors(element)), list(piping.successors(element))
        if len(before) != 1 or len(after) != 1 or after[0] != loop.valve:
            continue  # only an element directly in front of its valve can be swapped cleanly
        data = dict(graph.edges[element, loop.valve])
        outlet = _first_successor(graph, loop.valve)
        graph.remove_node(element)
        graph.add_edge(before[0], loop.valve, **data)
        graph.add_node(element, node_class="FlowMeasuringElement", unit_id="1", tag="FE-99999")
        out_data = dict(graph.edges[loop.valve, outlet])
        graph.remove_edge(loop.valve, outlet)
        graph.add_edge(loop.valve, element, **out_data)
        graph.add_edge(element, outlet, **out_data)
        sensor = next(
            t
            for _, t, d in view.graph.out_edges(element, data=True)
            if d["relation"] == "measured_by"
        )
        graph.add_edge(element, sensor, relation=Relation.MEASURED_BY.value)
        return _with_graph(view, graph), loop.valve
    raise AssertionError("no flow loop with its element directly in front of the valve found")


def _a_vessel_with_a_level_loop(view: RuleView) -> str:
    for node, data in sorted(view.graph.nodes(data=True)):
        if data["node_class"] in ("PressureVessel", "ProcessColumn") and controllers_on(
            view.graph, node, LEVEL
        ):
            return node
    raise AssertionError("no vessel with a level loop found")


def break_inventory_no_loop(view: RuleView) -> Broken:
    """Remove the level controller of a vessel: its liquid inventory is left uncontrolled."""
    graph, _ = _copy(view)
    vessel = _a_vessel_with_a_level_loop(view)
    graph.remove_nodes_from(controllers_on(graph, vessel, LEVEL))
    return _with_graph(view, graph), vessel


def break_inventory_two_loops(view: RuleView) -> Broken:
    """Give a vessel a second level controller on the same transmitter: two loops fight."""
    graph, _ = _copy(view)
    vessel = _a_vessel_with_a_level_loop(view)
    (controller, *_) = controllers_on(graph, vessel, LEVEL)
    (sensor,) = [
        s for s, _, d in graph.in_edges(controller, data=True) if d["relation"] == "send_signal_to"
    ]
    graph.add_node("mut-second-lic", node_class="ProcessControlFunction", measured_variable=LEVEL)
    graph.add_edge(sensor, "mut-second-lic", relation=Relation.SEND_SIGNAL_TO.value)
    return _with_graph(view, graph), vessel


def _pump_route_with_a_flow_valve(view: RuleView) -> tuple[str, str]:
    """(pump, valve): a pump with no variable speed and a flow or level valve on its discharge."""
    piping, graph = flow(view.graph), view.graph
    loops = {c.valve: c for c in control_loops(view) if c.variable in (FLOW, LEVEL)}
    for pump, data in sorted(graph.nodes(data=True)):
        if data["node_class"] != "CentrifugalPump" or drives_speed(graph, pump):
            continue
        reached = reach(piping, graph, pump, up=False)[0]
        valves = sorted(
            n for n in reached if n in loops and view.roles.get(n) == "control_valve_body"
        )
        if valves:
            return pump, valves[0]
    raise AssertionError("no centrifugal pump with a flow or level valve on its discharge found")


def break_pump_flow_uncontrolled(view: RuleView) -> Broken:
    """Cut the actuator of the valve that fixes a pump's flow: the discharge has no flow device."""
    graph, _ = _copy(view)
    pump, valve = _pump_route_with_a_flow_valve(view)
    actuators = [s for s, _, d in graph.in_edges(valve, data=True) if d["relation"] == "control"]
    graph.remove_nodes_from(actuators)
    return _with_graph(view, graph), pump


def break_pump_flow_twice(view: RuleView) -> Broken:
    """A second flow valve in series on the same discharge: the flow is fixed twice."""
    graph, _ = _copy(view)
    pump, valve = _pump_route_with_a_flow_valve(view)
    controller = next(c.controller for c in control_loops(view) if c.valve == valve)
    _add_control_valve(graph, valve, _first_successor(graph, valve), controller)
    return _with_graph(view, graph), pump


# ---- TOG320, TOG207, TOG326 --------------------------------------------------------------------
def break_hx_nontarget(view: RuleView) -> Broken:
    """Relabel the pipe of a utility temperature valve as a process line: it throttles in series."""
    graph, _ = _copy(view)
    for loop in (c for c in control_loops(view) if c.variable == TEMPERATURE):
        piping = flow(graph)
        edges = [*piping.in_edges(loop.valve), *piping.out_edges(loop.valve)]
        if edges and all(service_of(graph, a, b) in UTILITY_SERVICES for a, b in edges):
            for a, b in edges:
                graph.edges[a, b]["fluid_code"] = "P"
            return _with_graph(view, graph), loop.valve
    raise AssertionError("no temperature valve on a utility line found")


def _clean_exchanger(view: RuleView, violating: set[str]) -> str:
    """The first exchanger the check has no complaint about, with a pipe part in front of it."""
    piping = flow(view.graph)
    for node, data in sorted(view.graph.nodes(data=True)):
        if data["node_class"] != "TubularHeatExchanger" or node in violating or node not in piping:
            continue
        if [p for p in piping.predecessors(node) if _is_pipe_part(view.graph, p)]:
            return node
    raise AssertionError("no clean exchanger found")


def _is_pipe_part(graph: nx.DiGraph[str], node: str) -> bool:
    return bool(graph.nodes[node]["node_class"] not in EQUIPMENT_CLASSES)


def break_hx_isolation_valve(view: RuleView, violating: set[str]) -> Broken:
    """A gate valve straight in front of an exchanger: it can now be isolated."""
    graph, _ = _copy(view)
    exchanger = _clean_exchanger(view, violating)
    before = next(
        p
        for p in flow(graph).predecessors(exchanger)
        if graph.nodes[p]["node_class"] not in EQUIPMENT_CLASSES
    )
    _splice_into_pipe(
        graph, before, exchanger, "mut-block", node_class="GateValve", tag="GTV-99999"
    )
    return _with_graph(view, graph), exchanger


def break_hx_bypass(view: RuleView, violating: set[str]) -> Broken:
    """A plain valve in a pipe that leads round an exchanger, from its inlet line to its outlet."""
    graph, _ = _copy(view)
    exchanger = _clean_exchanger(view, violating)
    piping = flow(graph)
    inlet = next(
        p
        for p in piping.predecessors(exchanger)
        if graph.nodes[p]["node_class"] not in EQUIPMENT_CLASSES
    )
    outlets = [
        q
        for q in piping.successors(exchanger)
        if piping.out_degree(q) > 0 and graph.nodes[q]["node_class"] not in EQUIPMENT_CLASSES
    ]
    graph.add_node("mut-bypass", node_class="GlobeValve", tag="GV-99999", unit_id="1")
    graph.add_edge(inlet, "mut-bypass", **_LINE)
    graph.add_edge("mut-bypass", outlets[0], **_LINE)
    return _with_graph(view, graph), exchanger


def break_steam_condensate(view: RuleView) -> Broken:
    """Take every trap, trap station and condensate-pot level loop away from the steam heaters."""
    graph, roles = _copy(view)
    traps = [n for n, d in graph.nodes(data=True) if d["node_class"] == "SteamTrap"]
    pots = [n for n, r in view.roles.items() if r == "condensate_drain_pot"]
    pot_loops = [c for pot in pots for c in controllers_on(graph, pot, LEVEL)]
    graph.remove_nodes_from(traps + pot_loops)
    roles = {n: r for n, r in roles.items() if r != "trap_tee_in"}
    return _with_graph(view, graph, roles), "(all steam heaters)"


# ---- TOG224, TOG24, PLT-STREAM-CLOSURE ---------------------------------------------------------
def break_psv_pipe(view: RuleView) -> Broken:
    """A check valve between a vessel and its safety valve."""
    graph, _ = _copy(view)
    psv = next(
        n for n, d in sorted(graph.nodes(data=True)) if d["node_class"].endswith("SafetyValve")
    )
    before = sorted(flow(graph).predecessors(psv))[0]
    _splice_into_pipe(
        graph, before, psv, "mut-check", node_class="SwingCheckValve", tag="CHV-99999"
    )
    return _with_graph(view, graph), psv


def _with_unit(view: RuleView, index: int, **changes: object) -> RuleView:
    plan = view.plan
    units = list(plan.units)
    units[index] = units[index].model_copy(update=changes)
    generated = replace(view.generated, plan=plan.model_copy(update={"units": tuple(units)}))
    return replace(view, generated=generated)


def break_visiting_stream(view: RuleView) -> Broken:
    """Move the first inline part of a line to a sheet where neither end of the line is drawn."""
    for index, unit in enumerate(view.plan.units):
        for line in unit.instance.plan.lines:
            if line.items and line.src_id is not None and line.dst_id is not None:
                moved = {**unit.sheets.sheet_of, line.items[0].node_id: "99:9"}
                sheets = unit.sheets.model_copy(update={"sheet_of": moved})
                return _with_unit(view, index, sheets=sheets), line.items[0].node_id
    raise AssertionError("no line with items and two end items found")


def break_stream_closure(view: RuleView) -> Broken:
    """Cut a process line's sink: it now ends open at a plain pipe part."""
    for index, unit in enumerate(view.plan.units):
        for position, line in enumerate(unit.instance.plan.lines):
            if _can_be_left_open(view, line):
                lines = list(unit.instance.plan.lines)
                lines[position] = line.model_copy(update={"dst_id": None})
                plan = unit.instance.plan.model_copy(update={"lines": tuple(lines)})
                instance = unit.instance.model_copy(update={"plan": plan})
                return _with_unit(view, index, instance=instance), line.items[-1].node_id
    raise AssertionError("no process line found to leave open")


def _can_be_left_open(view: RuleView, line: LineSpec) -> bool:
    kind = view.generated.record.stream_kind.get(line.line_number)
    end = line.items[-1].node_class if line.items else ""
    plain_end = end in ("PipeTee", "GateValve", "ButterflyValve", "BallValve", "GlobeValve")
    return bool(
        line.items
        and line.src_id
        and line.dst_id
        and plain_end
        and kind
        and kind.value == "process"
    )
