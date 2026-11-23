"""Checks of the two pressure rules about what feeds an item: a check valve, a safety device.

The merge check reads the hidden pressure levels (`checks_pressure.py`, `pressure_levels.py`). A
**merge tee** is a tee where two streams join. A **pressure safety device** (PSD) is a part that
opens to relieve an enclosure that is too full: a safety valve, a rupture disc, a tank's breather
valve or open vent. An **enclosure** is a vessel, tank or column.
"""

from __future__ import annotations

from collections import deque

from plantgraph.benchmark.v2.hidden_state import SCOPE_NON_HYDROCARBON
from plantgraph.benchmark.v2.pressure_levels import VESSEL_CLASSES
from plantgraph.benchmark.v2.rules.checks_pressure import (
    NOT_APPLICABLE,
    edge_level,
    is_equipment,
    line_number_of,
    node_class,
)
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.tags import parse_line_number

_RELIEVING_CLASSES = frozenset({"RuptureDisc", "BreatherValve", "VentilationDevice"})
_CONDENSATE_POT_ROLE = "condensate_drain_pot"
_CODE_RELIEF_PATH = "relief_path"
#: TOG156 speaks of process streams tying into a container: process liquid and process gas
_SCOPE = frozenset({"P", "PG"})
_FLARE_SERVICE = "FL"
_PD_RELIEF_ROLE = "pd_relief_valve"


# ---- TOG156-MERGE-CHECK ------------------------------------------------------------------------


def _has_check_valve_behind(view: RuleView, tee: str, source: str) -> bool:
    """True when a check valve stands on the run that arrives at `tee` from `source`."""
    piping = view.piping
    number = line_number_of(view, source, tee)
    node, seen = source, set()
    while node not in seen and not is_equipment(view, node):
        if "CheckValve" in node_class(view, node):
            return True
        seen.add(node)
        before = [p for p in piping.predecessors(node) if line_number_of(view, p, node) == number]
        if len(before) != 1:
            return False
        node = before[0]
    return False


def _service(view: RuleView, upstream: str, downstream: str) -> str:
    """The service code (`P`, `FL`, `CHD`...) in the line number between two parts."""
    number = line_number_of(view, upstream, downstream)
    parsed = parse_line_number(number)
    if parsed is None:
        raise ValueError(f"expected a line number of the v2 grammar, got {number!r}")
    return parsed.service


def _is_relief_path(view: RuleView, tee: str, source: str) -> bool:
    """True when the stream into `tee` is a relief path: a flare line, or a PSV or PD relief.

    A check valve in a relief path could block the relief, so the rule leaves these alone (design
    17.13 R2; a design reading, not a page).
    """
    if _service(view, source, tee) == _FLARE_SERVICE:
        return True
    piping, number = view.piping, line_number_of(view, source, tee)
    node, seen = source, set()
    while node not in seen and not is_equipment(view, node):
        if (
            node_class(view, node).endswith("SafetyValve")
            or view.roles.get(node) == _PD_RELIEF_ROLE
        ):
            return True
        seen.add(node)
        before = [p for p in piping.predecessors(node) if line_number_of(view, p, node) == number]
        if len(before) != 1:
            return False
        node = before[0]
    return False


def _lower_streams(view: RuleView, tee: str) -> list[str]:
    """The streams into `tee` that arrive below the level it carries on."""
    (after,) = list(view.piping.successors(tee))
    carried = edge_level(view, tee, after)
    return [s for s in sorted(view.piping.predecessors(tee)) if edge_level(view, s, tee) < carried]


def _merge_problems(view: RuleView, tee: str) -> tuple[list[Violation], int]:
    """The lower streams into `tee` with no check valve, and how many relief paths were let by."""
    violations: list[Violation] = []
    relief_paths = 0
    for source in _lower_streams(view, tee):
        if _is_relief_path(view, tee, source):
            relief_paths += 1
        elif not _has_check_valve_behind(view, tee, source):
            level = edge_level(view, source, tee).name
            violations.append(
                Violation(
                    rule_id="TOG156-MERGE-CHECK",
                    node_id=tee,
                    detail=f"expected a check valve on the {level} stream from {source} tying "
                    f"into the line at {tee}, found none",
                )
            )
    return violations, relief_paths


def check_merge_check(view: RuleView) -> CheckResult:
    """TOG156-MERGE-CHECK: the lower-level process stream into a merge tee has a check valve.

    Only process lines (P, PG) are in scope, the page's context. Relief paths are counted under
    the exception code `relief_path`; closed-drain and utility collection headers are not checked.
    """
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule TOG156-MERGE-CHECK: a lower process stream tying in has a check valve (Toghraei p.156)
    piping = view.piping
    merges = sorted(
        n
        for n in piping
        if piping.in_degree(n) >= 2 and piping.out_degree(n) == 1 and not is_equipment(view, n)
    )
    scope = [t for t in merges if _service(view, t, next(iter(piping.successors(t)))) in _SCOPE]
    violations: list[Violation] = []
    relief_paths = 0
    for tee in scope:
        found, let_by = _merge_problems(view, tee)
        violations += found
        relief_paths += let_by
    return CheckResult(
        checked=len(scope),
        violations=tuple(violations),
        exceptions={_CODE_RELIEF_PATH: relief_paths} if relief_paths else {},
    )


# ---- API14C-A4-OVERPRESSURE --------------------------------------------------------------------


def _is_relieving(view: RuleView, node: str) -> bool:
    name = node_class(view, node)
    return name.endswith("SafetyValve") or name in _RELIEVING_CLASSES


def reaches_relief(view: RuleView, enclosure: str) -> bool:
    """True when a safety device hangs on the enclosure, over pipe parts only."""
    piping = view.piping
    seen, queue = {enclosure}, deque([enclosure])
    while queue:
        for nxt in piping.successors(queue.popleft()):
            if _is_relieving(view, nxt):
                return True
            if nxt not in seen and not is_equipment(view, nxt):
                seen.add(nxt)
                queue.append(nxt)
    return False


def check_overpressure(view: RuleView) -> CheckResult:
    """API14C-A4-OVERPRESSURE: every enclosure reaches a safety device, a condensate pot excepted.

    The steam condensate pots are outside A.4, which covers vessels handling hydrocarbon (A.4.1
    p.26): they are counted under the scope code `scope:non_hydrocarbon`. The SAC exceptions c.3
    and c.4 (another device protects the vessel) are not derived: every vessel carries its own.
    """
    if not view.handbook_enabled:
        return NOT_APPLICABLE
    # rule API14C-A4-OVERPRESSURE: every A.4 vessel has a PSV (API 14C A.4.2.2.1 c p.27)
    enclosures = sorted(n for n in view.piping if node_class(view, n) in VESSEL_CLASSES)
    violations: list[Violation] = []
    out_of_scope = 0
    for enclosure in enclosures:
        if reaches_relief(view, enclosure):
            continue
        if view.roles.get(enclosure) == _CONDENSATE_POT_ROLE:
            out_of_scope += 1
        else:
            violations.append(_unprotected(enclosure))
    return CheckResult(
        checked=len(enclosures),
        violations=tuple(violations),
        exceptions={SCOPE_NON_HYDROCARBON: out_of_scope} if out_of_scope else {},
    )


def _unprotected(enclosure: str) -> Violation:
    return Violation(
        rule_id="API14C-A4-OVERPRESSURE",
        node_id=enclosure,
        detail="expected a safety device on the A.4 vessel (API 14C A.4.2.2.1 c), found none",
    )
