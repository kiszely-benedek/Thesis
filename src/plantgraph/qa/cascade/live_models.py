"""The types of the live cascade: a free-text question, one tier's report, the answer.

Nothing here knows gold: a question typed into the demo has no reference answer, and a
benchmark question reaches the live path as an `AskedQuestion` with its gold fields ignored.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome


class FreeTextQuestion(BaseModel):
    """A question typed by a user: text and answer shape, no reference answer."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    text: str
    answer_type: AnswerType = AnswerType.FREE_TEXT

    @classmethod
    def from_text(
        cls, text: str, answer_type: AnswerType = AnswerType.FREE_TEXT
    ) -> FreeTextQuestion:
        """Give the text a stable id (a hash of it), so asking twice is one question."""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
        return cls(question_id=f"ask-{digest}", text=text, answer_type=answer_type)


class TierReport(BaseModel):
    """What one tried tier did: its outcome, whether the policy accepted it, time and money."""

    model_config = ConfigDict(frozen=True)

    tier: str
    strategy: str
    model_id: str
    outcome: Outcome
    accepted: bool
    #: The cascade's latency of the tier: model calls plus local compute (`Signals.latency_s`).
    latency_s: float
    #: Wall-clock seconds this tier took in this process (a cached tier is quick).
    wall_s: float
    #: Cost the tier's calls cost when first made, cached or not (`Signals.cost_usd`).
    cost_usd: float
    #: Money this ask spent on the tier's calls that missed the cache.
    spent_usd: float
    n_calls: int
    n_cached: int
    #: Agent steps taken; `None` for a tier that is not an agent.
    n_steps: int | None
    #: Why the agent stopped; `None` for a tier that is not an agent.
    stop_reason: str | None
    #: Rows the Cypher query returned; `None` for a tier that ran no query.
    n_rows: int | None


class LiveAnswer(BaseModel):
    """The answer to one question, with how the cascade got there; unscored."""

    model_config = ConfigDict(frozen=True)

    question_text: str
    corpus_id: str
    answer_type: AnswerType
    #: The policy that ran; a derived `<policy>-no-<tier>` when a tier was unavailable.
    policy: str
    #: False for a derived policy: its numbers are not the evaluated policy's.
    evaluated_policy: bool
    #: Why a tier was left out (for example "the store holds D1000, not D100"); else `None`.
    notice: str | None
    outcome: Outcome
    final_answer: FinalAnswer | None
    #: The tier whose answer this is; `None` when the question failed or came too late.
    answered_by: str | None
    #: No tier was accepted, so the first tier's own answer was used.
    fell_back: bool
    tiers: tuple[TierReport, ...]
    #: Summed latency of the tried tiers, as the offline report counts it.
    latency_s: float
    #: Summed wall-clock seconds of the tried tiers in this process.
    wall_s: float
    cost_usd: float
    #: Money this ask actually spent (0 when everything came from the cache).
    spent_usd: float
    from_cache: bool
    #: Sheets the answering tier read, when its strategy records them (the graph agent does).
    trace_sheets: tuple[str, ...]


class NeedsPaidCall(BaseModel):
    """A replay-mode ask reached a model call the cache does not hold; nothing was sent."""

    model_config = ConfigDict(frozen=True)

    missing_tier: str
    reason: str
