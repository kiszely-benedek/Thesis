"""Checks of four sampled alternatives of v2.2 (Toghraei 2019): TOG34, TOG122, TOG173, TOG214.

An **alternative** is a rule that allows several arrangements: the generator draws one for each
item (or train) and the check accepts exactly the arrangements the book names. Each check below
reports `checked=0` on a v2.1 plant and on a v2.2 plant with the handbook off, because those
plants draw the old single arrangement and their goldens are pinned.

Terms. A **battery limit** is where a unit meets the rest of the plant; a **blind** is a plate
that closes a line. A **pressure-control (PV) station** is a pressure control valve with a block
valve on each side and, usually, a **bypass** line for hand operation. A **reducer** narrows the
pipe and an **enlarger** widens it again. A **flame-failure trip** shuts the furnace's fuel valve
when the flame sensor sees no flame.
"""

from __future__ import annotations

import re
from collections import Counter

from plantgraph.benchmark.v2.rules.checks_pumps import nodes_with_role, pumps_of_classes
from plantgraph.benchmark.v2.rules.checks_v21_plant import CENTRIFUGAL_PUMP, flow, reach
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.trims_valves import FUEL_SWITCHING_ROLES, PRESSURE_LETTER
from plantgraph.graph.schema import Relation

_NOT_APPLICABLE = CheckResult(checked=0)


def _violation(rule_id: str, node: str, detail: str) -> Violation:
    return Violation(rule_id=rule_id, node_id=node, detail=detail)


# ---- TOG34-BL-ISOLATION ------------------------------------------------------------------------

_BLOCK, _BLIND, _CHECK = "battery_limit_block", "battery_limit_blind", "battery_limit_check"
#: the three arrangements of Toghraei p.34, as the roles of the blind and the parts just before it
_BATTERY_LIMIT_ARRANGEMENTS = (
    Counter([_BLIND]),
    Counter([_BLOCK, _BLIND]),
    Counter([_BLOCK, _CHECK, _BLIND]),
)


def _battery_limit_roles(view: RuleView, blind: str) -> Counter[str]:
    """The roles of the blind and of the battery-limit valves in the pipe run just before it."""
    piping = flow(view.graph)
    roles = Counter([_BLIND])
    node = blind
    while len(preds := list(piping.predecessors(node))) == 1:
        node = preds[0]
        if view.roles.get(node) not in (_BLOCK, _CHECK):
            break
        roles[view.roles[node]] += 1
    return roles


def check_battery_limit_variants(view: RuleView) -> CheckResult:
    """TOG34-BL-ISOLATION: a battery limit is a blind, valve and blind, or valve, blind, check."""
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    # rule TOG34-BL-ISOLATION: the battery-limit arrangements the book names (Toghraei 2019 p.34)
    blinds = nodes_with_role(view, view.graph.nodes, [_BLIND])
    violations = []
    for blind in blinds:
        roles = _battery_limit_roles(view, blind)
        if roles not in _BATTERY_LIMIT_ARRANGEMENTS:
            detail = (
                f"expected a blind, valve and blind, or valve, blind and check; found {dict(roles)}"
            )
            violations.append(_violation("TOG34-BL-ISOLATION", blind, detail))
    return CheckResult(checked=len(blinds), violations=tuple(violations))


# ---- TOG173-PUMP-REDUCERS ----------------------------------------------------------------------

_SUCTION_REDUCER, _DISCHARGE_ENLARGER = "pump_suction_reducer", "pump_discharge_enlarger"
_PUMP_CLASSES = (CENTRIFUGAL_PUMP, "ReciprocatingPump", "RotaryPump")


def _nozzle_parts(view: RuleView, pump: str) -> tuple[bool, bool]:
    """(has a suction reducer, has a discharge enlarger) next to the pump's nozzles."""
    piping = flow(view.graph)
    before = nodes_with_role(view, piping.predecessors(pump), [_SUCTION_REDUCER])
    after = nodes_with_role(view, piping.successors(pump), [_DISCHARGE_ENLARGER])
    return bool(before), bool(after)


def _reducer_problem(view: RuleView, pump: str) -> str | None:
    suction, discharge = _nozzle_parts(view, pump)
    if suction != discharge:
        return (
            "expected the suction reducer and the discharge enlarger together, found "
            f"suction reducer {suction}, discharge enlarger {discharge}"
        )
    if suction and view.graph.nodes[pump]["node_class"] != CENTRIFUGAL_PUMP:
        return "expected nozzle reducers on centrifugal pumps only"
    return None


def _set_problems(view: RuleView) -> list[Violation]:
    """The pumps of one installed set are identical, so they all have reducers or none does."""
    problems = []
    for record in view.generated.record.spare_sets:
        if len({_nozzle_parts(view, pump) for pump in record.node_ids}) > 1:
            detail = "expected the pumps of one spare set to share their nozzle reducers"
            problems.append(_violation("TOG173-PUMP-REDUCERS", record.node_ids[0], detail))
    return problems


def check_pump_reducers(view: RuleView) -> CheckResult:
    """TOG173-PUMP-REDUCERS: a centrifugal pump has reducer and enlarger together, or neither."""
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    # rule TOG173-PUMP-REDUCERS: suction reducer, discharge enlarger (Toghraei p.173–175)
    pumps = pumps_of_classes(view, _PUMP_CLASSES)
    violations = [
        _violation("TOG173-PUMP-REDUCERS", pump, problem)
        for pump in pumps
        if (problem := _reducer_problem(view, pump))
    ]
    centrifugal = pumps_of_classes(view, [CENTRIFUGAL_PUMP])
    return CheckResult(checked=len(centrifugal), violations=(*violations, *_set_problems(view)))


