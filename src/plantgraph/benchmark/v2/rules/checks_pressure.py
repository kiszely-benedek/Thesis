"""Checks of the pressure-level rules (design 6.2): what a plant does where its level changes.

The generator keeps a hidden **pressure level** for every run of pipe and every vessel
(`pressure_levels.py`): an ordinal rank from vacuum to high, never a value. A **run** is a stretch
of pipe with one line number; a **spec break** (`PropertyBreak`) is the part where the pipe's
class (its material and pressure rating) changes. These checks read the levels from
`view.hidden.segment_level` and test the drawing against them. On a v2.1 plant, or with the
handbook off, they report `checked=0`: no level is drawn there.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.hidden_state import PressureLevel
from plantgraph.benchmark.v2.plan_models import LineSpec, StreamKindV2
from plantgraph.benchmark.v2.pressure_levels import (
    COMPRESSOR_CLASSES,
    PUMP_CLASSES,
    is_mover,
)
from plantgraph.benchmark.v2.rules.control_graph import is_control_valve
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.benchmark.v2.trims_machine import DISCHARGE_BREAK_ROLE
from plantgraph.benchmark.v2.trims_min_flow import SWITCH_VALVE_ROLE
from plantgraph.benchmark.v2.vocabulary import LINE_SPECS
from plantgraph.graph.schema import EQUIPMENT_CLASSES

NOT_APPLICABLE = CheckResult(checked=0)
_BREAK = "PropertyBreak"
_ORIFICE = "RestrictionOrifice"
#: the roles of a reactor's recycle-gas inlet: a compressor loop inside its core (design 17.12)
_RECYCLE_GAS_ROLES = frozenset({"recycle_gas_block", "recycle_gas_check"})


# ---- reading the levels ------------------------------------------------------------------------


def edge_level(view: RuleView, upstream: str, downstream: str) -> PressureLevel:
    """The level of the pipe between two neighbouring parts (the level of its run)."""
    number = view.graph.edges[upstream, downstream]["line_number"]
    try:
        return view.hidden.segment_level[number]
    except KeyError:
        raise ValueError(
            f"expected a hidden pressure level for line {number}, found none"
        ) from None


def line_number_of(view: RuleView, upstream: str, downstream: str) -> str:
    """The line number of the pipe between two neighbouring parts."""
    return str(view.graph.edges[upstream, downstream]["line_number"])


def node_class(view: RuleView, node: str) -> str:
    """The schema class of a node of the oracle graph."""
    return str(view.graph.nodes[node]["node_class"])


def is_equipment(view: RuleView, node: str) -> bool:
    """True for a machine, vessel or exchanger (not a pipe part)."""
    return node_class(view, node) in EQUIPMENT_CLASSES


def _violation(rule_id: str, node: str, detail: str) -> Violation:
    return Violation(rule_id=rule_id, node_id=node, detail=detail)


# ---- PRS-MONOTONE ------------------------------------------------------------------------------


def _may_raise(view: RuleView, node: str) -> bool:
    """A mover raises the level; so does the spec break right behind it (`trims_machine.py`)."""
    return (
        is_mover(node_class(view, node), view.roles.get(node))
        or view.roles.get(node) == DISCHARGE_BREAK_ROLE
    )


def _rise_at(view: RuleView, node: str) -> list[Violation]:
    piping = view.piping
    top = max(edge_level(view, p, node) for p in piping.predecessors(node))
    return [
        _violation(
            "PRS-MONOTONE",
            node,
            f"expected the level behind {node} at or below {top.name}, found "
            f"{edge_level(view, node, s).name} on line {line_number_of(view, node, s)}",
        )
        for s in piping.successors(node)
        if edge_level(view, node, s) > top
    ]


def check_monotone(view: RuleView) -> CheckResult:
    """PRS-MONOTONE: along the flow the level never rises except across a mover."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule PRS-MONOTONE: the level never rises except across a mover (design §6.2)
    piping = view.piping
    nodes = [n for n in sorted(piping) if piping.in_degree(n) and piping.out_degree(n)]
    nodes = [n for n in nodes if not _may_raise(view, n)]
    violations = [v for node in nodes for v in _rise_at(view, node)]
    return CheckResult(checked=len(nodes), violations=tuple(violations))


