"""Markdown for the sealed-claims part of the report (tables T1-T4 and the paired sections)."""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.qa.cascade.evaluate import LatencyBound
from plantgraph.qa.cascade.report_claims import SPLIT_ORDER
from plantgraph.qa.cascade.report_models import Cell, Verdict
from plantgraph.qa.cascade.report_sealed_models import (
    GapRow,
    KBinRow,
    PairedRow,
    ScaleRow,
    ScopeRow,
    SealedReport,
    SplitRow,
)
from plantgraph.qa.cascade.report_table import table
from plantgraph.qa.cascade.stats import Interval, interval_of


def _interval(value: Interval, fmt: str) -> str:
    return f"{value.estimate:{fmt}} [{value.ci_low:{fmt}}, {value.ci_high:{fmt}}]"


def _cell(cell: Cell) -> str:
    return f"{cell.correct}/{cell.total}"


def _shares(row: ScopeRow) -> str:
    ordered = sorted(row.summary.tier_shares.items(), key=lambda item: -item[1])
    return ", ".join(f"{tier} {share:.0%}" for tier, share in ordered)


def _acceptance(row: ScopeRow) -> tuple[str, str]:
    """Tier-1 acceptance share and precision, or dashes where the policy has no such rule."""
    accept = row.acceptance
    if accept is None:
        return "-", "-"
    share = accept.n_accepted / row.summary.n_questions
    return (
        f"{share:.1%}",
        f"{accept.precision:.3f} ({accept.n_accepted_correct}/{accept.n_accepted})",
    )


def _headline_row(row: ScopeRow) -> list[str]:
    s = row.summary
    verdicts = {v.rule: v.status for v in row.latency_verdicts}
    accept_share, accept_precision = _acceptance(row)
    return [
        row.policy,
        f"{s.n_questions}",
        f"{s.n_correct_at_cutoff}/{s.n_questions} {_interval(row.accuracy, '.3f')}",
        f"{row.n_all_correct_at_cutoff}/{row.n_all_questions}",
        f"{s.cost_per_question_usd:.5f}",
        " / ".join(
            f"{v:.1f}"
            for v in (
                s.latency_median_s,
                s.latency_mean_s,
                s.latency_p90_s,
                s.latency_p95_s,
                s.latency_max_s,
            )
        ),
        f"{verdicts['LB-1']} / {verdicts['LB-2']}",
        _shares(row),
        accept_share,
        accept_precision,
    ]


def _t1_lines(rows: Sequence[ScopeRow], bound: LatencyBound) -> list[str]:
    header = [
        "policy",
        "n",
        f"acc@{bound.cutoff_s:g} (95 % Wilson CI)",
        f"all-question acc@{bound.cutoff_s:g}",
        "$/question",
        "latency s median / mean / p90 / p95 / max",
        "LB-1 / LB-2",
        "answered by",
        "tier-1 accept share",
        "tier-1 accept precision",
    ]
    lines = ["## T1 Headline", ""]
    for corpus_id, scope in dict.fromkeys((r.corpus_id, r.scope) for r in rows):
        chosen = [r for r in rows if (r.corpus_id, r.scope) == (corpus_id, scope)]
        lines += [f"### {corpus_id}, scope `{scope}`", ""]
        lines += table(header, [_headline_row(r) for r in chosen])
        lines += _latency_ci_lines(chosen)
    return lines


def _latency_ci_lines(rows: Sequence[ScopeRow]) -> list[str]:
    body = [
        [r.policy, _interval(r.latency_median, ".1f"), _interval(r.latency_p90, ".1f")]
        for r in rows
    ]
    return ["Latency, 95 % bootstrap intervals (s):", "", *table(["policy", "median", "p90"], body)]


def _t2_lines(split_rows: Sequence[SplitRow], gap_rows: Sequence[GapRow]) -> list[str]:
    if not split_rows:
        return []
    lines = ["## T2 Splits", ""]
    for corpus_id in dict.fromkeys(r.corpus_id for r in split_rows):
        rows = [r for r in split_rows if r.corpus_id == corpus_id]
        splits = [s for s in SPLIT_ORDER if any(r.split == s for r in rows)]
        body = []
        for policy in dict.fromkeys(r.policy for r in rows):
            by_split = {r.split: r for r in rows if r.policy == policy}
            body.append([policy, *[_split_cell(by_split.get(s)) for s in splits]])
        lines += [f"### {corpus_id}", "", *table(["policy", *splits], body)]
    gaps = [
        [
            g.corpus_id,
            g.policy,
            _cell(g.dev),
            _cell(g.held_out),
            _interval(g.gap, "+.3f"),
        ]
        for g in gap_rows
    ]
    header = ["corpus", "policy", "dev", "held-out", "gap dev - held-out (unpaired 95 % CI)"]
    return [*lines, "### Generalisation gap", "", *table(header, gaps)]