# ---- TOG122-PV-NO-BYPASS -----------------------------------------------------------------------

_UNIT_OF_NODE = re.compile(r"^u(\d+)-")
#: parts that may sit between a station's upstream block valve and its control valve
_STATION_INNER_ROLES = frozenset({"cv_reducer", "cv_drain_tee"})


def _station_block(view: RuleView, body: str) -> str | None:
    """The upstream block valve of the station around control valve `body`; None if it is bare."""
    piping = flow(view.graph)
    node = body
    while len(preds := list(piping.predecessors(node))) == 1:
        node = preds[0]
        if view.roles.get(node) == "cv_block_in":
            return node
        if view.roles.get(node) not in _STATION_INNER_ROLES:
            return None
    return None


def _pv_bodies(view: RuleView) -> list[str]:
    """The control valves tagged `PV-...`."""
    wanted = f"{PRESSURE_LETTER}V"
    bodies = nodes_with_role(view, view.graph.nodes, ["control_valve_body"])
    tags = {n: parse_tag(str(view.graph.nodes[n].get("tag") or "")) for n in bodies}
    return [n for n, parsed in tags.items() if parsed is not None and parsed.letters == wanted]


def _train_of(view: RuleView, node: str) -> int:
    match = _UNIT_OF_NODE.match(node)
    if match is None:
        raise ValueError(f"expected a node id with a unit prefix like 'u3-t12', got {node!r}")
    unit_no = int(match.group(1))
    return next(unit.train_no for unit in view.generated.record.units if unit.unit_no == unit_no)


def _has_bypass(view: RuleView, block: str) -> bool:
    """True when the station's block valve hangs off the tee that starts a bypass."""
    piping = flow(view.graph)
    return any(view.roles.get(pred) == "cv_tee_in" for pred in piping.predecessors(block))


def pv_stations_by_train(view: RuleView) -> dict[int, dict[bool, list[str]]]:
    """Train -> has a bypass -> the control valves of its pressure-control stations."""
    stations: dict[int, dict[bool, list[str]]] = {}
    for body in _pv_bodies(view):
        block = _station_block(view, body)
        if block is not None:  # a bare valve is not a station
            in_train = stations.setdefault(_train_of(view, body), {True: [], False: []})
            in_train[_has_bypass(view, block)].append(body)
    return stations


def check_pv_no_bypass(view: RuleView) -> CheckResult:
    """TOG122-PV-NO-BYPASS: within a train every pressure-control station has a bypass, or none."""
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    # rule TOG122-PV-NO-BYPASS: a company may give PV stations no bypass (Toghraei 2019 p.122)
    stations = pv_stations_by_train(view)
    violations = [
        _violation(
            "TOG122-PV-NO-BYPASS",
            split[False][0],
            f"expected train {train} to draw its PV stations all with or all without a bypass, "
            f"found {len(split[True])} with and {len(split[False])} without",
        )
        for train, split in sorted(stations.items())
        if split[True] and split[False]
    ]
    checked = sum(len(split[True]) + len(split[False]) for split in stations.values())
    return CheckResult(checked=checked, violations=tuple(violations))


# ---- TOG214-FUEL-SWITCHING-VALVES --------------------------------------------------------------

_FURNACE = "Furnace"


def _valve_problem(view: RuleView, valve: str) -> str | None:
    """Each switching valve has an actuator of its own, moving that valve alone."""
    graph = view.graph
    controlling = Relation.CONTROL.value
    actuators = [s for s, _, d in graph.in_edges(valve, data=True) if d["relation"] == controlling]
    if len(actuators) != 1:
        return f"expected one actuator on switching valve {valve}, found {len(actuators)}"
    moved = [
        t for _, t, d in graph.out_edges(actuators[0], data=True) if d["relation"] == controlling
    ]
    if moved != [valve]:
        return f"expected the actuator of {valve} to move only that valve, found {moved}"
    return None


def _fuel_problem(view: RuleView, furnace: str) -> str | None:
    upstream, _ = reach(flow(view.graph), view.graph, furnace, up=True)
    valves = nodes_with_role(view, upstream, FUEL_SWITCHING_ROLES)
    if len(valves) not in (1, 2):
        return f"expected one or two switching valves on the fuel line, found {len(valves)}"
    tags = [view.graph.nodes[v].get("tag") for v in valves]
    if len(set(tags)) != len(tags):
        return f"expected a number of its own on each switching valve, found {tags}"
    return next((problem for v in valves if (problem := _valve_problem(view, v))), None)


def check_fuel_switching_valves(view: RuleView) -> CheckResult:
    """TOG214-FUEL-SWITCHING-VALVES: a furnace's fuel line has one switching valve or two."""
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    # rule TOG214-FUEL-SWITCHING-VALVES: one switching valve, or two in series (Toghraei p.214)
    furnaces = sorted(n for n, d in view.graph.nodes(data=True) if d["node_class"] == _FURNACE)
    violations = [
        _violation("TOG214-FUEL-SWITCHING-VALVES", furnace, problem)
        for furnace in furnaces
        if (problem := _fuel_problem(view, furnace))
    ]
    return CheckResult(checked=len(furnaces), violations=tuple(violations))
