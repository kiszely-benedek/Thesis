"""Scale tables (T3): how each policy changes from the small corpus to the large one.

The two scales hold different questions, so every interval here is an unpaired bootstrap
(two-stage over plants, then questions, when a scale has several plants).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from plantgraph.qa.cascade.report_claims import cost_elasticity
from plantgraph.qa.cascade.report_groups import K_BIN_ORDER, k_bin
from plantgraph.qa.cascade.report_references import acceptance_result
from plantgraph.qa.cascade.report_scopes import SCOPE_HEADLINE, restrict
from plantgraph.qa.cascade.report_sealed_models import KBinRow, ScaleRow
from plantgraph.qa.cascade.report_sealed_views import (
    ScaleGroup,
    ScopeView,
    SealedCorpus,
    common_policies,
    group_scope_views,
)
from plantgraph.qa.cascade.stats import Interval, median, percentile, wilson_interval
from plantgraph.qa.cascade.stats_cluster import (
    cluster_mean_interval,
    cluster_unpaired_bootstrap,
    pooled_mean,
)


def _large_minus_small(small: float, large: float) -> float:
    return large - small


def _elasticity_of(sheets_small: int, sheets_large: int) -> Callable[[float, float], float]:
    """A statistic of two pooled mean costs: their elasticity."""

    def statistic(small: float, large: float) -> float:
        return cost_elasticity(small, large, sheets_small, sheets_large)

    return statistic


def _per_plant(views: Sequence[ScopeView], policy: str, field: str) -> list[list[float]]:
    """One series per plant: the policy's per-question `field` ("cost_usd", ...)."""
    return [list(getattr(v.evaluations[policy].series(), field)) for v in views]


def _accuracy(views: Sequence[ScopeView], policy: str) -> Interval:
    """Wilson for one plant (as registered); a two-stage bootstrap interval for several."""
    if len(views) == 1:
        summary = views[0].evaluations[policy].summary
        return wilson_interval(summary.n_correct_at_cutoff, summary.n_questions)
    return cluster_mean_interval(_per_plant(views, policy, "correct_at_cutoff"))


def _cost_per_question(views: Sequence[ScopeView], policy: str) -> float:
    """The summary's figure for one plant (as registered); the equal-weight plant mean otherwise."""
    if len(views) == 1:
        return views[0].evaluations[policy].summary.cost_per_question_usd
    return pooled_mean(_per_plant(views, policy, "cost_usd"))


def _pooled_latencies(views: Sequence[ScopeView], policy: str) -> list[float]:
    return [x for plant in _per_plant(views, policy, "latency_s") for x in plant]


def _scale_row(
    scope: str,
    policy: str,
    small: Sequence[ScopeView],
    large: Sequence[ScopeView],
    labels: tuple[str, str],
    sizes: tuple[int, int],
) -> ScaleRow:
    cost_small, cost_large = (
        _per_plant(small, policy, "cost_usd"),
        _per_plant(large, policy, "cost_usd"),
    )
    latency_small, latency_large = (
        _pooled_latencies(small, policy),
        _pooled_latencies(large, policy),
    )
    return ScaleRow(
        scope=scope,
        policy=policy,
        small_corpus=labels[0],
        large_corpus=labels[1],
        sheets_small=sizes[0],
        sheets_large=sizes[1],
        accuracy_small=_accuracy(small, policy),
        accuracy_large=_accuracy(large, policy),
        accuracy_diff=cluster_unpaired_bootstrap(
            _per_plant(small, policy, "correct_at_cutoff"),
            _per_plant(large, policy, "correct_at_cutoff"),
            _large_minus_small,
        ),
        cost_per_question_small_usd=_cost_per_question(small, policy),
        cost_per_question_large_usd=_cost_per_question(large, policy),
        elasticity=cluster_unpaired_bootstrap(cost_small, cost_large, _elasticity_of(*sizes)),
        n_plants_small=len(small),
        n_plants_large=len(large),
        latency_median_ratio=median(latency_large) / median(latency_small),
        latency_p90_ratio=percentile(latency_large, 90) / percentile(latency_small, 90),
    )


def scale_rows(
    small: ScaleGroup, large: ScaleGroup, views: Mapping[str, Mapping[str, ScopeView]]
) -> list[ScaleRow]:
    """A row per policy and scope that every plant of both scales has, small to large.

    Several plants per scale are pooled with the two-stage bootstrap; the two scales stay
    independent (no question exists at both).
    """
    small_scopes, large_scopes = group_scope_views(small, views), group_scope_views(large, views)
    labels, sizes = (small.label, large.label), (small.n_sheets, large.n_sheets)
    rows = []
    for scope in (name for name in small_scopes if name in large_scopes):  # small's order
        plants = [*small_scopes[scope], *large_scopes[scope]]
        rows += [
            _scale_row(scope, policy, small_scopes[scope], large_scopes[scope], labels, sizes)
            for policy in common_policies(plants)
        ]
    return rows


def _k_bin_row(corpus_id: str, policy: str, label: str, view: ScopeView, ids: set[str]) -> KBinRow:
    accepted = acceptance_result(restrict(view.joins[policy], ids))
    assert accepted is not None  # the caller only asks policies with a tier-1 acceptance rule
    return KBinRow(
        corpus_id=corpus_id,
        policy=policy,
        k_bin=label,
        n_questions=len(ids),
        n_accepted=accepted.n_accepted,
        n_accepted_correct=accepted.n_accepted_correct,
    )


def _policies_with_acceptance(view: ScopeView) -> list[str]:
    return [p for p, joined in view.joins.items() if acceptance_result(joined) is not None]


def k_bin_rows(
    corpora: Sequence[SealedCorpus],
    views: Mapping[str, Mapping[str, ScopeView]],
) -> list[KBinRow]:
    """Tier-1 acceptance share and precision per k-bin, on the headline questions."""
    rows: list[KBinRow] = []
    for corpus in corpora:
        view = views[corpus.corpus_id][SCOPE_HEADLINE]
        ids_by_bin = _ids_by_k_bin(corpus, view)
        for policy in _policies_with_acceptance(view):
            rows += [
                _k_bin_row(corpus.corpus_id, policy, label, view, ids_by_bin[label])
                for label in K_BIN_ORDER
                if label in ids_by_bin
            ]
    return rows


def _ids_by_k_bin(corpus: SealedCorpus, view: ScopeView) -> dict[str, set[str]]:
    """K-bin label -> headline question ids in it (bins with no question are absent)."""
    ids: dict[str, set[str]] = {}
    for question in corpus.questions:
        if question.question_id in view.ids:
            ids.setdefault(k_bin(question.k), set()).add(question.question_id)
    return ids
