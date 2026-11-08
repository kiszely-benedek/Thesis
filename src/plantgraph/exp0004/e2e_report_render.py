"""Markdown for the E2E report: plain tables."""

from __future__ import annotations

from plantgraph.exp0004.e2e_report_models import ArmRow, E2EReport, GroupRow
from plantgraph.qa.cascade.report_table import table


def _r3(value: float) -> str:
    """A number for the Markdown: 3 decimals (report.json keeps full precision)."""
    return f"{value:.3f}"


def _interval(estimate: float, low: float, high: float) -> str:
    return f"{_r3(estimate)} [{_r3(low)}, {_r3(high)}]"


def _claims_table(report: E2EReport) -> list[str]:
    pooled = report.n_plants > 1
    rows = [
        [
            c.claim,
            c.description,
            _interval(c.difference.mean, c.difference.ci_low, c.difference.ci_high),
            c.rule,
            "PASS" if c.passed else "FAIL",
            *([f"{c.n_same_sign} of {c.n_plants}"] if pooled else []),
        ]
        for c in report.claims
    ]
    header = ["Claim", "Difference", "Estimate [95% CI]", "Pass if", "Verdict"]
    return table([*header, *(["Plants with the pooled sign"] if pooled else [])], rows)


def _plants_table(report: E2EReport) -> list[str]:
    """Each plant's accuracies first: a row per plant, a `correct/n (Wilson CI)` cell per arm."""
    if not report.plants:
        return []
    labels = [a.label for a in report.arms]
    rows = [
        [p.plant_id, *(f"{a.n_correct}/{a.n} {_interval(*_wilson(a))}" for a in p.arms)]
        for p in report.plants
    ]
    return ["## Accuracy per plant", "", *table(["Plant", *labels], rows)]


def _wilson(arm: ArmRow) -> tuple[float, float, float]:
    return arm.accuracy.estimate, arm.accuracy.ci_low, arm.accuracy.ci_high


def _arms_table(report: E2EReport) -> list[str]:
    rows = [
        [
            a.label,
            str(a.n),
            str(a.n_correct),
            _interval(a.accuracy.estimate, a.accuracy.ci_low, a.accuracy.ci_high),
            f"{a.spend_usd:.4f}",
        ]
        for a in report.arms
    ]
    return table(
        [
            "Arm",
            "n",
            "correct@cutoff",
            "acc@cutoff (two-stage bootstrap 95% CI)"
            if report.n_plants > 1
            else "acc@cutoff (Wilson 95% CI)",
            "New spend USD (cache misses)",
        ],
        rows,
    )


def _group_cell(row: GroupRow) -> str:
    share = _r3(row.n_correct / row.n) if row.n else "n/a"
    return f"{row.n_correct}/{row.n} ({share})"


def _group_row(group: str, arms: list[str], by_key: dict[tuple[str, str], GroupRow]) -> list[str]:
    return [group, *(_group_cell(by_key[(group, arm)]) for arm in arms)]


def _group_table(rows: list[GroupRow], arms: list[str], title: str) -> list[str]:
    """One row per group, one `correct/n (accuracy)` cell per arm."""
    groups = list(dict.fromkeys(r.group for r in rows))
    by_key = {(r.group, r.arm): r for r in rows}
    return table([title, *arms], [_group_row(g, arms, by_key) for g in groups])


def _outcome_rows(arm: str, tiers: dict[str, dict[str, int]]) -> list[list[str]]:
    return [
        [arm, tier, ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))]
        for tier, counts in tiers.items()
    ]


def _outcome_table(report: E2EReport) -> list[str]:
    rows = [row for arm, tiers in report.outcomes.items() for row in _outcome_rows(arm, tiers)]
    return table(["Arm", "Tier", "Outcomes (questions)"], rows)


def render_markdown(report: E2EReport) -> str:
    """The whole report as Markdown."""
    arms = [a.label for a in report.arms]
    lines = [
        "# EXP-0004 end-to-end report",
        "",
        f"System: `{report.policy}`, accuracy at the {report.cutoff_s:g} s cutoff (acc@cutoff), "
        f"{report.n_questions} questions per arm"
        f"{f' over {report.n_plants} plants' if report.n_plants > 1 else ''}, "
        "paired by question id.",
        "",
        "## Pre-registered claims",
        "",
        *_claims_table(report),
        *_plants_table(report),
        "## Accuracy per arm" + (" (pooled over the plants)" if report.n_plants > 1 else ""),
        "",
        *_arms_table(report),
        "## Accuracy per question family (correct/n)",
        "",
        *_group_table(report.families, arms, "Family"),
        "## Exposed vs unexposed (correct/n)",
        "",
        *_group_table(report.exposure, arms, "Group"),
        "## Tier outcomes",
        "",
        *_outcome_table(report),
        "## Notes",
        "",
        *[f"- {note}" for note in report.notes],
        "",
    ]
    return "\n".join(lines)
