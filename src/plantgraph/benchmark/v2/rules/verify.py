"""Run the registry's checks on a generated plant (design 3.3).

Only rules with a wired check run; a rule whose check is still `pending:<task>` is absent from the
report, and `pending_rules()` lists them. `generate_plant_v2` calls `verify_generated` for a v2.2
config only: v2.1 generation stays untouched, so v2.1 plants are verified in tests alone.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.generate import GeneratedPlantV2
from plantgraph.benchmark.v2.rules import owed
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
        owed_by=owed.OWED_FIXES.get(rule.rule_id) if result.violations else None,
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
    """Raise `RuleViolationError` when any row has a violation, an owed rule's included."""
    _raise_on(report, [row for row in report.rows if row.violations])


def verify_generated(generated: GeneratedPlantV2) -> RuleReport:
    """Verify a freshly generated plant; raise on any violation of a rule that is not owed.

    A violation of an owed rule (`owed.py`) stays in the report, marked with its task.
    """
    report = verify_plant(generated)
    _raise_on(report, [row for row in report.rows if row.violations and row.owed_by is None])
    return report


def _raise_on(report: RuleReport, broken: list[RuleRow]) -> None:
    if broken:
        names = ", ".join(f"{row.rule_id} ({row.violations})" for row in broken[:5])
        raise RuleViolationError(f"expected a plant without rule violations, found: {names}")
