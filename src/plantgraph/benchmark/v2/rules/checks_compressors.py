"""Checks of the v2.2 compressor rules (Toghraei 2019 pp.316-319): capacity control.

A **dynamic** compressor (centrifugal) can **surge**: run so far below its design flow that the gas
flows backwards. An **anti-surge** loop prevents it by opening a recycle valve on a *flow* signal.
A **positive-displacement (PD)** compressor (reciprocating, rotary) cannot surge; its capacity is
set by spilling gas back to the inlet on a *pressure* signal, never by throttling its discharge.

A compressor **stage** is a `U2` unit of the plan. Its recycle valve is the control valve on a
line whose stream kind is `recycle`. Like `checks_pumps`, these report `checked=0` on v2.1 plants.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.rules.checks_v21_plant import reach
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import CONTROL_VALVE_BODY_CLASSES, Relation

_STAGE_PATTERN = "U2"
_DYNAMIC = "CentrifugalCompressor"
_FLOW_VALVE, _PRESSURE_VALVE = "FV-", "PV-"  # tag prefixes of a flow and a pressure control valve
_AEF = "ActuatingElectricalFunction"  # the variable-speed drive of a machine


class PdStage:
    """One PD compressor stage: its machine, its recycle valves and the parts after the machine."""

    def __init__(self, view: RuleView, unit_no: int, instance: PatternInstance) -> None:
        self.graph = view.graph
        in_unit = [n for n, d in self.graph.nodes(data=True) if d["unit_id"] == str(unit_no)]
        self.machine = next(n for n in sorted(in_unit) if self.node_class(n).endswith("Compressor"))
        recycle_lines = {
            number
            for number, kind in instance.plan.stream_kinds.items()
            if kind is StreamKindV2.RECYCLE
        }
        self.recycle_valves = _valves_on_lines(self.graph, recycle_lines)
        self.after_machine = reach(view.piping, self.graph, self.machine, up=False)[0]
        self.has_speed_drive = _is_driven_by_aef(self.graph, self.machine)

    def node_class(self, node: str) -> str:
        """The schema class of a graph node."""
        return str(self.graph.nodes[node]["node_class"])

    def tag(self, node: str) -> str:
        """The printed tag of a graph node, empty when it has none."""
        return str(self.graph.nodes[node].get("tag", ""))


def _valves_on_lines(graph: nx.DiGraph[str], line_numbers: set[str]) -> list[str]:
    found = {
        node
        for source, target, data in graph.edges(data=True)
        if data.get("line_number") in line_numbers
        for node in (source, target)
        if graph.nodes[node]["node_class"] in CONTROL_VALVE_BODY_CLASSES
    }
    return sorted(found)


def _is_driven_by_aef(graph: nx.DiGraph[str], machine: str) -> bool:
    """True when an actuating electrical function (a variable-speed drive) controls the machine."""
    return any(
        graph.nodes[source]["node_class"] == _AEF and data["relation"] == Relation.CONTROL.value
        for source, _, data in graph.in_edges(machine, data=True)
    )


def pd_stages(view: RuleView) -> list[PdStage]:
    """Every compressor stage of the plant whose machine is not a dynamic (centrifugal) one."""
    stages = []
    for unit in view.plan.units:
        if unit.instance.pattern != _STAGE_PATTERN:
            continue
        stage = PdStage(view, unit.slot.unit_no, unit.instance)
        if stage.node_class(stage.machine) != _DYNAMIC:
            stages.append(stage)
    return stages


def _violation(rule_id: str, stage: PdStage, detail: str) -> Violation:
    return Violation(rule_id=rule_id, node_id=stage.machine, detail=detail)


def check_antisurge_dynamic(view: RuleView) -> CheckResult:
    """TOG319-ANTISURGE-DYNAMIC: no flow-controlled recycle (anti-surge) on a PD compressor."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    stages = pd_stages(view)
    violations = [
        _violation("TOG319-ANTISURGE-DYNAMIC", stage, f"anti-surge recycle valve {valve}")
        for stage in stages
        for valve in stage.recycle_valves
        if stage.tag(valve).startswith(_FLOW_VALVE)
    ]
    return CheckResult(checked=len(stages), violations=tuple(violations))


def _capacity_problem(stage: PdStage) -> str | None:
    pressure_valves = [v for v in stage.recycle_valves if stage.tag(v).startswith(_PRESSURE_VALVE)]
    if not pressure_valves and not stage.has_speed_drive:
        return "expected a pressure-controlled spillback or a variable-speed drive, found neither"
    throttles = sorted(
        n for n in stage.after_machine if stage.node_class(n) in CONTROL_VALVE_BODY_CLASSES
    )
    if throttles:
        return f"control valve {throttles[0]} throttles the compressor discharge"
    return None


def check_pd_compressor_capacity(view: RuleView) -> CheckResult:
    """TOG316-PD-COMP-CAPACITY: spillback with a pressure loop or a drive; no discharge valve."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    stages = pd_stages(view)
    violations = [
        _violation("TOG316-PD-COMP-CAPACITY", stage, problem)
        for stage in stages
        if (problem := _capacity_problem(stage))
    ]
    return CheckResult(checked=len(stages), violations=tuple(violations))


# ---- API14C-A8: the discharge check valve and relief valve, on every plant ---------------------


def _compressors(view: RuleView) -> list[str]:
    nodes = view.graph.nodes(data=True)
    return sorted(n for n, d in nodes if str(d["node_class"]).endswith("Compressor"))


def _roles_after(view: RuleView, machine: str) -> set[str]:
    """The roles of the pipe parts downstream of the machine, up to the next equipment."""
    parts = reach(view.piping, view.graph, machine, up=False)[0]
    return {view.roles[n] for n in parts if n in view.roles}


def _check_discharge_role(view: RuleView, rule_id: str, role: str, what: str) -> CheckResult:
    """One violation per compressor whose discharge side has no part with `role`."""
    machines = _compressors(view)
    violations = [
        Violation(rule_id=rule_id, node_id=m, detail=f"expected {what} after {m}, found none")
        for m in machines
        if role not in _roles_after(view, m)
    ]
    return CheckResult(checked=len(machines), violations=tuple(violations))


def check_compressor_discharge_check(view: RuleView) -> CheckResult:
    """API14C-A8-FSV: a check valve on the final discharge of every compressor."""
    # rule API14C-A8-FSV: a discharge check valve (API 14C A.8.3.2 p.45; Toghraei p.84)
    role = "compressor_discharge_check"
    return _check_discharge_role(view, "API14C-A8-FSV", role, "a discharge check valve")


def check_compressor_discharge_psv(view: RuleView) -> CheckResult:
    """API14C-A8-PSV: a pressure safety valve on the discharge of every compressor."""
    # rule API14C-A8-PSV: a discharge safety valve (API 14C A.8.2.2.1 p.45)
    role = "compressor_discharge_psv"
    return _check_discharge_role(view, "API14C-A8-PSV", role, "a discharge safety valve")
