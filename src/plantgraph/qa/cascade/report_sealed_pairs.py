"""Paired comparisons (K1, K2, Q5) and the assembly of the claims table (T4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from plantgraph.qa.cascade.evaluate import Comparison, LatencyBound, Series
from plantgraph.qa.cascade.report_claims import (
    F1_CLAIMS,
    ClaimPolicies,
    judge_k1,
    judge_k2,
    judge_k3,
    judge_q5,
    judge_scale_claim,
    not_run_verdicts,
)
from plantgraph.qa.cascade.report_models import Verdict
from plantgraph.qa.cascade.report_references import random_reference_series
from plantgraph.qa.cascade.report_sealed_models import PairedRow, ScaleRow, ScopeRow
from plantgraph.qa.cascade.report_sealed_views import (
    ScaleGroup,
    ScopeView,
    group_scope_views,
)
from plantgraph.qa.cascade.stats import PairedDifference, interval_of
from plantgraph.qa.cascade.stats_cluster import cluster_paired_bootstrap

RANDOM_ESCALATION = "random escalation"


def compare_plants(policy: Sequence[Series], reference: Sequence[Series]) -> Comparison:
    """`compare` over several plants: one shared two-stage draw (plants, then questions) per metric.

    With one plant this is exactly `compare`, the registered single-plant computation.
    """

    def pooled(field: str) -> PairedDifference:
        return cluster_paired_bootstrap(
            [getattr(s, field) for s in policy], [getattr(s, field) for s in reference]
        )

    return Comparison(
        accuracy=pooled("correct"),
        accuracy_at_cutoff=pooled("correct_at_cutoff"),
        cost_usd=pooled("cost_usd"),
        latency_s=pooled("latency_s"),
    )


def _paired(
    claim: str, label: str, scope: str, policy: str, reference: str, versus: Comparison
) -> PairedRow:
    return PairedRow(
        claim=claim,
        corpus_id=label,
        scope=scope,
        policy=policy,
        reference=reference,
        comparison=versus,
    )


def _policy_pair(
    claim: str, label: str, plants: Sequence[ScopeView], policy: str, reference: str
) -> list[PairedRow]:
    """`policy` minus `reference` over the plants; nothing when a plant did not evaluate either."""
    if any(policy not in v.evaluations or reference not in v.evaluations for v in plants):
        return []
    versus = compare_plants(
        [v.evaluations[policy].series() for v in plants],
        [v.evaluations[reference].series() for v in plants],
    )
    return [_paired(claim, label, plants[0].scope, policy, reference, versus)]


def _random_pair(
    label: str, plants: Sequence[ScopeView], cutoff_s: float, policy: str
) -> list[PairedRow]:
    """`policy` minus random escalation at its own tier-2 share (K2)."""
    if any(policy not in v.evaluations for v in plants):
        return []
    references = [random_reference_series(v.joins[policy], cutoff_s) for v in plants]
    if any(reference is None for reference in references):
        return []
    versus = compare_plants(
        [v.evaluations[policy].series() for v in plants],
        [reference for reference in references if reference is not None],
    )
    return [_paired("K2", label, plants[0].scope, policy, RANDOM_ESCALATION, versus)]


def _claim_pairs(
    label: str, plants: Sequence[ScopeView], cutoff_s: float, claims: ClaimPolicies
) -> list[PairedRow]:
    return [
        *_policy_pair("K1", label, plants, claims.primary, claims.tier2_comparator),
        *_random_pair(label, plants, cutoff_s, claims.random_reference),
        *_policy_pair("Q5", label, plants, claims.tier2_comparator, claims.cypher_comparator),
    ]


def paired_rows(
    groups: Sequence[ScaleGroup],
    views: Mapping[str, Mapping[str, ScopeView]],
    cutoff_s: float,
    claims: ClaimPolicies = F1_CLAIMS,
) -> list[PairedRow]:
    """K1, K2 and Q5 for every scale and scope that can form them.

    A scale with several plants shows each plant's own row first (its corpus id), then the pooled
    row (the scale's label) whose interval comes from the two-stage bootstrap. Every pair is
    evaluated on the same plant and question draw (same seed, same sizes).
    """
    rows: list[PairedRow] = []
    for group in groups:
        for plants in group_scope_views(group, views).values():
            if group.is_pooled:
                for plant in plants:
                    rows += _claim_pairs(plant.corpus_id, [plant], cutoff_s, claims)
            rows += _claim_pairs(group.label, plants, cutoff_s, claims)
    return rows


def _incomplete(rule: str, scope: str, missing: str) -> Verdict:
    return Verdict(
        rule=rule, status="INCOMPLETE", headline=f"{rule} [{scope}]: {missing} is not available"
    )


def _find_pair(
    rows: Sequence[PairedRow], claim: str, corpus_id: str, scope: str
) -> PairedRow | None:
    for row in rows:
        if (row.claim, row.corpus_id, row.scope) == (claim, corpus_id, scope):
            return row
    return None


def _k1_verdict(scope: str, pair: PairedRow | None) -> Verdict:
    if pair is None:
        return _incomplete("K1", scope, "the cascade-vs-always-agent comparison")
    versus = pair.comparison
    return judge_k1(
        scope,
        interval_of(versus.accuracy_at_cutoff),
        interval_of(versus.cost_usd),
        interval_of(versus.latency_s),
    )


def _k2_verdict(scope: str, pair: PairedRow | None) -> Verdict:
    return judge_k2(
        scope, None if pair is None else interval_of(pair.comparison.accuracy_at_cutoff)
    )


def _k3_verdict(scope: str, row: ScopeRow | None, bound: LatencyBound, primary: str) -> Verdict:
    if row is None:
        return _incomplete("K3", scope, f"{primary} on the claims corpus")
    return judge_k3(scope, bound, row.latency_median, row.latency_p90)


def _q5_verdict(scope: str, pair: PairedRow | None) -> Verdict:
    if pair is None:
        return _incomplete("Q5", scope, "the typed-API-vs-Cypher comparison")
    return judge_q5(scope, interval_of(pair.comparison.accuracy_at_cutoff))


def _scale_verdicts(scope: str, scales: Sequence[ScaleRow], primary: str) -> list[Verdict]:
    """Q4 for the primary policy first, then Q4' for every other policy."""
    rows = [r for r in scales if r.scope == scope]
    rows.sort(key=lambda r: r.policy != primary)  # stable: the primary moves to the front
    verdicts = [
        judge_scale_claim(r.policy, scope, r.accuracy_diff, r.elasticity, primary) for r in rows
    ]
    if not any(r.policy == primary for r in rows):
        verdicts.insert(0, _incomplete("Q4 (primary)", scope, f"{primary} on both corpora"))
    return verdicts


def claims_for(
    claims_corpus: str,
    scope_rows: Sequence[ScopeRow],
    scales: Sequence[ScaleRow],
    pairs: Sequence[PairedRow],
    bound: LatencyBound,
    claims: ClaimPolicies = F1_CLAIMS,
) -> list[Verdict]:
    """T4: every claim on each scope the claims corpus has, then Q1-Q3 as not run."""
    scopes = list(dict.fromkeys(r.scope for r in scope_rows if r.corpus_id == claims_corpus))
    verdicts: list[Verdict] = []
    for scope in scopes:
        primary_row = next(
            (
                r
                for r in scope_rows
                if (r.corpus_id, r.scope, r.policy) == (claims_corpus, scope, claims.primary)
            ),
            None,
        )
        scale = _scale_verdicts(scope, scales, claims.primary)
        verdicts += [
            scale[0],
            _k1_verdict(scope, _find_pair(pairs, "K1", claims_corpus, scope)),
            _k2_verdict(scope, _find_pair(pairs, "K2", claims_corpus, scope)),
            _k3_verdict(scope, primary_row, bound, claims.primary),
            _q5_verdict(scope, _find_pair(pairs, "Q5", claims_corpus, scope)),
            *scale[1:],
        ]
    return verdicts + not_run_verdicts()
