"""Build the sealed-claims part of the report: T1 headline, T2 splits, and the assembly of T3/T4.

Every number comes from the policies' offline joins narrowed to a scope (`report_sealed_views`).
The scale tables are in `report_sealed_scale.py`, the paired sections and claims in
`report_sealed_pairs.py`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import fmean

from plantgraph.qa.cascade.evaluate import LatencyBound
from plantgraph.qa.cascade.report_claims import (
    DEV_SPLITS,
    F1_CLAIMS,
    SPLIT_HELD_OUT,
    SPLIT_ORDER,
    ClaimPolicies,
)
from plantgraph.qa.cascade.report_models import Cell
from plantgraph.qa.cascade.report_references import acceptance_result
from plantgraph.qa.cascade.report_scopes import SCOPE_HEADLINE, counted_ids, split_ids
from plantgraph.qa.cascade.report_sealed_models import GapRow, ScopeRow, SealedReport, SplitRow
from plantgraph.qa.cascade.report_sealed_pairs import claims_for, paired_rows
from plantgraph.qa.cascade.report_sealed_pooled import (
    paired_robustness,
    pooled_scope_rows,
    scale_robustness,
)
from plantgraph.qa.cascade.report_sealed_scale import k_bin_rows, scale_rows
from plantgraph.qa.cascade.report_sealed_views import (
    ScaleGroup,
    ScopeView,
    SealedCorpus,
    group_scales,
    make_view,
    scope_views,
)
from plantgraph.qa.cascade.report_verdicts import check_latency_bound
from plantgraph.qa.cascade.stats import (
    bootstrap_interval,
    median,
    percentile,
    unpaired_bootstrap,
    wilson_interval,
)


def _p90(values: Sequence[float]) -> float:
    return percentile(values, 90)


def _mean_difference(a: Sequence[float], b: Sequence[float]) -> float:
    return fmean(a) - fmean(b)


def _scope_rows(view: ScopeView, corpus: SealedCorpus, bound: LatencyBound) -> list[ScopeRow]:
    """T1 rows of one view: a row per policy, with the all-question count beside it."""
    rows = []
    for name, evaluation in view.evaluations.items():
        summary = evaluation.summary
        latencies = evaluation.series().latency_s
        every = corpus.evaluations[name].summary
        rows.append(
            ScopeRow(
                corpus_id=view.corpus_id,
                scope=view.scope,
                policy=name,
                summary=summary,
                accuracy=wilson_interval(summary.n_correct_at_cutoff, summary.n_questions),
                n_all_questions=every.n_questions,
                n_all_correct_at_cutoff=every.n_correct_at_cutoff,
                latency_verdicts=check_latency_bound(summary, bound),
                acceptance=acceptance_result(view.joins[name]),
                latency_median=bootstrap_interval(latencies, median),
                latency_p90=bootstrap_interval(latencies, _p90),
            )
        )
    return rows


def _cell_of(view: ScopeView, policy: str) -> Cell:
    summary = view.evaluations[policy].summary
    return Cell(correct=summary.n_correct_at_cutoff, total=summary.n_questions)


def _split_views(corpus: SealedCorpus, cutoff_s: float) -> dict[str, ScopeView]:
    """Split name -> view over that split's counted questions (empty splits are left out)."""
    assert corpus.splits is not None  # callers check
    counted = counted_ids(corpus.questions)
    views = {}
    for split in SPLIT_ORDER:
        ids = counted & split_ids(corpus.splits, (split,))
        if ids:
            views[split] = make_view(corpus, split, ids, cutoff_s)
    return views


def _gap_row(corpus_id: str, policy: str, dev: ScopeView, held_out: ScopeView) -> GapRow:
    """Dev minus held-out accuracy of one policy, with an unpaired bootstrap interval."""
    dev_correct = dev.evaluations[policy].series().correct_at_cutoff
    held_correct = held_out.evaluations[policy].series().correct_at_cutoff
    return GapRow(
        corpus_id=corpus_id,
        policy=policy,
        dev=_cell_of(dev, policy),
        held_out=_cell_of(held_out, policy),
        gap=unpaired_bootstrap(dev_correct, held_correct, _mean_difference),
    )


