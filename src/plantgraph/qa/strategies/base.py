"""The `Strategy` protocol and the one runner every strategy goes through (`qa-system.md` §7).

The fairness rule "retrieval sees only `question.text`" is enforced by the
type: `Strategy.retrieve` takes a plain string, so a strategy cannot read
`family`, `answer_type`, `k` or an evidence field even by accident.
"""

from __future__ import annotations

from typing import Protocol

from plantgraph.llm.models import ContextWall, ModelPin
from plantgraph.qa.final_answer import FinalStepResult, SendChatRequest, run_final_step
from plantgraph.qa.models import Question, RetrievalResult


class Strategy(Protocol):
    """A retrieval strategy: question text in, context string out. No LLM answer step here."""

    #: The short name recorded in `QuestionResult.strategy` and `RunConfig.strategies`.
    name: str

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Pick the context for one question; report a failure in `failure`, do not raise."""
        ...


def answer_question(
    strategy: Strategy,
    question: Question,
    *,
    pin: ModelPin,
    wall: ContextWall | None,
    send: SendChatRequest,
) -> FinalStepResult:
    """Retrieve with `strategy`, then run the shared final step (§7, §8).

    `question.answer_type` is used only by the final step, to word the answer
    format; retrieval receives `question.text` alone. A failed retrieval
    returns its `failure` outcome and makes no call.
    """
    retrieval = strategy.retrieve(question.text)
    trace = {"retrieval": retrieval.trace}
    if retrieval.failure is not None:
        return FinalStepResult(
            outcome=retrieval.failure, final_answer=None, response=None, trace=trace
        )
    if retrieval.context is None:
        raise ValueError(
            f"strategy {strategy.name!r} returned neither a context nor a failure "
            f"for question {question.question_id!r}"
        )
    final = run_final_step(
        pin=pin,
        context=retrieval.context,
        question_text=question.text,
        answer_type=question.answer_type,
        wall=wall,
        send=send,
    )
    return final.model_copy(update={"trace": {**trace, **final.trace}})
