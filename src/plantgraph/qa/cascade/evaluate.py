"""Score a policy's decisions against gold, the one place in the cascade that reads `correct`.

A `Decision` names the tier whose answer is final; this module looks that answer's `correct`
up in the tier's stored row. The reference arms (always-one-tier, random escalation, oracle)
live in `references.py` and reuse these types.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.accept import is_accepted
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.models import CascadePolicy, Decision
from plantgraph.qa.cascade.policy import decide_all
from plantgraph.qa.cascade.stats import PairedDifference, median, paired_bootstrap, percentile

#: Key of `Summary.tier_shares` for questions that end without an answer.
NO_ANSWER = "none"


class ScoredDecision(BaseModel):
    """A decision plus whether its final answer was correct (a failed question is wrong)."""

    model_config = ConfigDict(frozen=True)

    decision: Decision
    correct: bool


@dataclass(frozen=True)
class Series:
    """Per-question numbers in question order: the input of a paired bootstrap."""

    correct: list[float]
    cost_usd: list[float]
    latency_s: list[float]


class Summary(BaseModel):
    """One policy on one corpus, in the numbers the report prints."""

    model_config = ConfigDict(frozen=True)

    policy: str
    corpus_id: str
    n_questions: int
    n_correct: int
    total_cost_usd: float
    cost_per_question_usd: float
    latency_median_s: float
    latency_mean_s: float
    latency_p90_s: float
    #: Share of questions whose final answer came from each tier (plus `NO_ANSWER`).
    tier_shares: dict[str, float]
    #: Questions that tried each tier, i.e. calls the policy would make.
    tier_calls: dict[str, int]


class Evaluation(BaseModel):
    """The scored decisions of one policy on one corpus, and their summary."""

    model_config = ConfigDict(frozen=True)

    summary: Summary
    scored: tuple[ScoredDecision, ...]

    def series(self) -> Series:
        """The per-question numbers, for comparison."""
        return Series(
            correct=[float(s.correct) for s in self.scored],
            cost_usd=[s.decision.cost_usd for s in self.scored],
            latency_s=[s.decision.latency_s for s in self.scored],
        )


class Comparison(BaseModel):
    """Policy minus reference, per question, with bootstrap intervals."""

    model_config = ConfigDict(frozen=True)

    accuracy: PairedDifference
    cost_usd: PairedDifference
    latency_s: PairedDifference


class Acceptance(BaseModel):
    """How good the first tier's self-signal is as a judge of its own answers."""

    model_config = ConfigDict(frozen=True)

    n_accepted: int
    n_accepted_correct: int
    #: Questions the first tier answered correctly, accepted or not.
    n_first_tier_correct: int

    @property
    def precision(self) -> float:
        """Share of accepted first-tier answers that are correct."""
        return self.n_accepted_correct / self.n_accepted if self.n_accepted else 0.0

    @property
    def recall(self) -> float:
        """Share of correct first-tier answers that were accepted (not escalated)."""
        total = self.n_first_tier_correct
        return self.n_accepted_correct / total if total else 0.0


def score_decisions(joined: JoinedCorpus, decisions: Sequence[Decision]) -> list[ScoredDecision]:
    """Attach `correct` from the final tier's stored row."""
    return [ScoredDecision(decision=d, correct=_final_answer_correct(joined, d)) for d in decisions]


def _final_answer_correct(joined: JoinedCorpus, decision: Decision) -> bool:
    if decision.answered_by is None:
        return False
    return joined.runs[decision.answered_by].rows[decision.question_id].correct


def evaluate_decisions(joined: JoinedCorpus, decisions: Sequence[Decision]) -> Evaluation:
    """Score and summarise a list of decisions (a policy's, or a reference arm's)."""
    scored = score_decisions(joined, decisions)
    return Evaluation(summary=_summarise(joined.corpus_id, scored), scored=tuple(scored))


def evaluate_policy(joined: JoinedCorpus) -> Evaluation:
    """Run the corpus' own policy over the joined signals and score it."""
    decisions = decide_all(joined.policy, joined.question_ids, joined.need_labels, joined.signals)
    return evaluate_decisions(joined, decisions)


def _summarise(corpus_id: str, scored: list[ScoredDecision]) -> Summary:
    decisions = [s.decision for s in scored]
    latencies = [d.latency_s for d in decisions]
    total_cost = sum(d.cost_usd for d in decisions)
    final = Counter(d.answered_by or NO_ANSWER for d in decisions)
    tried = Counter(tier for d in decisions for tier in d.tiers_tried)
    return Summary(
        policy=decisions[0].policy,
        corpus_id=corpus_id,
        n_questions=len(decisions),
        n_correct=sum(s.correct for s in scored),
        total_cost_usd=total_cost,
        cost_per_question_usd=total_cost / len(decisions),
        latency_median_s=median(latencies),
        latency_mean_s=sum(latencies) / len(latencies),
        latency_p90_s=percentile(latencies, 90),
        tier_shares={tier: n / len(decisions) for tier, n in final.items()},
        tier_calls=dict(tried),
    )


def first_tier_acceptance(joined: JoinedCorpus, policy: CascadePolicy) -> Acceptance:
    """Precision and recall of `policy`'s first-tier acceptance rule against gold."""
    first = policy.tiers[0]
    rows = joined.runs[first.name].rows
    accepted = [
        qid
        for qid in joined.question_ids
        if is_accepted(joined.signals[first.name][qid], first.accept)
    ]
    return Acceptance(
        n_accepted=len(accepted),
        n_accepted_correct=sum(rows[qid].correct for qid in accepted),
        n_first_tier_correct=sum(row.correct for row in rows.values()),
    )


def compare(policy: Series, reference: Series) -> Comparison:
    """Paired bootstrap of accuracy, cost per question and latency per question."""
    return Comparison(
        accuracy=paired_bootstrap(policy.correct, reference.correct),
        cost_usd=paired_bootstrap(policy.cost_usd, reference.cost_usd),
        latency_s=paired_bootstrap(policy.latency_s, reference.latency_s),
    )
