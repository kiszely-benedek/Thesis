"""Checks of the rules about what a line connects to (Toghraei 2019 pp.24, 224), on any plant.

A **line** is one run of pipe with a line number. A P&ID is drawn **sheet** by sheet: a line that
leaves a sheet continues on another through an off-page connector. A **PSV** (pressure safety
valve) opens when the pressure in the **enclosure** (the vessel or pipe it protects) gets too
high, so nothing may stand between enclosure and PSV that could close or throttle that path.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.boundary import END_FITTINGS
from plantgraph.benchmark.v2.plan_models import LineSpec, StreamKindV2
from plantgraph.benchmark.v2.rules.control_graph import is_control_valve
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.trims_valves import BATTERY_LIMIT_ROLES
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation


def _lines(view: RuleView) -> list[LineSpec]:
    return [line for unit in view.plan.units for line in unit.instance.plan.lines]


def _is_safety_valve(node_class: str) -> bool:
    return node_class.endswith("SafetyValve")


# ---- TOG224-PSV-PIPE-CLEAN ---------------------------------------------------------------------


def _pipe_to_enclosure(view: RuleView, psv: str) -> list[str]:
    """The parts between the PSV and the item or tee it is tapped from, nearest the PSV first."""
    piping, graph = view.piping, view.graph
    between: list[str] = []
    node = psv
    while True:
        before = list(piping.predecessors(node))
        if len(before) != 1:
            return between
        node = before[0]
        # the branch starts at the equipment item or at the tee that splits the main line
        if graph.nodes[node]["node_class"] in EQUIPMENT_CLASSES or piping.out_degree(node) > 1:
            return between
        between.append(node)


def _blocking_part(view: RuleView, node: str) -> str | None:
    """Why a part may not stand in a PSV's inlet pipe, or None."""
    node_class = str(view.graph.nodes[node]["node_class"])
    if "CheckValve" in node_class:
        return "check valve"
    if is_control_valve(view.graph, node):
        return "control valve"
    return None


def check_psv_pipe_clean(view: RuleView) -> CheckResult:
    """TOG224-PSV-PIPE-CLEAN: no check or control valve between an enclosure and its PSV."""
    # rule TOG224-PSV-PIPE-CLEAN: a clear pipe from the enclosure to its PSV (Toghraei 2019 p.224)
    graph = view.graph
    psvs = sorted(n for n, d in graph.nodes(data=True) if _is_safety_valve(d["node_class"]))
    violations = []
    for psv in psvs:
        for part in _pipe_to_enclosure(view, psv):
            kind = _blocking_part(view, part)
            if kind:
                detail = f"{kind} {part} between the enclosure and its PSV {psv}"
                violations.append(
                    Violation(rule_id="TOG224-PSV-PIPE-CLEAN", node_id=psv, detail=detail)
                )
    return CheckResult(checked=len(psvs), violations=tuple(violations))


# ---- TOG24-NO-VISITING-STREAM ------------------------------------------------------------------


def _sheet_of_every_node(view: RuleView) -> dict[str, str]:
    """Node id -> sheet, over all units (a cross-unit line names a node of another unit)."""
    sheets: dict[str, str] = {}
    for unit in view.plan.units:
        sheets.update(unit.sheets.sheet_of)
    return sheets


def _visiting_sheets(line: LineSpec, sheet_of: dict[str, str]) -> set[str]:
    """Sheets that show parts of the line but neither of its two end items."""
    ends = [end for end in (line.src_id, line.dst_id) if end is not None]
    missing = [n for n in [*ends, *(i.node_id for i in line.items)] if n not in sheet_of]
    if missing:
        raise ValueError(
            f"expected a sheet for every node of line {line.line_number}, no sheet for {missing}"
        )
    end_sheets = {sheet_of[end] for end in ends}
    return {sheet_of[item.node_id] for item in line.items} - end_sheets


