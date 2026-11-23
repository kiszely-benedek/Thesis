"""Checks of the v2.2 min-flow rules that follow a pump's hidden power band (Toghraei 2019).

A centrifugal pump of at least 5 hp gets a **min-flow line** (spillback): a line that returns liquid
to the suction vessel so the pump never runs against a closed valve. The power in horsepower (hp) is
not on any drawing; the generator draws it as a **band** and keeps it in `HiddenDesignState`
(`view.hidden.pump_power`). These checks read the band from there and test the drawing against it.

Like `checks_pumps`, they apply to v2.2 plants with the handbook on and report `checked=0`
otherwise.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.hidden_state import PumpPowerBand
from plantgraph.benchmark.v2.rules.checks_pumps import nodes_with_role, pumps_of_classes
from plantgraph.benchmark.v2.rules.checks_v21_plant import CENTRIFUGAL_PUMP, reach
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.trims_min_flow import CONTROL_VALVE_ROLE, SWITCH_VALVE_ROLE
from plantgraph.graph.schema import Relation

_ORIFICE = "RestrictionOrifice"
#: what each method leaves in the graph: the letters of the tags that drive its valve, valve first
_SWITCH_CHAIN = ["FSLL", "FT"]  # flow transmitter -> low-low flow switch -> on-off valve
_CONTROL_CHAIN = ["FIC", "FT"]  # flow transmitter -> flow controller -> control valve
_METHOD_OF_BAND = {
    PumpPowerBand.BELOW_5: None,
    PumpPowerBand.B5_20: "restriction orifice",
    PumpPowerBand.B20_35: "switching valve",
    PumpPowerBand.ABOVE_35: "flow control loop",
}


def _band_violation(rule_id: str, pump: str) -> Violation:
    return Violation(
        rule_id=rule_id,
        node_id=pump,
        detail="expected a hidden power band for the pump, found none",
    )


def _downstream(view: RuleView, pump: str) -> set[str]:
    """The pipe parts after the pump, up to the next equipment item (includes branch lines)."""
    return reach(view.piping, view.graph, pump, up=False)[0]


# ---- TOG177-MINFLOW-NEED -----------------------------------------------------------------------


def check_minflow_need(view: RuleView) -> CheckResult:
    """TOG177-MINFLOW-NEED: a centrifugal pump has a min-flow line exactly when it is 5 hp+."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    pumps = pumps_of_classes(view, [CENTRIFUGAL_PUMP])
    violations = [problem for pump in pumps if (problem := _need_problem(view, pump))]
    return CheckResult(checked=len(pumps), violations=tuple(violations))


def _need_problem(view: RuleView, pump: str) -> Violation | None:
    rule_id = "TOG177-MINFLOW-NEED"
    band = view.hidden.pump_power.get(pump)
    if band is None:
        return _band_violation(rule_id, pump)
    needs_line = band is not PumpPowerBand.BELOW_5
    has_line = bool(nodes_with_role(view, _downstream(view, pump), ["min_flow_tee"]))
    if needs_line == has_line:
        return None
    wanted = "a min-flow line" if needs_line else "no min-flow line"
    return Violation(
        rule_id=rule_id,
        node_id=pump,
        detail=f"expected {wanted} for a pump of {band.value} hp, found "
        f"{'one' if has_line else 'none'}",
    )


# ---- TOG313-MINFLOW-METHOD ---------------------------------------------------------------------


def check_minflow_method(view: RuleView) -> CheckResult:
    """TOG313-MINFLOW-METHOD: the min-flow method is the one the pump's band prescribes."""
    if not view.handbook_enabled:
        return CheckResult(checked=0)
    pumps = pumps_of_classes(view, [CENTRIFUGAL_PUMP])
    violations = [problem for pump in pumps if (problem := _method_problem(view, pump))]
    return CheckResult(checked=len(pumps), violations=tuple(violations))


def _method_problem(view: RuleView, pump: str) -> Violation | None:
    rule_id = "TOG313-MINFLOW-METHOD"
    band = view.hidden.pump_power.get(pump)
    if band is None:
        return _band_violation(rule_id, pump)
    found = _methods_found(view, _downstream(view, pump))
    expected = {method for method in [_METHOD_OF_BAND[band]] if method is not None}
    if found == expected:
        return None
    return Violation(
        rule_id=rule_id,
        node_id=pump,
        detail=f"expected {sorted(expected) or 'no method'} for a pump of {band.value} hp, "
        f"found {sorted(found) or 'none'}",
    )


def _methods_found(view: RuleView, parts: set[str]) -> set[str]:
    """The min-flow methods the pump's discharge parts show; a broken loop does not count."""
    found = set()
    if any(view.graph.nodes[n]["node_class"] == _ORIFICE for n in parts):
        found.add("restriction orifice")
    if _has_valve_driven_by(view, parts, SWITCH_VALVE_ROLE, _SWITCH_CHAIN):
        found.add("switching valve")
    if _has_valve_driven_by(view, parts, CONTROL_VALVE_ROLE, _CONTROL_CHAIN):
        found.add("flow control loop")
    return found


def _has_valve_driven_by(view: RuleView, parts: set[str], role: str, chain: list[str]) -> bool:
    """True if a part with `role` is moved by an actuator driven by the tags in `chain`."""
    return any(
        _driver_letters(view.graph, valve) == chain
        for valve in nodes_with_role(view, parts, [role])
    )


def _driver_letters(graph: nx.DiGraph[str], valve: str) -> list[str]:
    """Tag letters of what drives `valve`, walking back: its actuator, the bubble, the sensor."""
    letters: list[str] = []
    node = valve
    # valve <- actuator (control), actuator <- bubble (signal), bubble <- sensor (signal)
    for relation in (Relation.CONTROL, Relation.SEND_SIGNAL_TO, Relation.SEND_SIGNAL_TO):
        sources = [
            s for s, _, d in graph.in_edges(node, data=True) if d["relation"] == relation.value
        ]
        if len(sources) != 1:
            return letters
        node = sources[0]
        parsed = parse_tag(graph.nodes[node].get("tag") or "")
        if parsed is not None:  # the actuator prints no tag
            letters.append(parsed.letters)
    return letters
