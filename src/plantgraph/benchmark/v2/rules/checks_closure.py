"""Checks of the rules about what a line connects to (Toghraei 2019 pp.24, 224), on any plant.

A **line** is one run of pipe with a line number. A P&ID is drawn **sheet** by sheet: a line that
leaves a sheet continues on another through an off-page connector. A **PSV** (pressure safety
valve) opens when the pressure in the **enclosure** (the vessel or pipe it protects) gets too
high, so nothing may stand between enclosure and PSV that could close or throttle that path.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec, StreamKindV2
from plantgraph.benchmark.v2.rules.checks_v21_plant import flow
from plantgraph.benchmark.v2.rules.control_graph import is_control_valve
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import EQUIPMENT_CLASSES

#: where a line may end with nothing behind it: a blind or cap, an open drain funnel, a vent to
#: the atmosphere (breather, ventilation device, silencer, flame arrestor), a rupture disc
_END_FITTINGS = frozenset(
    {
        "BlindFlange",
        "LineBlind",
        "Funnel",
        "VentilationDevice",
        "BreatherValve",
        "Silencer",
        "FlameArrestor",
        "RuptureDisc",
    }
)


def _lines(view: RuleView) -> list[LineSpec]:
    return [line for unit in view.plan.units for line in unit.instance.plan.lines]


def _is_safety_valve(node_class: str) -> bool:
    return node_class.endswith("SafetyValve")


# ---- TOG224-PSV-PIPE-CLEAN ---------------------------------------------------------------------


def _pipe_to_enclosure(view: RuleView, psv: str) -> list[str]:
    """The parts between the PSV and the item or tee it is tapped from, nearest the PSV first."""
    piping, graph = flow(view.graph), view.graph
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


def _open_ends(line: LineSpec) -> list[LineItemSpec]:
    """The last inline part at each end of the line that connects to no item."""
    ends = []
    if line.src_id is None:
        ends.append(line.items[0])
    if line.dst_id is None:
        ends.append(line.items[-1])
    return ends


def _declared_as(view: RuleView, line: LineSpec, end: LineItemSpec) -> str | None:
    """The kind of declared end a line stops at, or None when it just stops."""
    if view.generated.record.stream_kind.get(line.line_number) is StreamKindV2.UTILITY_STUB:
        return "utility_stub"  # a utility line that continues on the network sheets
    if end.node_class in _END_FITTINGS or _is_safety_valve(end.node_class):
        return "end_fitting"  # a cap, drain funnel, vent or relief outlet
    return None


def check_stream_closure(view: RuleView) -> CheckResult:
    """PLT-STREAM-CLOSURE: a line has a source and a sink item, or a declared end."""
    # rule PLT-STREAM-CLOSURE: a source and a sink item, or a declared end (Toghraei 2019 p.24)
    lines = _lines(view)
    declared: dict[str, int] = {}
    violations = []
    for line in lines:
        for end in _open_ends(line):
            kind = _declared_as(view, line, end)
            if kind is not None:
                declared[kind] = declared.get(kind, 0) + 1
                continue
            stream = view.generated.record.stream_kind.get(line.line_number)
            detail = (
                f"line {line.line_number} ({stream.value if stream else 'unknown kind'}) "
                f"ends open at a {end.node_class} with no declared end"
            )
            violations.append(
                Violation(rule_id="PLT-STREAM-CLOSURE", node_id=end.node_id, detail=detail)
            )
    return CheckResult(checked=len(lines), violations=tuple(violations), exceptions=declared)
