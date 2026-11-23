"""The plant-level checks of task T9, on plants of seeds 1-5 and on plants broken on purpose.

Per rule (design 3.3): (a) no violation on a v2.2 plant, (b) a mutation is caught, (c) the check
looked at something over the five seeds. Unlike the T3/T4 checks these also run on v2.1 plants.
Four rules fail on the plants the generator draws today; per the T9 design rule the generator was
not touched, so their (a) tests are expected failures (`xfail`, strict) that carry the reason and
one example from `t9_support.KNOWN_FAILURES`.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
import t9_mutations as mutations
from t9_support import KNOWN_FAILURES, SEEDS, T9_RULES, view_v21, view_v22

from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.view import RuleView


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _positive_cases() -> list[object]:
    """One (rule, seed) case per T9 rule and seed; a known failure is an expected failure."""
    cases = []
    for rule_id in T9_RULES:
        seeds, reason = KNOWN_FAILURES.get(rule_id, ([], ""))
        for seed in SEEDS:
            marks = [pytest.mark.xfail(reason=reason, strict=True)] if seed in seeds else []
            cases.append(pytest.param(rule_id, seed, marks=marks, id=f"{rule_id}-seed{seed}"))
    return cases


# ---- (a) positive, (c) non-vacuity ---------------------------------------------------------------


@pytest.mark.parametrize(("rule_id", "seed"), _positive_cases())
def test_a_t9_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, view_v22(seed)).violations == ()


@pytest.mark.parametrize(("rule_id", "seed"), _positive_cases())
def test_a_t9_rule_has_no_violation_on_a_v21_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, view_v21(seed)).violations == ()


@pytest.mark.parametrize("rule_id", T9_RULES)
def test_a_t9_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, view_v22(seed)).checked for seed in SEEDS) > 0


def test_the_inventory_check_found_the_exceptions_it_allows() -> None:
    codes = {c for seed in SEEDS for c in _run("TOG295-INVENTORY-ONCE", view_v22(seed)).exceptions}
    assert "storage_tank_batch" in codes
    assert any(code.startswith("pressure_floating_on:") for code in codes)


def test_the_closure_check_counts_the_declared_ends_it_lets_through() -> None:
    kinds = {k for seed in SEEDS for k in _run("PLT-STREAM-CLOSURE", view_v22(seed)).exceptions}
    assert kinds == {"end_fitting", "utility_stub"}


# ---- (b) mutations -------------------------------------------------------------------------------

_BROKEN: dict[str, list[Callable[[RuleView], mutations.Broken]]] = {
    "TOG271-ONE-CV-LIQUID": [mutations.break_one_cv_liquid],
    "TOG267-FE-UPSTREAM-FV": [mutations.break_fe_upstream_fv],
    "TOG295-INVENTORY-ONCE": [
        mutations.break_inventory_no_loop,
        mutations.break_inventory_two_loops,
    ],
    "TOG270-PUMP-FLOW-CONTROLLED": [
        mutations.break_pump_flow_uncontrolled,
        mutations.break_pump_flow_twice,
    ],
    "TOG320-HX-NONTARGET": [mutations.break_hx_nontarget],
    "TOG224-PSV-PIPE-CLEAN": [mutations.break_psv_pipe],
    "TOG24-NO-VISITING-STREAM": [mutations.break_visiting_stream],
    "PLT-STREAM-CLOSURE": [mutations.break_stream_closure],
    "TOG326-STEAM-CONDENSATE": [mutations.break_steam_condensate],
}
_BROKEN_CASES = [(rule, fn) for rule, fns in _BROKEN.items() for fn in fns]


def _mutated_names(violations: tuple[object, ...]) -> str:
    return " ".join(f"{getattr(v, 'node_id', '')} {getattr(v, 'detail', '')}" for v in violations)


@pytest.mark.parametrize(
    ("rule_id", "break_it"), _BROKEN_CASES, ids=lambda x: getattr(x, "__name__", x)
)
def test_a_t9_rule_catches_a_plant_broken_on_purpose(
    rule_id: str, break_it: Callable[[RuleView], mutations.Broken]
) -> None:
    """The break adds violations (the failing rules have some already) and one names the break."""
    view = view_v22(1)
    before = _run(rule_id, view).violations
    broken, node = break_it(view)
    result = _run(rule_id, broken)
    assert len(result.violations) > len(before)
    assert all(v.rule_id == rule_id and v.node_id and v.detail for v in result.violations)
    if not node.startswith("("):
        assert node in _mutated_names(result.violations), result.violations


def test_the_steam_condensate_check_fails_every_heater_once_the_traps_are_gone() -> None:
    view = view_v22(1)
    broken, _ = mutations.break_steam_condensate(view)
    result = _run("TOG326-STEAM-CONDENSATE", broken)
    assert result.checked > 0 and len(result.violations) == result.checked


@pytest.mark.parametrize(
    "break_it", [mutations.break_hx_isolation_valve, mutations.break_hx_bypass]
)
def test_the_exchanger_check_catches_an_isolation_valve_and_a_bypass(
    break_it: Callable[[RuleView, set[str]], mutations.Broken],
) -> None:
    view = view_v22(1)
    before = {v.node_id for v in _run("TOG207-HX-NO-ISOLATION", view).violations}
    broken, exchanger = break_it(view, before)
    after = {v.node_id for v in _run("TOG207-HX-NO-ISOLATION", broken).violations}
    assert exchanger in after - before
