"""The wired registry checks on plants of seeds 1-5 and on plants broken on purpose (design 3.3).

Per wired rule: (a) no violation on seeds 1-5, (b) a mutation that breaks the plant is caught,
(c) over the five seeds the check looked at something. Rules with a pending check have none of
these yet; `test_rule_registry.py` lists them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import networkx as nx
import pytest
from plant_invariants import plant_view

from plantgraph.benchmark.v2.rules import checks_rules
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.checks_v21_plant import flow, reach
from plantgraph.benchmark.v2.rules.registry import CheckResult
from plantgraph.benchmark.v2.rules.verify import (
    RuleViolationError,
    raise_on_violations,
    verify_plant,
    verify_view,
    wired_rules,
)
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.graph.schema import CONTROL_VALVE_BODY_CLASSES
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
_WIRED = [rule.rule_id for rule in wired_rules() if rule.since == "v2.1"]  # v2.2 rules: next file
_ALL_WIRED = [rule.rule_id for rule in wired_rules()]


def _view(seed: int) -> RuleView:
    units = smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units  # about 30 sheets
    return plant_view(seed, units)


def _run(rule_id: str, view: RuleView) -> CheckResult:
    from plantgraph.benchmark.v2.rules.verify import run_rule

    return run_rule(rule_by_id(rule_id), view)


# ---- (a) positive and (c) non-vacuity -----------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _WIRED)
def test_a_wired_rule_has_no_violation_on_a_v21_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, _view(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _WIRED)
def test_a_wired_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, _view(seed)).checked for seed in SEEDS) > 0


# ---- (b) mutations -------------------------------------------------------------------------------


def _without_nodes(view: RuleView, doomed: Callable[[str, dict[str, object]], bool]) -> RuleView:
    graph = view.graph.copy()
    graph.remove_nodes_from([n for n, d in view.graph.nodes(data=True) if doomed(n, d)])
    return replace(view, graph=graph)


def _break_pump_trim(view: RuleView) -> RuleView:
    roles = {n: r for n, r in view.roles.items() if r != "suction_strainer"}
    return replace(view, roles=roles)


def _break_pd_relief(view: RuleView) -> RuleView:
    """Make the relief's tap come after the check valve, by wiring the check to it."""
    piping = flow(view.graph)
    graph = view.graph.copy()
    for relief in sorted(n for n, r in view.roles.items() if r == "pd_relief_valve"):
        (start,) = piping.predecessors(relief)
        for pump in (n for n in piping if reach(piping, view.graph, n, up=False)[0] >= {start}):
            checks = [
                n for n in reach(piping, view.graph, pump, up=False)[0]
                if view.roles.get(n) == "discharge_check"
            ]  # fmt: skip
            if checks and view.graph.nodes[pump]["node_class"].endswith("Pump"):
                graph.add_edge(
                    checks[0], start, relation="send_to", line_number="x", fluid_code="P"
                )
                return replace(view, graph=graph)
    raise AssertionError("no positive-displacement pump relief found to break")


def _break_vessel_psv(view: RuleView) -> RuleView:
    return _without_nodes(view, lambda _, d: "SafetyValve" in str(d["node_class"]))


def _break_phase(view: RuleView) -> RuleView:
    """Pipe a pump's discharge block straight back to the vessel it draws from."""
    piping, graph = flow(view.graph), view.graph.copy()
    for pump, data in sorted(view.graph.nodes(data=True)):
        if not str(data["node_class"]).endswith("Pump"):
            continue
        suction_vessels = reach(piping, view.graph, pump, up=True)[1] - {pump}
        blocks = [
            n for n in reach(piping, view.graph, pump, up=False)[0]
            if view.roles.get(n) == "discharge_block"
        ]  # fmt: skip
        if suction_vessels and blocks:
            graph.add_edge(blocks[0], sorted(suction_vessels)[0], relation="send_to",
                           line_number="x", fluid_code="P")  # fmt: skip
            return replace(view, graph=graph)
    raise AssertionError("no pump with a suction vessel found to break")


