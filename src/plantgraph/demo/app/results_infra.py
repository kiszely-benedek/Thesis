"""The Results tab's infrastructure and end-to-end views, projected from their report files."""

from __future__ import annotations

import re
from collections.abc import Sequence

from plantgraph.demo.app.config import E2ESource, InfraSource
from plantgraph.demo.app.results_reports import (
    E2EArmRow,
    E2EClaim,
    E2EReport,
    GrowthRow,
    InfraCheck,
    InfraReport,
    provenance,
    read_report,
)
from plantgraph.demo.app.results_views import (
    ClaimLine,
    E2EArm,
    E2EView,
    InfraRowView,
    InfraView,
    IntervalMethod,
)

POOLED = "pooled"

#: Most check names start with their id ("M1 replay answers ..."); "Old-run rows" has none.
_CHECK_ID = re.compile(r"^M\d+\b")


def infra_view(source: InfraSource) -> InfraView:
    """Project the configured growth rows (in config order) and every self-check.

    Raises:
        ValueError: a configured row name is not in the report's `growth`.
    """
    report = read_report(source.report, InfraReport)
    by_name = {row.name: row for row in report.growth}
    unknown = [row.name for row in source.rows if row.name not in by_name]
    if unknown:
        raise ValueError(
            f"expected the configured infra rows to be in {source.report}, "
            f"found no growth row named {unknown} (known: {sorted(by_name)})"
        )
    rows = tuple(
        _infra_row(by_name[configured.name], configured.unit) for configured in source.rows
    )
    return InfraView(
        rows=rows,
        checks=tuple(_check_line(check) for check in report.checks),
        machine=report.machine_summary,
        source=provenance(source.report, source.result_row),
    )


def _infra_row(growth: GrowthRow, unit: str) -> InfraRowView:
    return InfraRowView(unit=unit, **growth.model_dump())


def _check_line(check: InfraCheck) -> ClaimLine:
    found = _CHECK_ID.match(check.name)
    return ClaimLine(
        claim_id=found.group(0) if found else check.name,
        verdict=check.status.upper(),
        text=f"{check.name}: {check.detail}",
    )


def _arms(
    rows: Sequence[E2EArmRow], wanted: Sequence[str], corpus: str, method: IntervalMethod
) -> tuple[E2EArm, ...]:
    by_label = {row.label: row for row in rows}
    missing = [label for label in wanted if label not in by_label]
    if missing:
        raise ValueError(
            f"expected arms {list(wanted)} for {corpus!r} in the e2e report, found no {missing} "
            f"(known: {sorted(by_label)})"
        )
    return tuple(
        E2EArm(
            label=label,
            corpus=corpus,
            n=by_label[label].n,
            n_correct=by_label[label].n_correct,
            accuracy=by_label[label].accuracy,
            interval_method=method,
        )
        for label in wanted
    )


def _e2e_claim_line(claim: E2EClaim) -> ClaimLine:
    diff = claim.difference
    return ClaimLine(
        claim_id=claim.claim,
        verdict="PASS" if claim.passed else "FAIL",
        text=(
            f"{claim.description}: {diff.mean:+.3f} [{diff.ci_low:+.3f}, {diff.ci_high:+.3f}]"
            f"; rule: {claim.rule}"
        ),
    )


def e2e_view(source: E2ESource) -> E2EView:
    """Project the pooled arms, the configured plant's arms and the claim lines.

    Raises:
        ValueError: a configured arm or the configured plant is not in the report.
    """
    report = read_report(source.report, E2EReport)
    # a pooled figure resamples plants too; a single plant gets the closed-form Wilson interval
    arms = _arms(report.arms, source.arms, POOLED, "two-stage bootstrap")
    if source.plant is not None:
        plants = {plant.plant_id: plant for plant in report.plants}
        if source.plant not in plants:
            raise ValueError(
                f"expected plant {source.plant!r} in {source.report}, found {sorted(plants)}"
            )
        arms += _arms(plants[source.plant].arms, source.arms, source.plant, "wilson")
    return E2EView(
        arms=arms,
        claims=tuple(_e2e_claim_line(claim) for claim in report.claims),
        source=provenance(source.report, source.result_row),
    )