# ---- TOG82-SPEC-BREAK --------------------------------------------------------------------------


def _unmarked_change(view: RuleView, node: str) -> Violation | None:
    """A pipe part where the line number and the level change but the part is no spec break."""
    piping = view.piping
    (before,), (after,) = list(piping.predecessors(node)), list(piping.successors(node))
    if line_number_of(view, before, node) == line_number_of(view, node, after):
        return None
    low, high = edge_level(view, before, node), edge_level(view, node, after)
    if low == high or node_class(view, node) == _BREAK:
        return None
    return _violation(
        "TOG82-SPEC-BREAK",
        node,
        f"expected a spec break where the level changes from {low.name} to {high.name}, "
        f"found a {node_class(view, node)}",
    )


def _has_rising_break_behind(view: RuleView, machine: str) -> bool:
    """True when a spec break right behind the machine (past its nozzle parts) raises the level."""
    piping = view.piping
    for start in piping.successors(machine):
        node = start
        while not is_equipment(view, node) and node_class(view, node) != _BREAK:
            following = list(piping.successors(node))
            if len(following) != 1:
                break
            node = following[0]
        if node_class(view, node) == _BREAK and _raises_across(view, node):
            return True
    return False


def _raises_across(view: RuleView, spec_break: str) -> bool:
    piping = view.piping
    (before,), (after,) = list(piping.predecessors(spec_break)), list(piping.successors(spec_break))
    return edge_level(view, spec_break, after) > edge_level(view, before, spec_break)


def check_spec_break(view: RuleView) -> CheckResult:
    """TOG82-SPEC-BREAK: a level change along a pipe, or at a pump or compressor, has a break."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule TOG82-SPEC-BREAK: a spec break where the level changes (Toghraei 2019 p.82)
    piping = view.piping
    inline = [
        n
        for n in sorted(piping)
        if not is_equipment(view, n) and piping.in_degree(n) == 1 and piping.out_degree(n) == 1
    ]
    machines = sorted(n for n in piping if node_class(view, n) in PUMP_CLASSES | COMPRESSOR_CLASSES)
    violations = [v for node in inline if (v := _unmarked_change(view, node))]
    violations += [
        _violation(
            "TOG82-SPEC-BREAK",
            machine,
            "expected a spec break behind the machine that raises the level",
        )
        for machine in machines
        if not _has_rising_break_behind(view, machine)
    ]
    return CheckResult(checked=len(inline) + len(machines), violations=tuple(violations))


# ---- PRS-SPEC-CLASS ----------------------------------------------------------------------------


def _spec_rank(number: str) -> int:
    parsed = parse_line_number(number)
    if parsed is None:
        raise ValueError(f"expected a line number of the v2 grammar, got {number!r}")
    return LINE_SPECS.index(parsed.spec)


def _class_problem(view: RuleView, spec_break: str) -> Violation | None:
    piping = view.piping
    (before,), (after,) = list(piping.predecessors(spec_break)), list(piping.successors(spec_break))
    low, high = edge_level(view, before, spec_break), edge_level(view, spec_break, after)
    if low == high:
        return None  # no level change to follow: nothing to rank
    before_rank = _spec_rank(line_number_of(view, before, spec_break))
    after_rank = _spec_rank(line_number_of(view, spec_break, after))
    heavier_is_after = after_rank > before_rank
    if heavier_is_after == (high > low) and after_rank != before_rank:
        return None
    return _violation(
        "PRS-SPEC-CLASS",
        spec_break,
        f"expected the heavier piping class on the higher side ({max(low, high).name}); the class "
        f"ranks are {before_rank} before and {after_rank} behind the break",
    )


def check_spec_class(view: RuleView) -> CheckResult:
    """PRS-SPEC-CLASS: across a spec break the higher-level side has the heavier piping class."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule PRS-SPEC-CLASS: the heavier class is on the higher-level side (ADR-0065 F8c)
    piping = view.piping
    breaks = [
        n
        for n in sorted(piping)
        if node_class(view, n) == _BREAK and piping.in_degree(n) == 1 and piping.out_degree(n) == 1
    ]
    violations = [v for node in breaks if (v := _class_problem(view, node))]
    return CheckResult(checked=len(breaks), violations=tuple(violations))


