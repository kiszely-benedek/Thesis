"""The input and output types of answering one question without scoring it (`attempt.py`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plantgraph.llm.models import ContextWall, ModelPin
from plantgraph.qa.models import CallUsage, FinalAnswer, Outcome, QuestionResult, RunConfig


@dataclass(frozen=True)
class AttemptSettings:
    """The parts of a run's config that answering one question reads."""

    run_id: str
    answer_pin: ModelPin
    context_wall: ContextWall | None
    #: Whether the prompts carry the P&ID reading primer.
    primer: bool
    #: The call-time budget written into a `TIMED_OUT` row's trace; the meter enforces it.
    question_deadline_s: float | None

    @classmethod
    def from_config(cls, config: RunConfig) -> AttemptSettings:
        """The settings a harness run answers with."""
        return cls(
            config.run_id,
            config.answer_pin,
            config.context_wall,
            config.primer,
            config.question_deadline_s,
        )


@dataclass(frozen=True)
class UnscoredAnswer:
    """One finished answer before any gold is looked at: a row's fields minus its score."""

    strategy: str
    outcome: Outcome
    final_answer: FinalAnswer | None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    latency_s: float
    context_chars: int
    trace: dict[str, Any]
    retrieval_usage: CallUsage | None
    #: Wall time of retrieval and answering.
    wall_s: float
    #: Wall time minus the time inside model calls (what `timings.jsonl` stores).
    local_compute_s: float
    #: Cost of the calls that missed the cache, retrieval-side and final.
    spent_usd: float
    #: Whether the final call came from the cache; `None` when no final call was made.
    final_call_cached: bool | None

    def as_row(
        self,
        settings: AttemptSettings,
        question_id: str,
        repeat: int,
        correct: bool,
        f1: float | None,
    ) -> QuestionResult:
        """The row, with `correct` and `f1` from the scoring step (placeholders if unscored)."""
        return QuestionResult(
            run_id=settings.run_id,
            question_id=question_id,
            strategy=self.strategy,
            repeat=repeat,
            outcome=self.outcome,
            final_answer=self.final_answer,
            correct=correct,
            f1=f1,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cost_usd=self.cost_usd,
            latency_s=self.latency_s,
            context_chars=self.context_chars,
            trace=self.trace,
            retrieval_usage=self.retrieval_usage,
        )
