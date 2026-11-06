"""Markdown for the E2E report: plain tables."""

from __future__ import annotations

from plantgraph.exp0004.e2e_report_models import E2EReport, GroupRow


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines + [""]


def _claims_table(report: E2EReport) -> list[str]:
    rows = [
        [
            c.claim,
            c.description,
            f"{c.difference.mean} [{c.difference.ci_low}, {c.difference.ci_high}]",
            c.rule,
            "PASS" if c.passed else "FAIL",
        ]
        for c in report.claims
    ]
    return _table(["Claim", "Difference", "Estimate [95% CI]", "Pass if", "Verdict"], rows)


def _arms_table(report: E2EReport) -> list[str]:
    rows = [
        [
            a.label,
            str(a.n),
            str(a.n_correct),
            f"{a.accuracy.estimate} [{a.accuracy.ci_low}, {a.accuracy.ci_high}]",
            f"{a.spend_usd:.4f}",
        ]
        for a in report.arms
    ]
    return _table(["Arm", "n", "correct@cutoff", "acc@cutoff (Wilson 95% CI)", "Spend USD"], rows)


def _group_table(rows: list[GroupRow], arms: list[str], title: str) -> list[str]:
    """One row per group, one `correct/n (accuracy)` cell per arm."""
    groups = list(dict.fromkeys(r.group for r in rows))
    by_key = {(r.group, r.arm): r for r in rows}
    body = []
    for group in groups:
        cells = []
        for arm in arms:
            row = by_key[(group, arm)]
            share = row.n_correct / row.n if row.n else float("nan")
            cells.append(f"{row.n_correct}/{row.n} ({share})")
        body.append([group, *cells])
    return _table([title, *arms], body)


def _outcome_table(report: E2EReport) -> list[str]:
    rows = []
    for arm, tiers in report.outcomes.items():
        for tier, counts in tiers.items():
            rows.append([arm, tier, ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))])
    return _table(["Arm", "Tier", "Outcomes (questions)"], rows)


def render_markdown(report: E2EReport) -> str:
    """The whole report as Markdown."""
    arms = [a.label for a in report.arms]
    lines = [
        "# EXP-0004 end-to-end report",
        "",
        f"System: `{report.policy}`, accuracy at the {report.cutoff_s:g} s cutoff (acc@cutoff), "
        f"{report.n_questions} questions per arm, paired by question id.",
        "",
        "## Pre-registered claims",
        "",
        *_claims_table(report),
        "## Accuracy per arm",
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
