"""The data of a replay-agreement run: offline result, live result and whether they match.

The *offline walk* is how the experiment scored the system: it joins the stored rows of every
tier and lets the cascade policy pick the final tier from them, without calling any model. The
*live cascade* is what the demo runs. If the demo is faithful, the two agree on every question
whose model calls are all in the stored cache.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.cascade.models import Decision
from plantgraph.qa.cascade.policy import decide_all
from plantgraph.qa.models import FinalAnswer, Outcome
from plantgraph.qa.need.labels import NeedLabel


class OfflineResult(BaseModel):
    """What the frozen offline walk gives one question, in the live answer's own terms."""

    model_config = ConfigDict(frozen=True)

    need_label: NeedLabel | None
    answered_by: str | None
    outcome: Outcome
    final_answer: FinalAnswer | None


class Agreement(str, Enum):
    """How one replayed question ended."""

    AGREE = "agree"
    DISAGREE = "disagree"
    #: A model call was not in the cache; nothing was sent, so there is nothing to compare.
    MISS = "miss"


class ReplayRow(BaseModel):
    """One question: the offline result, the live one (if any) and the verdict."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    #: True when the question starts at a later tier than the first.
    routed: bool
    agreement: Agreement
    #: Fields that differ (`need_label`, `answered_by`, `outcome`, `final_answer`); empty unless
    #: the verdict is `disagree`.
    differs: tuple[str, ...]
    #: The tier whose call missed the cache; set only on a miss.
    missing_tier: str | None
    #: False when the live cascade ran a derived policy (the database tier was unavailable).
    live_policy_evaluated: bool | None
    offline: OfflineResult
    live: OfflineResult | None


def offline_results(
    joined: JoinedCorpus, question_ids: list[str], cutoff_s: float
) -> dict[str, OfflineResult]:
    """The frozen walk (`decide_all`) for `question_ids`, one result per question.

    Raises:
        ValueError: a question reaches a tier with no stored row (the join is incomplete).
    """
    decisions = decide_all(joined.policy, question_ids, joined.need_labels, joined.signals)
    return {d.question_id: _offline_result(joined, d, cutoff_s) for d in decisions}


def _offline_result(joined: JoinedCorpus, decision: Decision, cutoff_s: float) -> OfflineResult:
    label = joined.need_labels.get(decision.question_id)
    # mirror the live cascade: an answer later than the cutoff counts as TIMED_OUT, unanswered
    if decision.latency_s > cutoff_s:
        return OfflineResult(
            need_label=label, answered_by=None, outcome=Outcome.TIMED_OUT, final_answer=None
        )
    # with no answering tier, the last tried tier's outcome says why the question failed
    tier = decision.answered_by or decision.tiers_tried[-1]
    row = joined.runs[tier].rows[decision.question_id]
    return OfflineResult(
        need_label=label,
        answered_by=decision.answered_by,
        outcome=row.outcome,
        final_answer=row.final_answer if decision.answered_by else None,
    )


def live_result(answer: LiveAnswer, need_label: NeedLabel) -> OfflineResult:
    """The same four facts, read off a live answer."""
    return OfflineResult(
        need_label=need_label,
        answered_by=answer.answered_by,
        outcome=answer.outcome,
        final_answer=answer.final_answer,
    )


def compare(
    question_id: str,
    routed: bool,
    offline: OfflineResult,
    live: LiveAnswer | NeedsPaidCall,
    live_label: NeedLabel,
) -> ReplayRow:
    """The verdict for one question; a cache miss is a verdict of its own, never a mismatch."""
    if isinstance(live, NeedsPaidCall):
        return ReplayRow(
            question_id=question_id,
            routed=routed,
            agreement=Agreement.MISS,
            differs=(),
            missing_tier=live.missing_tier,
            live_policy_evaluated=None,
            offline=offline,
            live=None,
        )
    found = live_result(live, live_label)
    differs = tuple(
        name
        for name in ("need_label", "answered_by", "outcome", "final_answer")
        if getattr(offline, name) != getattr(found, name)
    )
    return ReplayRow(
        question_id=question_id,
        routed=routed,
        agreement=Agreement.DISAGREE if differs else Agreement.AGREE,
        differs=differs,
        missing_tier=None,
        live_policy_evaluated=live.evaluated_policy,
        offline=offline,
        live=found,
    )


class CorpusReplay(BaseModel):
    """The result of replaying one corpus."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    policy: str
    routed_only: bool
    cutoff_s: float
    #: The stored cache that was copied (never opened for writing), with its hash before and after.
    cache_source: str
    cache_sha256_before: str
    cache_sha256_after: str
    n_questions: int
    n_agree: int
    n_disagree: int
    n_miss: int
    #: Replayed rows whose live cascade ran a derived policy, not the evaluated one.
    n_derived_policy: int
    rows: tuple[ReplayRow, ...]


def summarise(rows: list[ReplayRow]) -> dict[str, int]:
    """The counts of a corpus report, from its rows."""
    return {
        "n_questions": len(rows),
        "n_agree": sum(r.agreement is Agreement.AGREE for r in rows),
        "n_disagree": sum(r.agreement is Agreement.DISAGREE for r in rows),
        "n_miss": sum(r.agreement is Agreement.MISS for r in rows),
        "n_derived_policy": sum(r.live_policy_evaluated is False for r in rows),
    }
