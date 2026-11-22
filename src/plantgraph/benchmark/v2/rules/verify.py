"""Run the registry's checks on a generated plant (design 3.3).

Only rules with a wired check run; a rule whose check is still `pending:<task>` is absent from the
report, and `pending_rules()` lists them. `verify_plant` is not called by `generate_plant_v2` yet:
v2.1 generation must stay untouched, and the v2.2 generator it guards does not exist (task T2).
"""

from __future__ import annotations

from plantgraph.benchmark.v2.generate import GeneratedPlantV2
from plantgraph.benchmark.v2.rules.catalogue import rules_with_status
from plantgraph.benchmark.v2.rules.registry import (
    CheckResult,
    HandbookRule,
    RuleReport,
    RuleRow,
    RuleStatus,
    is_pending,
    resolve_check,
)
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view


class RuleViolationError(Exception):
    """A generated plant breaks at least one rule; the message names the first few."""


def wired_rules() -> tuple[HandbookRule, ...]:
    """Encoded rules whose check exists today."""
    return tuple(r for r in rules_with_status(RuleStatus.ENCODED) if not is_pending(r))


def pending_rules() -> tuple[HandbookRule, ...]:
    """Encoded rules whose check a later task still owes."""
    return tuple(r for r in rules_with_status(RuleStatus.ENCODED) if is_pending(r))


def run_rule(rule: HandbookRule, view: RuleView) -> CheckResult:
    """Run one wired rule's check."""
    return resolve_check(rule)(view)


def _row(rule: HandbookRule, result: CheckResult) -> RuleRow:
    return RuleRow(
        rule_id=rule.rule_id,
        checked=result.checked,
        violations=len(result.violations),
        exceptions=result.exceptions,
    )


def verify_view(view: RuleView, generator_version: str) -> RuleReport:
    """The report of every wired rule on one view."""
    rows = tuple(_row(rule, run_rule(rule, view)) for rule in wired_rules())
    return RuleReport(generator_version=generator_version, rows=rows)


def verify_plant(generated: GeneratedPlantV2) -> RuleReport:
    """The rule report of a generated plant."""
    version = generated.plan.config.generator_version
    return verify_view(build_rule_view(generated), version)


def raise_on_violations(report: RuleReport) -> None:
    """Raise `RuleViolationError` when any row has a violation."""
    broken = [row for row in report.rows if row.violations]
    if broken:
        names = ", ".join(f"{row.rule_id} ({row.violations})" for row in broken[:5])
        raise RuleViolationError(f"expected a plant without rule violations, found: {names}")