def _split_cell(row: SplitRow | None) -> str:
    if row is None:
        return "-"
    return f"{_cell(row.cell)} {_interval(row.accuracy, '.3f')}"


def _scale_row(r: ScaleRow) -> list[str]:
    return [
        r.scope,
        r.policy,
        _interval(r.accuracy_small, ".3f"),
        _interval(r.accuracy_large, ".3f"),
        _interval(r.accuracy_diff, "+.3f"),
        f"{r.cost_per_question_small_usd:.5f} -> {r.cost_per_question_large_usd:.5f}",
        _interval(r.elasticity, ".3f"),
        f"{r.latency_median_ratio:.2f} / {r.latency_p90_ratio:.2f}",
    ]


def _k_bin_row(row: KBinRow) -> list[str]:
    share = row.n_accepted / row.n_questions
    # an unanswerable bin accepts nothing, so there is no precision to show
    precision = (
        f"{row.n_accepted_correct / row.n_accepted:.3f} ({row.n_accepted_correct}/{row.n_accepted})"
        if row.n_accepted
        else "-"
    )
    return [row.corpus_id, row.policy, row.k_bin, f"{row.n_questions}", f"{share:.1%}", precision]


def _t3_lines(report: SealedReport) -> list[str]:
    sheets = report.sheets
    big, small = report.claims_corpus, report.small_corpus
    header = [
        "scope",
        "policy",
        f"acc@C {small}",
        f"acc@C {big}",
        f"{big} - {small} (unpaired CI)",
        "$/question",
        "cost elasticity e (95 % CI)",
        "latency ratio median / p90",
    ]
    lines = [
        "## T3 Scale",
        "",
        f"{small} has {sheets[small]} sheets, {big} has {sheets[big]}; "
        "e = ln(cost ratio) / ln(sheet ratio).",
        "",
    ]
    lines += table(header, [_scale_row(r) for r in report.scale_rows])
    bins = ["corpus", "policy", "k bin", "n", "tier-1 accept share", "tier-1 accept precision"]
    return [
        *lines,
        "### Tier 1 by k bin (headline questions)",
        "",
        *table(bins, [_k_bin_row(r) for r in report.k_bin_rows]),
    ]


def _paired_lines(rows: Sequence[PairedRow]) -> list[str]:
    header = ["claim", "corpus", "scope", "policy - reference", "acc@C", "$/question", "latency s"]
    body = [
        [
            r.claim,
            r.corpus_id,
            r.scope,
            f"{r.policy} - {r.reference}",
            _interval(interval_of(r.comparison.accuracy_at_cutoff), "+.3f"),
            _interval(interval_of(r.comparison.cost_usd), "+.5f"),
            _interval(interval_of(r.comparison.latency_s), "+.2f"),
        ]
        for r in rows
    ]
    return [
        "## Paired bootstrap sections (K1, K2, Q5; mean difference [95 % CI])",
        "",
        *table(header, body),
    ]


def _claim_lines(claims: Sequence[Verdict], corpus_id: str) -> list[str]:
    lines = ["## T4 Claims", "", f"Claims corpus: {corpus_id}.", ""]
    for verdict in claims:
        lines.append(f"- **{verdict.status}** {verdict.headline}")
        lines += [f"  - {detail}" for detail in verdict.details]
    return [*lines, ""]


def sealed_lines(report: SealedReport, bound: LatencyBound) -> list[str]:
    """The sealed part of the report as Markdown lines."""
    lines = _claim_lines(report.claims, report.claims_corpus)
    lines += _t1_lines(report.scope_rows, bound)
    lines += _t2_lines(report.split_rows, report.gap_rows)
    lines += _t3_lines(report)
    lines += _paired_lines(report.paired_rows)
    lines += ["## Notes", "", *[f"- {note}" for note in report.notes], ""]
    return lines