# ---- PLT-RECYCLE-CLOSURE -----------------------------------------------------------------------


def _recycle_lines(view: RuleView) -> list[LineSpec]:
    """Spillback, min-flow and anti-surge lines; a reactor's recycle-gas inlet is a core loop."""
    lines = [line for unit in view.plan.units for line in unit.instance.plan.lines]
    return [
        line
        for line in lines
        if view.stream_kind_of(line.line_number) is StreamKindV2.RECYCLE
        and not any(view.roles.get(i.node_id) in _RECYCLE_GAS_ROLES for i in line.items)
    ]


def _level_returned_to(view: RuleView, end: str) -> PressureLevel:
    """The level of what a line returns into: a vessel, or the pipe at the tee it ties into."""
    levels = view.hidden.segment_level
    if end in levels:
        return levels[end]
    following = list(view.piping.successors(end))
    if following:
        return edge_level(view, end, following[0])
    return edge_level(view, next(iter(view.piping.predecessors(end))), end)


def _reduces(view: RuleView, node: str) -> bool:
    """An orifice, a control valve, or the on-off valve of a pump's switching min-flow method."""
    return (
        node_class(view, node) == _ORIFICE
        or is_control_valve(view.graph, node)
        or view.roles.get(node) == SWITCH_VALVE_ROLE
    )


def _relies_on_switching_valve(view: RuleView, line: LineSpec) -> bool:
    """True when the on-off valve of the switching method is the line's only reducing part."""
    nodes = [item.node_id for item in line.items]
    only_switch = [n for n in nodes if _reduces(view, n)]
    return bool(only_switch) and all(view.roles.get(n) == SWITCH_VALVE_ROLE for n in only_switch)


def _recycle_problem(view: RuleView, line: LineSpec) -> str | None:
    if line.src_id is None or line.dst_id is None:
        return "expected a recycle that starts and ends inside the drawing, found an open end"
    units = {view.graph.nodes[n]["unit_id"] for n in (line.src_id, line.dst_id)}
    if len(units) != 1:
        return f"expected the recycle to return inside its unit, found units {sorted(units)}"
    start = view.hidden.segment_level[line.line_number]
    back = _level_returned_to(view, line.dst_id)
    if start <= back:
        return f"expected a fall from a higher to a lower level, found {start.name} to {back.name}"
    if not any(_reduces(view, item.node_id) for item in line.items):
        return "expected an orifice or a valve on the recycle, found neither"
    return None


def check_recycle_closure(view: RuleView) -> CheckResult:
    """PLT-RECYCLE-CLOSURE: a recycle returns inside its unit, downhill, through a reducing part."""
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule PLT-RECYCLE-CLOSURE: a recycle returns downhill through a reducer (Toghraei 2019 p.317)
    lines = _recycle_lines(view)
    violations = [
        _violation("PLT-RECYCLE-CLOSURE", line.items[0].node_id, f"line {line.line_number}: {why}")
        for line in lines
        if (why := _recycle_problem(view, line))
    ]
    # element code `switching_valve`: how often the on-off valve of the switching method is the
    # only reducer, so the reader sees how much the reading carries (design 17.13 R3)
    switching = sum(_relies_on_switching_valve(view, line) for line in lines)
    return CheckResult(
        checked=len(lines),
        violations=tuple(violations),
        exceptions={"switching_valve": switching} if switching else {},
    )
