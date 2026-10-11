"""Write the EXP-0001 report as markdown, JSON and the figure's CSV files (design section 8)."""

from __future__ import annotations

import csv
from pathlib import Path

from plantgraph.qa.exp0001.ladder_stats import log10_sheets
from plantgraph.qa.exp0001.report_models import ArmCell, LadderReport, PairedDelta, SizePoint, Trend

FIGURE_COLUMNS = [
    "corpus_id", "n_sheets", "log10_sheets", "arm", "scope", "n",
    "acc_at_120", "acc_ci_low", "acc_ci_high", "cost_mean", "latency_median",
]  # fmt: skip


def write_report(report: LadderReport, out_dir: Path, h1000_sheets: int = 1001) -> list[Path]:
    """Write `report.md`, `report.json`, `figure.csv` and `figure_marks.csv` into `out_dir`.

    The marks file holds the figure's vertical lines: the H1000 wall and X5's fitted wall.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "report.md": render_markdown(report),
        "report.json": report.model_dump_json(indent=2),
    }
    for name, text in paths.items():
        (out_dir / name).write_text(text + "\n", encoding="utf-8")
    figure = _write_figure(report, out_dir / "figure.csv")
    marks = _write_marks(out_dir / "figure_marks.csv", report.wall_sheets, h1000_sheets)
    return [out_dir / "report.md", out_dir / "report.json", figure, marks]


def _write_figure(report: LadderReport, path: Path) -> Path:
    sheets = {s.corpus_id: s.n_sheets for s in report.sizes}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIGURE_COLUMNS)
        writer.writerows(_figure_row(c, sheets[c.corpus_id]) for c in report.cells)
    return path


def _figure_row(c: ArmCell, n_sheets: int) -> list[object]:
    acc = c.acc_at_120
    position = f"{log10_sheets(n_sheets):.4f}"
    cost, latency = c.cost_mean, c.latency_median
    head = [c.corpus_id, n_sheets, position, c.policy, c.scope, c.n]
    return [*head, acc.estimate, acc.ci_low, acc.ci_high, cost, latency]


def _write_marks(path: Path, wall_sheets: float | None, h1000_sheets: int) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mark", "sheets", "log10_sheets"])
        writer.writerow(["H1000_does_not_fit", h1000_sheets, f"{log10_sheets(h1000_sheets):.4f}"])
        if wall_sheets is not None:
            writer.writerow(
                ["context_wall_W", f"{wall_sheets:.0f}", f"{log10_sheets(round(wall_sheets)):.4f}"]
            )
    return path


def render_markdown(report: LadderReport) -> str:
    """The whole report as one markdown document."""
    parts = [
        "# EXP-0001 report",
        f"Cutoff {report.cutoff_s:g} s (acc@{report.cutoff_s:g}); paired bootstrap "
        f"{report.n_boot} resamples, seed {report.seed}, 95 % percentile CI.",
        "## Claims",
        _claims_table(report),
        "## Corpus sizes",
        _sizes_table(report.sizes),
        "## Arms per size",
        _cells_table(report.cells),
        "## Paired differences",
        _deltas_table(report),
        "## Trend over log10(sheets)",
        _trend_table(report),
        "## Scopes",
        _scopes_text(report),
        "## Arms or sizes not scored",
        "\n".join(f"- {line}" for line in report.absent) or "none",
    ]
    return "\n\n".join(parts)


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _claims_table(report: LadderReport) -> str:
    rows = [[c.id, c.wording, c.value, c.verdict] for c in report.claims]
    return _table(["Id", "Claim", "Value", "Verdict"], rows)


def _optional(value: float | int | None, spec: str = "") -> str:
    return "-" if value is None else format(value, spec)


def _sizes_table(sizes: list[SizePoint]) -> str:
    header = ["Corpus", "Sheets", "Occurrence nodes", "ctx prompt chars", "Median prompt tokens"]
    header.append("Chars/token")
    return _table(header, [_size_row(s) for s in sizes])


def _size_row(s: SizePoint) -> list[str]:
    return [
        s.corpus_id,
        str(s.n_sheets),
        str(s.n_occurrence_nodes),
        _optional(s.ctx_prompt_chars, ","),
        _optional(s.ctx_prompt_tokens_median, ","),
        _optional(s.chars_per_token, ".2f"),
    ]


def _cells_table(cells: list[ArmCell]) -> str:
    header = ["Corpus", "Arm", "Scope", "n", "acc@cutoff [95% CI]", "Uncut"]
    header += ["$/q mean (median)", "Latency median / p90 s", "Outcomes"]
    return _table(header, [_cell_row(c) for c in cells])


def _cell_row(c: ArmCell) -> list[str]:
    acc = c.acc_at_120
    outcomes = ", ".join(f"{name} {count}" for name, count in c.outcomes.items() if count)
    return [
        c.corpus_id,
        c.policy,
        c.scope,
        str(c.n),
        f"{acc.estimate:.3f} [{acc.ci_low:.3f}, {acc.ci_high:.3f}]",
        f"{c.acc_uncut:.3f}",
        f"{c.cost_mean:.5f} ({c.cost_median:.5f})",
        f"{c.latency_median:.1f} / {c.latency_p90:.1f}",
        outcomes,
    ]


def _deltas_table(report: LadderReport) -> str:
    header = ["Corpus", "Scope", "Difference", "Metric", "n", "Delta", "95% CI"]
    return _table(header, [_delta_row(d) for d in report.deltas])


def _delta_row(d: PairedDelta) -> list[str]:
    return [
        d.corpus_id,
        d.scope,
        f"{d.a} - {d.b}",
        d.metric,
        str(d.n),
        f"{d.delta:+.5f}",
        f"[{d.ci.ci_low:+.5f}, {d.ci.ci_high:+.5f}]",
    ]


def _trend_table(report: LadderReport) -> str:
    if not report.trends:
        return "not computed: fewer than two ladder sizes have both arms"
    return _table(
        ["Scope", "Sizes", "Slope", "95% CI", "Resamples", "Seed"],
        [_trend_row(t) for t in report.trends],
    )


def _trend_row(t: Trend) -> list[str]:
    interval = f"[{t.ci.ci_low:+.4f}, {t.ci.ci_high:+.4f}]"
    return [t.scope, ", ".join(t.sizes), f"{t.slope:+.4f}", interval, str(t.n_boot), str(t.seed)]


def _scopes_text(report: LadderReport) -> str:
    return "\n".join(
        f"- **{name}** ({len(families)} families): {', '.join(families)}"
        for name, families in report.scope_families.items()
    )
