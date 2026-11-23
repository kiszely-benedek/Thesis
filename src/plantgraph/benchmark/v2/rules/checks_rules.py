"""Registry checks for the rules the v2.1 invariants already verify (design 3.3).

The S1-S24 checks (`checks_v21.py`) stop at the first problem by raising `AssertionError`. Each
function here runs one or two of them on a `RuleView` and reports in the registry's own types, so
`verify_plant` treats every rule alike. A failed invariant becomes one `Violation`; its `node_id` is
read from the assertion message when it starts with `<node id>:`, else `(plant)`. The `detail`
(the full message) is the authority.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from plantgraph.benchmark.v2.rules import checks_v21
from plantgraph.benchmark.v2.rules.checks_documents import check_document_conventions
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView

_COUNTING = Callable[[RuleView], int]
#: a message that starts `<node id>:` or `<node id>,` names its offender; others are plant-wide
_LEADING_NODE_ID = re.compile(r"^([^\s:,()\[\]{}]+)(?::|,|$)")
_WHOLE_PLANT = "(plant)"


def _violation(rule_id: str, error: AssertionError) -> Violation:
    detail = str(error) or "assertion failed"
    match = _LEADING_NODE_ID.match(detail)
    return Violation(
        rule_id=rule_id, node_id=match.group(1) if match else _WHOLE_PLANT, detail=detail
    )


def _run(rule_id: str, view: RuleView, *invariants: _COUNTING) -> CheckResult:
    """Run the invariants in order; the first failure ends the run with one violation."""
    checked = 0
    try:
        for invariant in invariants:
            checked += invariant(view)
    except AssertionError as error:
        return CheckResult(checked=checked, violations=(_violation(rule_id, error),))
    return CheckResult(checked=checked)


def _solenoids(view: RuleView) -> dict[str, str | None]:
    """On-off valve id -> the sub-tag of its solenoid, read from the DEXPI model."""
    systems = view.model.conceptualModel.actuatingSystems  # type: ignore[union-attr]
    return {
        s.operatedValveReference.valve.id: (  # type: ignore[union-attr]
            s.controlledActuator.subTagName if s.controlledActuator else None
        )
        for s in systems
    }


def _s7(view: RuleView) -> int:
    return checks_v21.check_s7(view.graph, _solenoids(view))


def _graph_check(invariant: Callable[..., int]) -> _COUNTING:
    return lambda view: invariant(view.graph)


def check_pump_trim(view: RuleView) -> CheckResult:
    """TOG175-PUMP-TRIM: S1 (suction) and S2 (discharge); S2 is a v2.1 rule, see the catalogue."""
    return _run("TOG175-PUMP-TRIM", view, checks_v21.check_s1, checks_v21.check_s2)


def check_pd_relief(view: RuleView) -> CheckResult:
    """TOG219-PD-RELIEF: S3."""
    return _run("TOG219-PD-RELIEF", view, checks_v21.check_s3)


def check_vessel_psv(view: RuleView) -> CheckResult:
    """TOG219-VESSEL-PSV: S6 (the condensate drain pot is exempt)."""
    return _run("TOG219-VESSEL-PSV", view, checks_v21.check_s6)


def check_phase(view: RuleView) -> CheckResult:
    """PLT-PHASE: S12."""
    return _run("PLT-PHASE", view, checks_v21.check_s12)


def check_shared_loop_number(view: RuleView) -> CheckResult:
    """LIP1-1.1-SHARED-LOOP-NUMBER: S4 (valve) and S8 (sensor, bubble, actuator)."""
    return _run(
        "LIP1-1.1-SHARED-LOOP-NUMBER",
        view,
        _graph_check(checks_v21.check_s4),
        _graph_check(checks_v21.check_s8),
    )


def check_automatic_valve_letters(view: RuleView) -> CheckResult:
    """TOG113-AUTOMATIC-VALVE-LETTERS: S4 (control-valve letters) and S7 (on-off valves)."""
    return _run("TOG113-AUTOMATIC-VALVE-LETTERS", view, _graph_check(checks_v21.check_s4), _s7)


def check_spare_naming(view: RuleView) -> CheckResult:
    """TOG28-SPARE-NAMING: S23 per train, and every train keeps its document's convention."""
    return _run("TOG28-SPARE-NAMING", view, checks_v21.check_s23, check_document_conventions)
