"""Render the cascade `Report` as Markdown and write it, with the JSON, to an output directory."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from plantgraph.qa.cascade.evaluate import Comparison, Summary
from plantgraph.qa.cascade.report_models import (
    Cell,
    CorpusReport,
    PolicyResult,
    Report,
    Tier3Tally,
    Verdict,
)
from plantgraph.qa.cascade.stats import PairedDifference


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """A Markdown table as lines."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return lines + [""]


def _shares(summary: Summary) -> str:
    ordered = sorted(summary.tier_shares.items(), key=lambda item: -item[1])
    return ", ".join(f"{tier} {share:.0%}" for tier, share in ordered)


def _interval(diff: PairedDifference, fmt: str) -> str:
    return f"{diff.mean:{fmt}} [{diff.ci_low:{fmt}}, {diff.ci_high:{fmt}}]"


def _policy_rows(corpus: CorpusReport) -> list[list[str]]:
    rows = []
    for result in corpus.policies:
        s = result.summary
        accept = result.acceptance
        rows.append(
            [
                s.policy,
                f"{s.n_correct}/{s.n_questions}",
                f"{s.total_cost_usd:.4f}",
                f"{s.cost_per_question_usd:.5f}",
                f"{s.latency_median_s:.1f} / {s.latency_mean_s:.1f} / {s.latency_p90_s:.1f}",
                _shares(s),
                f"{accept.precision:.3f} ({accept.n_accepted_correct}/{accept.n_accepted})"
                if accept
                else "-",
                f"{accept.recall:.3f} ({accept.n_accepted_correct}/{accept.n_first_tier_correct})"
                if accept
                else "-",
            ]
        )
    return rows


def _comparison_rows(results: Sequence[PolicyResult], versus: str) -> list[list[str]]:
    rows = []
    for result in results:
        comparison: Comparison | None = (
            result.vs_always_n if versus == "always_n" else result.vs_random
        )
        if comparison is None:
            continue
        rows.append(
            [
                result.summary.policy,
                _interval(comparison.accuracy, "+.3f"),
                _interval(comparison.cost_usd, "+.5f"),
                _interval(comparison.latency_s, "+.1f"),
            ]
        )
    return rows


def _reference_rows(results: Sequence[PolicyResult]) -> list[list[str]]:
    rows = []
    for result in results:
        if result.oracle is None or result.random is None:
            continue
        r = result.random
        rows.append(
            [
                result.summary.policy,
                f"{result.summary.n_correct}",
                f"{result.oracle.n_correct} (${result.oracle.total_cost_usd:.4f})",
                f"{r.correct_mean:.1f} [{r.correct_low:.0f}, {r.correct_high:.0f}] "
                f"(${r.cost_total_mean_usd:.4f}, {r.n_escalated} escalated)",
            ]
        )
    return rows


def _breakdown_lines(corpus: CorpusReport, dimension: str) -> list[str]:
    groups = corpus.breakdowns[dimension]
    policies = [r.summary.policy for r in corpus.policies]
    rows = [[group, *[_cell(cells.get(p)) for p in policies]] for group, cells in groups.items()]
    return [f"#### By {dimension}", "", *_table(["group", *policies], rows)]


def _cell(cell: Cell | None) -> str:
    return f"{cell.correct}/{cell.total}" if cell else "-"


def _corpus_lines(corpus: CorpusReport) -> list[str]:
    lines = [f"## Corpus {corpus.corpus_id} ({corpus.n_questions} questions)", ""]
    lines += ["### Policies", ""]
    header = [
        "policy",
        "correct",
        "total $",
        "$/question",
        "latency s median / mean / p90",
        "answered by",
        "tier-1 accept precision",
        "tier-1 accept recall",
    ]
    lines += _table(header, _policy_rows(corpus))
    lines += ["### Paired bootstrap vs always_n (policy minus always_n, mean [95% CI])", ""]
    header = ["policy", "accuracy", "$/question", "latency s/question"]
    lines += _table(header, _comparison_rows(corpus.policies, "always_n"))
    lines += ["### References (never deployable)", ""]
    header = ["policy", "correct", "oracle cascade", "random escalation, same share"]
    lines += _table(header, _reference_rows(corpus.policies))
    skipped = [p for p in corpus.policies if p.references_skipped]
    lines += [f"- {p.summary.policy}: no references - {p.references_skipped}" for p in skipped]
    lines += ["", "### Paired bootstrap vs random escalation", ""]
    header = ["policy", "accuracy", "$/question", "latency s/question"]
    lines += _table(header, _comparison_rows(corpus.policies, "random"))
    if corpus.not_evaluated:
        lines += ["### Not evaluated", ""]
        lines += [
            f"- **{p.policy}**: {_first_line(p.reason)}; gaps {p.gaps}"
            for p in corpus.not_evaluated
        ]
        lines.append("")
    lines += ["### Breakdowns (correct / questions)", ""]
    for dimension in corpus.breakdowns:
        lines += _breakdown_lines(corpus, dimension)
    return lines


def _first_line(text: str) -> str:
    return text.splitlines()[0]


def _verdict_lines(verdicts: Sequence[Verdict]) -> list[str]:
    lines = ["## Pre-registered rules S1-S3", ""]
    for verdict in verdicts:
        lines.append(f"- **{verdict.rule}: {verdict.status}** - {verdict.headline}")
        lines += [f"  - {detail}" for detail in verdict.details]
    return [*lines, ""]


def _tier3_lines(tallies: Sequence[Tier3Tally]) -> list[str]:
    if not tallies:
        return []
    rows = [
        [
            t.tier,
            f"{t.n_correct}/{t.n_runaways}",
            f"{t.n_rows}",
            f"{t.total_cost_usd:.4f}",
            f"{t.mean_latency_s:.1f}",
        ]
        for t in tallies
    ]
    header = [
        "tier-3 candidate",
        "correct on dev runaways",
        "rows stored",
        "cost $",
        "mean latency s",
    ]
    return ["## Tier-3 candidates on the dev runaways (S1)", "", *_table(header, rows)]


def render_markdown(report: Report) -> str:
    """The whole report as one Markdown document."""
    lines = ["# Method-and-effort cascade report", ""]
    lines += _verdict_lines(report.verdicts)
    lines += _tier3_lines(report.tier3)
    for corpus in report.corpora:
        lines += _corpus_lines(corpus)
    return "\n".join(lines).rstrip() + "\n"


def write_report(report: Report, out_dir: Path) -> tuple[Path, Path]:
    """Write `report.md` and `report.json` into `out_dir`; returns both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown = out_dir / "report.md"
    markdown.write_text(render_markdown(report), encoding="utf-8")
    json_path = out_dir / "report.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return markdown, json_path
