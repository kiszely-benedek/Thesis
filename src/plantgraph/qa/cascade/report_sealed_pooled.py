"""Pooled T1 rows and the plant-robustness count for scales that have several plants.

Per-plant rows are built by the single-corpus code; this module adds, for a scale with more than
one plant, the equal-weight pooled row (design `review-fixes.md` section 5.2) and a descriptive
count of the plants that agree with the pooled sign.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from plantgraph.qa.cascade.evaluate import Evaluation, LatencyBound, pool_evaluations
from plantgraph.qa.cascade.report_sealed_models import (
    PairedRow,
    RobustnessRow,
    ScaleRow,
    ScopeRow,
)
from plantgraph.qa.cascade.report_sealed_views import (
    ScaleGroup,
    ScopeView,
    common_policies,
    group_scope_views,
)
from plantgraph.qa.cascade.report_verdicts import check_latency_bound
from plantgraph.qa.cascade.stats import bootstrap_interval, median, percentile
from plantgraph.qa.cascade.stats_cluster import cluster_mean_interval, same_sign_count

ViewsByCorpus = Mapping[str, Mapping[str, ScopeView]]


def _p90(values: Sequence[float]) -> float:
    return percentile(values, 90)


def _pooled_row(
    group: ScaleGroup, scope: str, policy: str, plants: Sequence[ScopeView], bound: LatencyBound
) -> ScopeRow:
    """One policy on all plants of a scale: pooled summary, two-stage accuracy interval."""
    pooled = pool_evaluations([v.evaluations[policy] for v in plants], group.label, bound.cutoff_s)
    every = pool_evaluations(
        [p.evaluations[policy] for p in group.plants], group.label, bound.cutoff_s
    )
    latencies = pooled.series().latency_s
    return ScopeRow(
        corpus_id=group.label,
        scope=scope,
        policy=policy,
        summary=pooled.summary,
        accuracy=cluster_mean_interval(
            [v.evaluations[policy].series().correct_at_cutoff for v in plants]
        ),
        n_all_questions=every.summary.n_questions,
        n_all_correct_at_cutoff=every.summary.n_correct_at_cutoff,
        latency_verdicts=check_latency_bound(pooled.summary, bound),
        acceptance=None,  # acceptance counts are per plant; the pooled row leaves them out
        # The latency intervals resample the pooled questions only (not plants first): descriptive.
        latency_median=bootstrap_interval(latencies, median),
        latency_p90=bootstrap_interval(latencies, _p90),
    )


def pooled_scope_rows(
    groups: Sequence[ScaleGroup], views: ViewsByCorpus, bound: LatencyBound
) -> list[ScopeRow]:
    """T1 rows for the scales with several plants: a row per scope and policy every plant has."""
    rows = []
    for group in (g for g in groups if g.is_pooled):
        for scope, plants in group_scope_views(group, views).items():
            rows += [
                _pooled_row(group, scope, policy, plants, bound)
                for policy in common_policies(plants)
            ]
    return rows


def _pair_key(row: PairedRow) -> tuple[str, str, str, str]:
    return row.claim, row.scope, row.policy, row.reference


def paired_robustness(
    groups: Sequence[ScaleGroup], pairs: Sequence[PairedRow]
) -> list[RobustnessRow]:
    """K1, K2 and Q5: plants whose own acc@C difference has the pooled difference's sign."""
    rows = []
    for group in (g for g in groups if g.is_pooled):
        plant_ids = {p.corpus_id for p in group.plants}
        for pooled in (r for r in pairs if r.corpus_id == group.label):
            own = [
                r.comparison.accuracy_at_cutoff.mean
                for r in pairs
                if r.corpus_id in plant_ids and _pair_key(r) == _pair_key(pooled)
            ]
            rows.append(
                RobustnessRow(
                    claim=pooled.claim,
                    scope=pooled.scope,
                    policy=pooled.policy,
                    n_plants=len(own),
                    n_same_sign=same_sign_count(own, pooled.comparison.accuracy_at_cutoff.mean),
                )
            )
    return rows


def _accuracy_of(evaluation: Evaluation) -> float:
    summary = evaluation.summary
    return summary.n_correct_at_cutoff / summary.n_questions


def scale_robustness(
    large: ScaleGroup, views: ViewsByCorpus, scales: Sequence[ScaleRow]
) -> list[RobustnessRow]:
    """Q4: large plants whose acc@C minus the pooled small-scale acc@C has the pooled sign.

    The two scales share no question, so a large plant is compared with the small scale's
    pooled accuracy, not with a partner plant.
    """
    if not large.is_pooled:
        return []
    rows = []
    for row in scales:
        small_accuracy = row.accuracy_small.estimate
        own = [
            _accuracy_of(views[p.corpus_id][row.scope].evaluations[row.policy]) - small_accuracy
            for p in large.plants
        ]
        rows.append(
            RobustnessRow(
                claim="Q4",
                scope=row.scope,
                policy=row.policy,
                n_plants=len(own),
                n_same_sign=same_sign_count(own, row.accuracy_diff.estimate),
            )
        )
    return rows
