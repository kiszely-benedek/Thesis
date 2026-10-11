"""Scale tables (T3): how each policy changes from the small corpus to the large one.

The two corpora hold different questions, so every interval here is an unpaired bootstrap.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from statistics import fmean

from plantgraph.qa.cascade.report_claims import cost_elasticity
from plantgraph.qa.cascade.report_groups import K_BIN_ORDER, k_bin
from plantgraph.qa.cascade.report_references import acceptance_result
from plantgraph.qa.cascade.report_scopes import SCOPE_HEADLINE, restrict
from plantgraph.qa.cascade.report_sealed_models import KBinRow, ScaleRow
from plantgraph.qa.cascade.report_sealed_views import ScopeView, SealedCorpus
from plantgraph.qa.cascade.stats import median, percentile, unpaired_bootstrap, wilson_interval


def _large_minus_small(small: Sequence[float], large: Sequence[float]) -> float:
    return fmean(large) - fmean(small)


def _elasticity_of(
    sheets_small: int, sheets_large: int
) -> Callable[[Sequence[float], Sequence[float]], float]:
    """A statistic of two cost samples: the elasticity of their means."""

    def statistic(small: Sequence[float], large: Sequence[float]) -> float:
        return cost_elasticity(fmean(small), fmean(large), sheets_small, sheets_large)

    return statistic


def _scale_row(
    scope: str, policy: str, small: ScopeView, large: ScopeView, sizes: tuple[int, int]
) -> ScaleRow:
    series_small = small.evaluations[policy].series()
    series_large = large.evaluations[policy].series()
    summary_small = small.evaluations[policy].summary
    summary_large = large.evaluations[policy].summary
    return ScaleRow(
        scope=scope,
        policy=policy,
        small_corpus=small.corpus_id,
        large_corpus=large.corpus_id,
        sheets_small=sizes[0],
        sheets_large=sizes[1],
        accuracy_small=wilson_interval(
            summary_small.n_correct_at_cutoff, summary_small.n_questions
        ),
        accuracy_large=wilson_interval(
            summary_large.n_correct_at_cutoff, summary_large.n_questions
        ),
        accuracy_diff=unpaired_bootstrap(
            series_small.correct_at_cutoff, series_large.correct_at_cutoff, _large_minus_small
        ),
        cost_per_question_small_usd=summary_small.cost_per_question_usd,
        cost_per_question_large_usd=summary_large.cost_per_question_usd,
        elasticity=unpaired_bootstrap(
            series_small.cost_usd, series_large.cost_usd, _elasticity_of(*sizes)
        ),
        latency_median_ratio=median(series_large.latency_s) / median(series_small.latency_s),
        latency_p90_ratio=percentile(series_large.latency_s, 90)
        / percentile(series_small.latency_s, 90),
    )


def scale_rows(
    small_views: Mapping[str, ScopeView],
    large_views: Mapping[str, ScopeView],
    small: SealedCorpus,
    large: SealedCorpus,
) -> list[ScaleRow]:
    """A row per policy and scope that both corpora have, small corpus to large corpus."""
    sizes = (small.n_sheets, large.n_sheets)
    return [
        _scale_row(scope, policy, small_views[scope], large_views[scope], sizes)
        for scope in small_views
        if scope in large_views
        for policy in small_views[scope].evaluations
        if policy in large_views[scope].evaluations
    ]


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
