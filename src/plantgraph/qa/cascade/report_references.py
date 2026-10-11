"""Per-policy report fields beyond the summary: acceptance, oracle, random escalation."""

from __future__ import annotations

from plantgraph.qa.cascade.evaluate import Evaluation, compare, first_tier_acceptance
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.references import evaluate_oracle, random_escalation
from plantgraph.qa.cascade.report_models import AcceptanceResult, RandomSummary


def _has_references(policy: CascadePolicy) -> bool:
    """Oracle and random escalation are defined for label-free policies with 2+ tiers."""
    routed = policy.start_tier_by_label or policy.last_tier_by_label
    return len(policy.tiers) >= 2 and not routed


def acceptance_result(joined: JoinedCorpus) -> AcceptanceResult | None:
    """The first tier's acceptance precision and recall; `None` for a one-tier or routed policy."""
    policy = joined.policy
    if len(policy.tiers) < 2 or policy.start_tier_by_label:
        return None  # a single tier accepts everything; a router skips tier 1 for some labels
    raw = first_tier_acceptance(joined, policy)
    return AcceptanceResult(
        n_accepted=raw.n_accepted,
        n_accepted_correct=raw.n_accepted_correct,
        n_first_tier_correct=raw.n_first_tier_correct,
        precision=raw.precision,
        recall=raw.recall,
    )


def reference_fields(
    joined: JoinedCorpus, evaluation: Evaluation, cutoff_s: float
) -> dict[str, object]:
    """Oracle and random escalation, or the reason they cannot be computed on these rows."""
    if not _has_references(joined.policy):
        return {}
    try:
        reference = random_escalation(joined, cutoff_s=cutoff_s)
        oracle = evaluate_oracle(joined, cutoff_s)
    except ValueError as error:  # e.g. the second tier has rows only for the runaways
        return {"references_skipped": str(error)}
    return {
        "oracle": oracle.summary,
        "random": RandomSummary(
            n_draws=reference.n_draws,
            n_escalated=reference.n_escalated,
            correct_mean=reference.correct_mean,
            correct_low=reference.correct_low,
            correct_high=reference.correct_high,
            correct_at_cutoff_mean=reference.correct_at_cutoff_mean,
            correct_at_cutoff_low=reference.correct_at_cutoff_low,
            correct_at_cutoff_high=reference.correct_at_cutoff_high,
            cost_total_mean_usd=reference.cost_total_mean_usd,
            latency_mean_s=reference.latency_mean_s,
        ),
        "vs_random": compare(evaluation.series(), reference.series()),
    }