def _split_tables(corpus: SealedCorpus, cutoff_s: float) -> tuple[list[SplitRow], list[GapRow]]:
    """T2 for one corpus: a row per policy and split, and the generalisation gap per policy."""
    views = _split_views(corpus, cutoff_s)
    rows = [
        SplitRow(
            corpus_id=corpus.corpus_id,
            policy=policy,
            split=split,
            cell=_cell_of(view, policy),
            accuracy=wilson_interval(_cell_of(view, policy).correct, _cell_of(view, policy).total),
        )
        for split, view in views.items()
        for policy in view.evaluations
    ]
    dev_ids = counted_ids(corpus.questions) & split_ids(corpus.splits or {}, DEV_SPLITS)
    held_view = views.get(SPLIT_HELD_OUT)
    if not dev_ids or held_view is None:
        return rows, []
    dev_view = make_view(corpus, "dev", dev_ids, cutoff_s)
    gaps = [_gap_row(corpus.corpus_id, p, dev_view, held_view) for p in dev_view.evaluations]
    return rows, gaps


def build_sealed(
    corpora: Sequence[SealedCorpus],
    bound: LatencyBound,
    claims: ClaimPolicies = F1_CLAIMS,
    scales: Mapping[str, Sequence[str]] | None = None,
) -> SealedReport:
    """Tables T1-T4 for the corpora given; the last scale holds the claims, the first the small end.

    `claims` names the policies the claims are about (default: F1's). `scales` maps a scale label
    to the corpus ids of its plants (design `review-fixes.md` section 5.2): the plants are shown
    one by one, then pooled with the two-stage bootstrap. A corpus named in no scale is a scale
    of its own, which is the registered single-plant computation.

    Raises:
        ValueError: fewer than two scales (the scale tables need a small and a large one).
    """
    groups = group_scales(corpora, scales)
    if len(groups) < 2:
        raise ValueError(f"expected at least two scales for the scale tables, found {len(groups)}")
    views = {c.corpus_id: scope_views(c, bound.cutoff_s) for c in corpora}
    scope_rows = [
        row
        for c in corpora
        for view in views[c.corpus_id].values()
        for row in _scope_rows(view, c, bound)
    ]
    scope_rows += pooled_scope_rows(groups, views, bound)
    split_rows: list[SplitRow] = []
    gap_rows: list[GapRow] = []
    for corpus in (c for c in corpora if c.splits is not None):
        splits, gaps = _split_tables(corpus, bound.cutoff_s)
        split_rows += splits
        gap_rows += gaps
    small, large = groups[0], groups[-1]
    scale_table = scale_rows(small, large, views)
    pairs = paired_rows(groups, views, bound.cutoff_s, claims)
    verdicts = claims_for(large.label, scope_rows, scale_table, pairs, bound, claims)
    return SealedReport(
        claims_corpus=large.label,
        small_corpus=small.label,
        sheets={g.label: g.n_sheets for g in groups},
        scope_sizes={g.label: _scope_sizes(g, views) for g in groups},
        scope_rows=scope_rows,
        split_rows=split_rows,
        gap_rows=gap_rows,
        scale_rows=scale_table,
        k_bin_rows=k_bin_rows(corpora, views),
        paired_rows=pairs,
        claims=verdicts,
        scales={g.label: [p.corpus_id for p in g.plants] for g in groups if g.is_pooled},
        robustness=paired_robustness(groups, pairs) + scale_robustness(large, views, scale_table),
        notes=_notes(corpora, groups),
    )


def _scope_sizes(group: ScaleGroup, views: Mapping[str, Mapping[str, ScopeView]]) -> dict[str, int]:
    """Scope -> number of questions a scale counts, summed over its plants."""
    sizes: dict[str, int] = {}
    for plant in group.plants:
        for scope, view in views[plant.corpus_id].items():
            sizes[scope] = sizes.get(scope, 0) + view.n_questions
    return sizes


def _pooling_notes(groups: Sequence[ScaleGroup]) -> list[str]:
    pooled = [g for g in groups if g.is_pooled]
    if not pooled:
        return []
    labels = ", ".join(f"{g.label} ({len(g.plants)} plants)" for g in pooled)
    return [
        f"pooled scales: {labels}; the pooled value is the equal-weight mean of the plants, "
        "intervals are two-stage cluster bootstraps (plants, then questions) with the EXP-0007 "
        "seed and resample count",
        "with few plants the bootstrap understates between-plant variance (about 4/5 at five "
        "plants); pooled latency intervals resample questions only",
        "the plant-robustness table counts plants whose own acc@C difference has the pooled "
        "sign; it is descriptive and judges nothing",
    ]


def _notes(corpora: Sequence[SealedCorpus], groups: Sequence[ScaleGroup]) -> list[str]:
    """What the tables could not show, said once instead of leaving a silent gap."""
    return (
        _pooling_notes(groups)
        + [
            f"{c.corpus_id}: no splits.json beside the questions, so there is no split table "
            "and no held-out scope"
            for c in corpora
            if c.splits is None
        ]
        + [f"scope `{SCOPE_HEADLINE}` leaves out the family LOOP_ACTUATED_VALVE (ADR-0044 U2)"]
    )