def check_no_visiting_stream(view: RuleView) -> CheckResult:
    """TOG24-NO-VISITING-STREAM: every line on a sheet connects to an item on that sheet."""
    # rule TOG24-NO-VISITING-STREAM: every line touches an item on its sheet (Toghraei 2019 p.24)
    sheet_of = _sheet_of_every_node(view)
    lines = _lines(view)
    violations = []
    for line in lines:
        visiting = _visiting_sheets(line, sheet_of)
        if visiting:
            detail = (
                f"line {line.line_number} runs over sheets {sorted(visiting)} "
                "without touching an item there"
            )
            violations.append(
                Violation(
                    rule_id="TOG24-NO-VISITING-STREAM", node_id=line.items[0].node_id, detail=detail
                )
            )
    return CheckResult(checked=len(lines), violations=tuple(violations))


# ---- PLT-STREAM-CLOSURE ------------------------------------------------------------------------


def _dead_ends(piping: nx.DiGraph[str], graph: nx.DiGraph[str]) -> list[str]:
    """The pipe parts where a stream stops (no way on) or starts (no way in), once lines are joined.

    Equipment is no end: a vessel is where a stream is made or used. A line that continues into the
    next unit has no dead end at the join, which is why this reads the joined graph, not the
    per-unit lines.
    """
    is_end = (n for n in piping if piping.out_degree(n) == 0 or piping.in_degree(n) == 0)
    return sorted(n for n in is_end if graph.nodes[n]["node_class"] not in EQUIPMENT_CLASSES)


def _line_number_at(graph: nx.DiGraph[str], end: str) -> str:
    """The number of the pipe at a dead end; `graph` is needed, `flow` drops the edge data."""
    pipes = [d for _, _, d in [*graph.in_edges(end, data=True), *graph.out_edges(end, data=True)]
             if d["relation"] == Relation.SEND_TO.value]  # fmt: skip
    return str(pipes[0].get("line_number", ""))


def _beside(piping: nx.DiGraph[str], end: str) -> list[str]:
    """The neighbours of the end: the one pipe part (or equipment) it hangs from."""
    return [*piping.predecessors(end), *piping.successors(end)]


def _declared_as(view: RuleView, piping: nx.DiGraph[str], end: str) -> str | None:
    """The kind of declared end a dead end is, or None when it just stops."""
    graph = view.graph
    nearby = [end, *_beside(piping, end)]  # the blind may sit one part inside its block valve
    if any(view.roles.get(n) in BATTERY_LIMIT_ROLES for n in nearby):
        return "battery_limit"  # the unit's boundary toward the rest of the plant
    kind = view.stream_kind_of(_line_number_at(view.graph, end))
    if kind is StreamKindV2.UTILITY_STUB:
        return "utility_stub"  # a utility line that continues on the network sheets
    node_class = str(graph.nodes[end]["node_class"])
    if node_class in END_FITTINGS or _is_safety_valve(node_class):
        return "end_fitting"  # a cap, drain funnel, vent or relief outlet
    return None


def check_stream_closure(view: RuleView) -> CheckResult:
    """PLT-STREAM-CLOSURE: every stream ends at a declared end (a source or sink item, or a stub).

    Runs on the plant flow graph after the flowsheet joins, so a line that continues into the next
    unit is not an end. `checked` is the number of dead ends found.
    """
    # rule PLT-STREAM-CLOSURE: a source and a sink item, or a declared end (Toghraei 2019 p.24)
    piping = view.piping
    ends = _dead_ends(piping, view.graph)
    declared: dict[str, int] = {}
    violations = []
    for end in ends:
        kind = _declared_as(view, piping, end)
        if kind is not None:
            declared[kind] = declared.get(kind, 0) + 1
            continue
        number = _line_number_at(view.graph, end)
        stream = view.stream_kind_of(number)
        detail = (
            f"line {number} ({stream.value if stream else 'unknown kind'}) "
            f"ends open at a {view.graph.nodes[end]['node_class']} "
            f"(role {view.roles.get(end, '?')}) with no declared end"
        )
        violations.append(Violation(rule_id="PLT-STREAM-CLOSURE", node_id=end, detail=detail))
    return CheckResult(checked=len(ends), violations=tuple(violations), exceptions=declared)
