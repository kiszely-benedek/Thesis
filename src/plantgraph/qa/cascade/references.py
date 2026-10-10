"""Reference arms a policy is compared with: always-one-tier, random escalation, oracle.

None of them is deployable. Always-one-tier is the plain baseline; random escalation sends
as many questions to the next tier as the policy does but picks them by chance, so it tests
whether the policy's self-flags beat luck; the oracle escalates exactly the questions the
first tier got wrong (it reads gold) and is the upper bound.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.evaluate import (
    DEFAULT_CUTOFF_S,
    Evaluation,
    Series,
    evaluate_decisions,
    score_decisions,
)
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.models import CascadePolicy, Decision, TierSpec
from plantgraph.qa.cascade.policy import decide, decide_all
from plantgraph.qa.cascade.stats import percentile

N_DRAWS = 1000
RANDOM_SEED = 1


def always_policy(tier: TierSpec) -> CascadePolicy:
    """Answer every question with this one tier's answer, whatever it is."""
    return CascadePolicy(name=f"always-{tier.name}", tiers=(tier,))


def evaluate_always(
    joined: JoinedCorpus, tier: TierSpec, cutoff_s: float = DEFAULT_CUTOFF_S
) -> Evaluation:
    """The accuracy, cost and latency of using only `tier`."""
    policy = always_policy(tier)
    decisions = decide_all(policy, joined.question_ids, joined.need_labels, joined.signals)
    return evaluate_decisions(replace(joined, policy=policy), decisions, cutoff_s)


def _require_label_free(policy: CascadePolicy, arm: str) -> None:
    if policy.start_tier_by_label or policy.last_tier_by_label or len(policy.tiers) < 2:
        raise ValueError(
            f"expected a label-free policy with at least two tiers for the {arm} reference, "
            f"found {policy.name!r}"
        )


def evaluate_oracle(joined: JoinedCorpus, cutoff_s: float = DEFAULT_CUTOFF_S) -> Evaluation:
    """Escalate exactly the questions whose first-tier answer is wrong (reads gold)."""
    policy = joined.policy
    _require_label_free(policy, "oracle")
    first_rows = joined.runs[policy.tiers[0].name].rows
    escalate = {qid: not first_rows[qid].correct for qid in joined.question_ids}
    named = policy.model_copy(update={"name": f"oracle({policy.name})"})
    decisions = decide_all(named, joined.question_ids, joined.need_labels, joined.signals, escalate)
    return evaluate_decisions(replace(joined, policy=named), decisions, cutoff_s)


class RandomReference(BaseModel):
    """Random escalation at the policy's own escalation count, over many seeded draws."""

    model_config = ConfigDict(frozen=True)

    n_draws: int
    n_escalated: int
    correct_mean: float
    #: 2.5th and 97.5th percentile of the correct count over the draws.
    correct_low: float
    correct_high: float
    #: The same three numbers counting only answers within the cutoff (acc@C).
    correct_at_cutoff_mean: float
    correct_at_cutoff_low: float
    correct_at_cutoff_high: float
    cost_total_mean_usd: float
    latency_mean_s: float
    #: Per-question expectations over the draws, as a paired-bootstrap series.
    expected_correct: list[float]
    expected_correct_at_cutoff: list[float]
    expected_cost_usd: list[float]
    expected_latency_s: list[float]

    def series(self) -> Series:
        """The per-question expectations, for `compare`."""
        return Series(
            self.expected_correct,
            self.expected_correct_at_cutoff,
            self.expected_cost_usd,
            self.expected_latency_s,
        )


def random_escalation(
    joined: JoinedCorpus,
    n_draws: int = N_DRAWS,
    seed: int = RANDOM_SEED,
    cutoff_s: float = DEFAULT_CUTOFF_S,
) -> RandomReference:
    """Escalate as many random questions as the policy escalated; keep the downstream rules."""
    policy = joined.policy
    _require_label_free(policy, "random")
    ids = joined.question_ids
    own = decide_all(policy, ids, joined.need_labels, joined.signals)
    n_escalated = sum(len(d.tiers_tried) > 1 for d in own)
    # Each question has exactly two possible outcomes under random choice; build both once.
    kept = _scored_alternatives(joined, escalate=False, cutoff_s=cutoff_s)
    sent = _scored_alternatives(joined, escalate=True, cutoff_s=cutoff_s)
    rng = random.Random(seed)
    draws = [rng.sample(range(len(ids)), n_escalated) for _ in range(n_draws)]
    return _summarise_draws(draws, kept, sent, n_escalated)


class _Alternative(NamedTuple):
    """What one question contributes if it is (not) escalated."""

    correct: float
    correct_at_cutoff: float
    cost_usd: float
    latency_s: float


def _scored_alternatives(
    joined: JoinedCorpus, escalate: bool, cutoff_s: float
) -> list[_Alternative]:
    decisions: list[Decision] = [
        decide(joined.policy, qid, joined.need_labels.get(qid), joined.signals, escalate)
        for qid in joined.question_ids
    ]
    return [
        _Alternative(
            float(s.correct), float(s.correct_at_cutoff), s.decision.cost_usd, s.decision.latency_s
        )
        for s in score_decisions(joined, decisions, cutoff_s)
    ]


def _summarise_draws(
    draws: list[list[int]],
    kept: list[_Alternative],
    sent: list[_Alternative],
    n_escalated: int,
) -> RandomReference:
    n = len(kept)
    # per-question running sums over the draws, field by field (correct, at cutoff, cost, latency)
    sums = [[0.0] * n for _ in range(4)]
    correct_counts: list[float] = []
    at_cutoff_counts: list[float] = []
    for chosen in draws:
        picked = set(chosen)
        rows = [sent[i] if i in picked else kept[i] for i in range(n)]
        correct_counts.append(sum(r.correct for r in rows))
        at_cutoff_counts.append(sum(r.correct_at_cutoff for r in rows))
        for i, row in enumerate(rows):
            for total, value in zip(sums, row, strict=True):
                total[i] += value
    k = len(draws)
    expected = [[x / k for x in total] for total in sums]
    return RandomReference(
        n_draws=k,
        n_escalated=n_escalated,
        correct_mean=sum(correct_counts) / k,
        correct_low=percentile(correct_counts, 2.5),
        correct_high=percentile(correct_counts, 97.5),
        correct_at_cutoff_mean=sum(at_cutoff_counts) / k,
        correct_at_cutoff_low=percentile(at_cutoff_counts, 2.5),
        correct_at_cutoff_high=percentile(at_cutoff_counts, 97.5),
        cost_total_mean_usd=sum(sums[2]) / k,
        latency_mean_s=sum(sums[3]) / k / n,
        expected_correct=expected[0],
        expected_correct_at_cutoff=expected[1],
        expected_cost_usd=expected[2],
        expected_latency_s=expected[3],
    )
