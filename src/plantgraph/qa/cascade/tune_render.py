"""Render a `TuneReport` as Markdown (the JSON is `TuneReport.model_dump_json`)."""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.cascade.report_table import table
from plantgraph.qa.cascade.tune_models import SECONDARY_CUTOFFS_S, FamilyChange, TuneReport


def render_tune_report(report: TuneReport, changes: list[FamilyChange] | None = None) -> str:
    """The report as Markdown; `changes` (vs the previous round) adds a per-family delta table."""
    setting = report.setting
    limit_kind = "question deadline" if setting.question_deadline_s else "hang guard"
    lines = [
        f"# V2T tuning: {report.corpus_id}, setting {setting.name}",
        "",
        f"Cypher timeout {setting.cypher_timeout_s:g} s; limit {setting.cutoff_s:g} s "
        f"({limit_kind}). {report.n_questions} questions. Primary number: uncut accuracy.",
        "",
        *_variant_table(report),
        *_cypher_lines(report),
        *_choice_lines(report),
    ]
    if changes is not None:
        lines += _change_table(changes)
    return "\n".join(lines) + "\n"


def write_tune_report(
    report: TuneReport, out_dir: Path, changes: list[FamilyChange] | None = None
) -> tuple[Path, Path]:
    """Write `tune_report.md` and `tune_report.json` into `out_dir`; return both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown, json_path = out_dir / "tune_report.md", out_dir / "tune_report.json"
    markdown.write_text(render_tune_report(report, changes), encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return markdown, json_path


def _variant_table(report: TuneReport) -> list[str]:
    secondary = [f"acc@{c:g}" for c in SECONDARY_CUTOFFS_S]
    header = ["policy", "uncut", *secondary, "in limit", "beyond", "oracle gap", "p50 s", "p90 s"]
    rows = []
    for result in report.results.values():
        n = result.n_questions
        within = [f"{result.n_correct_within[f'{c:g}']}/{n}" for c in SECONDARY_CUTOFFS_S]
        rows.append(
            [
                result.policy,
                f"{result.n_correct_uncut}/{n}",
                *within,
                f"{result.n_correct_in_limit}/{n}",
                str(result.n_beyond_limit),
                str(report.oracle_correct - result.n_correct_uncut),
                f"{result.latency_median_s:.1f}",
                f"{result.latency_p90_s:.1f}",
            ]
        )
    return table(header, rows)


def _cypher_lines(report: TuneReport) -> list[str]:
    cypher = report.cypher
    rejected = ", ".join(f"{rule} {n}" for rule, n in sorted(cypher.rejected_by.items())) or "none"
    return [
        f"Cypher tier: {cypher.n_accepted}/{cypher.n_tried} accepted "
        f"({cypher.n_accepted_correct} correct); rejected by rule: {rejected}; "
        f"correct answers rejected only for being cut at the row cap: {cypher.n_cut_but_correct}.",
        "",
        f"Oracle (either tier correct): {report.oracle_correct}/{report.n_questions}.",
        "",
    ]


def _choice_lines(report: TuneReport) -> list[str]:
    choice = report.choice
    if choice is None:
        return ["Variant choice: not defined here (the rule is fixed on the tuning set only).", ""]
    return [
        f"Variant choice: **{choice.chosen}** ({choice.rule}; "
        f"v4 {choice.n_correct_v4}, v4_iso {choice.n_correct_v4_iso} of {choice.n_questions}).",
        "",
    ]


def _change_table(changes: list[FamilyChange]) -> list[str]:
    rows = [[c.family, str(c.previous), str(c.current), f"{c.delta:+d}"] for c in changes]
    header = ["family", "before", "now", "change"]
    return ["Per family vs the previous round (cascade_v4):", "", *table(header, rows)]
