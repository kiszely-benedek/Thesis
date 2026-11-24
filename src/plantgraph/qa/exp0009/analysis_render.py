"""The Markdown text of the sealed analysis: claims first, then the descriptive tables.

Differences of accuracy are printed in percentage points of acc@C with their 95 % interval; K3's
latency in seconds. Every claim line ends with the run folders it was computed from.
"""

from __future__ import annotations

from plantgraph.qa.cascade.stats import Interval
from plantgraph.qa.exp0009.analysis_models import (
    AnalysisReport,
    ClaimRow,
    PlantRecord,
    Table,
    TableCell,
)


def _interval_text(row: ClaimRow) -> str:
    interval: Interval | None = row.interval
    if interval is None:
        return "-"
    if row.unit == "seconds":
        return f"{interval.estimate:.1f} s [{interval.ci_low:.1f}, {interval.ci_high:.1f}]"
    scale = 100  # accuracy shares are shown as points
    low, high = interval.ci_low * scale, interval.ci_high * scale
    return f"{interval.estimate * scale:+.1f} [{low:+.1f}, {high:+.1f}]"


def _cell(value: TableCell) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _claims_table(claims: list[ClaimRow]) -> list[str]:
    lines = [
        "| claim | arm | scope | verdict | estimate [95 % interval] | questions | rule |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in claims:
        n = "-" if c.n_questions is None else str(c.n_questions)
        verdict = f"{c.status.value} | {_interval_text(c)} | {n}"
        lines.append(f"| {c.claim} | {c.arm} | {c.scope} | {verdict} | {c.rule} |")
    return lines


def _claim_details(claims: list[ClaimRow]) -> list[str]:
    lines = []
    for c in claims:
        runs = f"{len(c.runs)} runs: {', '.join(c.runs)}" if c.runs else "no runs"
        note = f"{c.detail} ({runs})" if c.detail else f"({runs})"
        lines.append(f"- **{c.claim}**: {note}")
    return lines


def _plants_table(plants: list[PlantRecord]) -> list[str]:
    lines = [
        "| plant | scale | sheets | A2 runs | B runs | A2 questions | B questions |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in plants:
        b_runs = ", ".join(p.b_runs) or "not run"
        lines.append(
            f"| {p.plant_id} | {p.scale} | {p.sheets} | {', '.join(p.a2_runs)} | {b_runs} "
            f"| {p.n_a2_questions} | {p.n_b_questions} |"
        )
    return lines


def _table(table: Table) -> list[str]:
    lines = [f"### {table.title}", ""]
    if table.note:
        lines += [table.note, ""]
    lines += ["| " + " | ".join(table.header) + " |", "|" + "---|" * len(table.header)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in table.rows]
    return lines + [""]


def render_markdown(report: AnalysisReport) -> str:
    """The whole report as one Markdown document."""
    b_text = "B ran sealed" if report.b_sealed else "B was not run sealed (G1-B or G1-B2 failed)"
    lines = [
        "# EXP-0009 sealed analysis (T17)", "",
        f"Root `{report.root}`. {b_text}. {report.scope_note}", "",
        "## Claims", "", *_claims_table(report.claims), "",
        "Differences are percentage points of acc@C (K3: seconds), 95 % two-stage cluster "
        "bootstrap (5,000 resamples, seed 1).", "",
        *_claim_details(report.claims), "",
    ]  # fmt: skip
    if report.exp0008_verdicts:
        lines += ["### EXP-0008's own verdict lines for V2T-A2 (cost elasticity included)", ""]
        lines += [f"- {text}" for text in report.exp0008_verdicts] + [""]
    lines += ["## Runs", "", *_plants_table(report.plants), "", "## Descriptive tables", ""]
    for table in report.tables:
        lines += _table(table)
    if report.notes:
        lines += ["## Notes", "", *[f"- {note}" for note in report.notes], ""]
    return "\n".join(lines)