def _break_loop_number(view: RuleView) -> RuleView:
    graph = view.graph.copy()
    actuator = next(
        n for n, d in sorted(graph.nodes(data=True))
        if d["node_class"] == "ActuatingFunction" and d.get("loop_tag")
    )  # fmt: skip
    graph.nodes[actuator]["loop_tag"] = "ZZZ-0"
    return replace(view, graph=graph)


def _control_valve_with_a_number(graph: nx.DiGraph[str]) -> str:
    return next(
        n for n, d in sorted(graph.nodes(data=True))
        if d["node_class"] in CONTROL_VALVE_BODY_CLASSES and d.get("tag")
    )  # fmt: skip


def _break_valve_number(view: RuleView) -> RuleView:
    """Change the last digit of a control valve's tag, so it no longer shares its loop's number."""
    graph = view.graph.copy()
    valve = _control_valve_with_a_number(graph)
    tag = graph.nodes[valve]["tag"]
    graph.nodes[valve]["tag"] = tag[:-1] + ("8" if tag[-1] == "9" else "9")
    return replace(view, graph=graph)


def _break_spare_naming(view: RuleView) -> RuleView:
    """Flip one on-off valve from `XV` to `YV` (or back): its train now mixes both letters."""
    graph = view.graph.copy()
    valve = next(
        n for n, d in sorted(graph.nodes(data=True))
        if d["node_class"] in CONTROL_VALVE_BODY_CLASSES and str(d.get("tag", "")).startswith("XV-")
    )  # fmt: skip
    graph.nodes[valve]["tag"] = "Y" + graph.nodes[valve]["tag"][1:]
    return replace(view, graph=graph)


_MUTATIONS: dict[str, Callable[[RuleView], RuleView]] = {
    "TOG175-PUMP-TRIM": _break_pump_trim,
    "TOG219-PD-RELIEF": _break_pd_relief,
    "TOG219-VESSEL-PSV": _break_vessel_psv,
    "PLT-PHASE": _break_phase,
    "LIP1-1.1-SHARED-LOOP-NUMBER": _break_loop_number,
    "TOG113-AUTOMATIC-VALVE-LETTERS": _break_valve_number,
    "TOG28-SPARE-NAMING": _break_spare_naming,
}


def test_every_wired_rule_has_a_mutation_test() -> None:
    assert sorted(_MUTATIONS) == sorted(_WIRED)


@pytest.mark.parametrize("rule_id", _WIRED)
def test_a_wired_rule_catches_a_plant_broken_on_purpose(rule_id: str) -> None:
    broken = _MUTATIONS[rule_id](_view(1))
    result = _run(rule_id, broken)
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.rule_id == rule_id and violation.node_id and violation.detail


# ---- the plant report ----------------------------------------------------------------------------


def test_verify_plant_reports_every_wired_rule_without_violations() -> None:
    report = verify_plant(_view(1).generated)
    assert report.generator_version == "v2.1"
    assert [row.rule_id for row in report.rows] == _ALL_WIRED
    assert all(row.violations == 0 and row.checked >= 0 for row in report.rows)
    raise_on_violations(report)


def test_a_report_with_a_violation_raises_naming_the_rule() -> None:
    broken = _break_pump_trim(_view(1))
    report = verify_view(broken, "v2.1")
    with pytest.raises(RuleViolationError, match="TOG175-PUMP-TRIM"):
        raise_on_violations(report)


def test_a_failing_invariant_that_is_not_an_assertion_is_not_swallowed() -> None:
    """Only `AssertionError` means 'the plant is wrong'; any other error is a bug and propagates."""
    view = _view(1)
    roles = {n: r for n, r in view.roles.items() if r != "pd_relief_valve"}
    with pytest.raises(ValueError):
        checks_rules.check_pd_relief(replace(view, roles=roles))
