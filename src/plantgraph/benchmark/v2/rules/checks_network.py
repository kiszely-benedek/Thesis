"""Checks of the network rules (Toghraei 2019 pp.32-34, 141, 360): where relief and drains go.

A **network** is a pipe system the whole plant shares (the flare header, the closed drain, a
utility main). On a v2.2 plant its header is drawn on its own network sheets, and each process
sheet reaches it through one connector per service (`network_units.py`). These checks follow the
pipes of the oracle graph from a process part to the header tee of the right service, so they
fail if a tie-in is missing, goes to the wrong network, or is cut.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

import networkx as nx

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.hidden_state import FluidClass, PressureLevel
from plantgraph.benchmark.v2.network_models import (
    FLUID_CLASS_OF_SERVICE,
    SERVICE_DIRECTION,
    NetworkUnit,
    TieDirection,
)
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.rules.control_graph import service_of
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.trims_valves import BATTERY_LIMIT_ROLES

_NOT_APPLICABLE = CheckResult(checked=0)
_DRAIN_VALVE_ROLE = re.compile(r"_drain_valve$")
_HEADER_TEE = "header_tee"
_FLARE_ROLES = frozenset({"psv", "psv_outlet_block", "compressor_discharge_psv"})
_BLEED_ROLE = "dbb_bleed_valve"


def _violation(rule_id: str, node: str, detail: str) -> Violation:
    return Violation(rule_id=rule_id, node_id=node, detail=detail)


def _networks(view: RuleView) -> tuple[NetworkUnit, ...]:
    return view.plan.network_units


def _header_tees(view: RuleView) -> dict[str, frozenset[str]]:
    """Service -> every header tee of that service, over all trains."""

    def build() -> dict[str, frozenset[str]]:
        found: dict[str, set[str]] = defaultdict(set)
        for unit in _networks(view):
            found[unit.service] |= {n for n, r in unit.plan.roles.items() if r == _HEADER_TEE}
        return {service: frozenset(nodes) for service, nodes in found.items()}

    return view.cached("header_tees", build)


def _reaches(view: RuleView, node: str, targets: Iterable[str], *, downstream: bool) -> bool:
    """True when one of `targets` is on a pipe path from `node` (with the flow, or against it)."""
    reached = nx.descendants(view.piping, node) if downstream else nx.ancestors(view.piping, node)
    return not reached.isdisjoint(targets)


def _applies(view: RuleView) -> bool:
    return view.handbook_enabled and bool(_networks(view))


# ---- TOG32-NETWORK-SHEETS ----------------------------------------------------------------------


def check_network_sheets(view: RuleView) -> CheckResult:
    """TOG32-NETWORK-SHEETS: a PSV outlet or a fuel-gas bleed continues on the flare sheet."""
    if not _applies(view):
        return _NOT_APPLICABLE
    # rule TOG32-NETWORK-SHEETS: relief lines continue on network sheets (Toghraei 2019 p.32–34)
    flare = _header_tees(view).get("FL", frozenset())
    reliefs = sorted(n for n in view.piping if _is_relief_outlet(view, n))
    violations = [
        _violation(
            "TOG32-NETWORK-SHEETS",
            node,
            f"expected the relief outlet {node} to reach a flare header tee, found none",
        )
        for node in reliefs
        if not _reaches(view, node, flare, downstream=True)
    ]
    return CheckResult(checked=len(reliefs), violations=tuple(violations))


def _is_relief_outlet(view: RuleView, node: str) -> bool:
    """A part of a flare line that ends the relief path: a PSV or its outlet block, or a bleed."""
    role = view.roles.get(node)
    if role == _BLEED_ROLE:
        return True
    if role not in _FLARE_ROLES:
        return False
    after = list(view.piping.successors(node))
    before = list(view.piping.predecessors(node))
    services = {service_of(view.graph, node, n) for n in after} | {
        service_of(view.graph, n, node) for n in before
    }
    return "FL" in services and not _feeds_another_flare_part(view, node)


def _feeds_another_flare_part(view: RuleView, node: str) -> bool:
    """True for a PSV whose outlet block follows it: the block is the outlet, not the PSV."""
    return any(view.roles.get(n) == "psv_outlet_block" for n in view.piping.successors(node))


# ---- TOG141-DRAIN-DESTINATION ------------------------------------------------------------------


def check_drain_destination(view: RuleView) -> CheckResult:
    """TOG141-DRAIN-DESTINATION: hydrocarbon drains go to the closed drain, others to a funnel.

    A drain of a vacuum line is the one exception (`vacuum_drain`): nothing flows from vacuum
    into an atmospheric header, so it keeps its cap, a maintenance drain.
    """
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    # rule TOG141-DRAIN-DESTINATION: hydrocarbon drains go to the closed drain (Toghraei 2019 p.141)
    drains = sorted(n for n in view.piping if _DRAIN_VALVE_ROLE.search(view.roles.get(n, "")))
    closed_drain = _header_tees(view).get("CHD", frozenset())
    violations: list[Violation] = []
    vacuum = 0
    for drain in drains:
        problem, is_vacuum = _drain_problem(view, drain, closed_drain)
        vacuum += is_vacuum
        if problem:
            violations.append(_violation("TOG141-DRAIN-DESTINATION", drain, problem))
    return CheckResult(
        checked=len(drains),
        violations=tuple(violations),
        exceptions={"vacuum_drain": vacuum} if vacuum else {},
    )


def _drain_problem(view: RuleView, drain: str, closed_drain: frozenset[str]) -> tuple[str, bool]:
    """(what is wrong or "", whether the drain is the vacuum exception)."""
    (before,) = view.piping.predecessors(drain)
    service = service_of(view.graph, before, drain)
    fluid = FLUID_CLASS_OF_SERVICE[service]
    to_closed = _reaches(view, drain, closed_drain, downstream=True)
    funnel = any(view.graph.nodes[n]["node_class"] == "Funnel" for n in _after(view, drain))
    if fluid is not FluidClass.HYDROCARBON:
        if to_closed or not funnel:
            return (
                f"expected the {fluid.value} drain {drain} to end in a funnel (open drain)",
                False,
            )
        return "", False
    if to_closed and not funnel:
        return "", False
    if _is_vacuum_drain(view, before, drain):
        return "", True
    return (
        f"expected the hydrocarbon drain {drain} to reach the closed drain header, found none",
        False,
    )


def _after(view: RuleView, node: str) -> set[str]:
    return nx.descendants(view.piping, node)


def _is_vacuum_drain(view: RuleView, before: str, drain: str) -> bool:
    number = str(view.graph.edges[before, drain]["line_number"])
    return view.hidden.segment_level.get(number) == PressureLevel.VAC


# ---- TOG360-UTILITY-NETWORKS -------------------------------------------------------------------


def check_utility_networks(view: RuleView) -> CheckResult:
    """TOG360-UTILITY-NETWORKS: every utility stub joins the distribution or collection network."""
    if not _applies(view):
        return _NOT_APPLICABLE
    # rule TOG360-UTILITY-NETWORKS: each utility has a distribution network (Toghraei 2019 p.360)
    ends = _utility_stub_ends(view)
    tees = _header_tees(view)
    violations = []
    for node, service, direction in ends:
        reached = _reaches(
            view, node, tees.get(service, frozenset()),
            downstream=direction is TieDirection.COLLECTION,
        )  # fmt: skip
        if not reached:
            violations.append(
                _violation(
                    "TOG360-UTILITY-NETWORKS",
                    node,
                    f"expected the {service} stub at {node} to join a {service} {direction.value} "
                    "header, found none",
                )
            )
    return CheckResult(checked=len(ends), violations=tuple(violations))


def _utility_stub_ends(view: RuleView) -> list[tuple[str, str, TieDirection]]:
    """(part, service, direction) for the open end of every utility stub of a process unit."""
    ends: list[tuple[str, str, TieDirection]] = []
    for unit in view.plan.units:
        plan = unit.instance.plan
        for line in plan.lines:
            if plan.stream_kinds.get(line.line_number) is not StreamKindV2.UTILITY_STUB:
                continue
            direction = SERVICE_DIRECTION.get(line.fluid_code)
            if direction is TieDirection.DISTRIBUTION and line.src_id is None:
                ends.append((line.items[0].node_id, line.fluid_code, direction))
            if direction is TieDirection.COLLECTION and line.dst_id is None and line.items:
                ends.append((line.items[-1].node_id, line.fluid_code, direction))
    return sorted(ends)


# ---- TOG33-INTERAREA ---------------------------------------------------------------------------


def check_interarea(view: RuleView) -> CheckResult:
    """TOG33-INTERAREA: trains meet only over an interarea sheet, with a battery limit in it."""
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    # rule TOG33-INTERAREA: lines between areas run over an interarea sheet (Toghraei p.33)
    train_of = _train_of_nodes(view)
    straight = [unit for unit in _networks(view) if unit.is_interarea]
    interarea_nodes = {n for unit in straight for n in unit.sheets.sheet_of}
    direct = [
        _violation(
            "TOG33-INTERAREA",
            u,
            f"expected an interarea sheet between {u} and {v}, found a direct pipe",
        )
        for u, v in sorted(view.piping.edges)
        if train_of[u] != train_of[v] and not {u, v} & interarea_nodes
    ]
    unguarded = [
        _violation("TOG33-INTERAREA", min(unit.sheets.sheet_of), "expected a battery limit")
        for unit in straight
        if not BATTERY_LIMIT_ROLES & set(unit.plan.roles.values())
    ]
    lines = sum(len(unit.plan.lines) for unit in straight)
    return CheckResult(checked=lines, violations=tuple([*direct, *unguarded]))


def _train_of_nodes(view: RuleView) -> dict[str, int]:
    train_of_unit = {str(u.unit_no): u.train_no for u in view.generated.record.units}
    return {n: train_of_unit[str(d["unit_id"])] for n, d in view.graph.nodes(data=True)}


# ---- PLT-NETWORK-CLOSURE -----------------------------------------------------------------------


def check_network_closure(view: RuleView) -> CheckResult:
    """PLT-NETWORK-CLOSURE: one connector per service per process sheet; every header ends.

    The splitter cuts every pipe that crosses two sheets into a connector pair, so a connector has
    a partner exactly when the plan puts both ends on a sheet. What can go wrong is therefore the
    count: more than one crossing from a process sheet to one network, a header sheet over its
    capacity, or a header end that is not a battery limit.
    """
    if not _applies(view):
        return _NOT_APPLICABLE
    # rule PLT-NETWORK-CLOSURE: every network connector pairs and every header ends (TOG p.32–34)
    violations = [*_crossing_problems(view), *_capacity_problems(view), *_end_problems(view)]
    checked = len(_crossings(view)) + len(_networks(view))
    return CheckResult(checked=checked, violations=tuple(violations))


def _crossings(view: RuleView) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """(process sheet, service) -> the pipes that join that sheet to a network header."""
    sheet_of = view.plan.sheet_of
    service_of_node = {
        n: unit.service for unit in _networks(view) if not unit.is_interarea
        for n in unit.sheets.sheet_of
    }  # fmt: skip
    found: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for u, v in view.piping.edges:
        header, process = (v, u) if v in service_of_node else (u, v)
        if header in service_of_node and process not in service_of_node:
            found[(sheet_of[process], service_of_node[header])].append((u, v))
    return found


def _crossing_problems(view: RuleView) -> list[Violation]:
    return [
        _violation(
            "PLT-NETWORK-CLOSURE",
            pipes[0][0],
            f"expected one {service} connector on process sheet {sheet}, found {len(pipes)}",
        )
        for (sheet, service), pipes in sorted(_crossings(view).items())
        if len(pipes) != 1
    ]


def _capacity_problems(view: RuleView) -> list[Violation]:
    config = view.plan.config
    if not isinstance(config, GeneratorConfigV22):  # unreachable: only v2.2 plants have networks
        raise ValueError(f"expected a v2.2 config, got {type(config).__name__}")
    capacity = config.handbook.max_tie_ins_per_network_sheet
    found = []
    for unit in _networks(view):
        tees_per_sheet: dict[str, int] = defaultdict(int)
        for node, role in unit.plan.roles.items():
            if role == _HEADER_TEE:
                tees_per_sheet[unit.sheets.sheet_of[node]] += 1
        found += [
            _violation(
                "PLT-NETWORK-CLOSURE",
                sheet,
                f"expected at most {capacity} tie-ins on {sheet}, found {n}",
            )
            for sheet, n in sorted(tees_per_sheet.items())
            if n > capacity
        ]
    return found


def _end_problems(view: RuleView) -> list[Violation]:
    """A header's dead end (no way on, or no way in) must be a battery limit."""
    problems = []
    for unit in _networks(view):
        nodes = set(unit.sheets.sheet_of)
        for node in sorted(nodes):
            piping = view.piping
            is_end = piping.out_degree(node) == 0 or piping.in_degree(node) == 0
            if is_end and not _near_battery_limit(view, node):
                problems.append(
                    _violation(
                        "PLT-NETWORK-CLOSURE", node, f"expected {node} to end at a battery limit"
                    )
                )
    return problems


def _near_battery_limit(view: RuleView, node: str) -> bool:
    piping = view.piping
    nearby = [node, *piping.predecessors(node), *piping.successors(node)]
    return any(view.roles.get(n) in BATTERY_LIMIT_ROLES for n in nearby)
