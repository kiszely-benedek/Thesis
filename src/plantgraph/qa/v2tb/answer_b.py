"""The B final step: retrieve, then ask the model with the B prompt and read the reply the B way.

The frozen `answer_question` and `run_final_step` have no seam for another answer type or another
primer (design `v2t-b` §10, finding F4), so each is copied here with the three B calls swapped in
(`render_final_answer_request_b`, `to_outcome_b`, the B primer). Everything else is the frozen
code: the fit check, the overflow handling, the V2T template.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from plantgraph.llm.models import (
    ContextOverflow,
    ContextWall,
    ModelPin,
    QuestionDeadline,
    RequestTimedOut,
)
from plantgraph.qa.final_answer import FinalStepResult, SendChatRequest
from plantgraph.qa.final_answer_variants import template_path_for
from plantgraph.qa.fit import check_fit, handle_overflow
from plantgraph.qa.models import AnswerType, Outcome
from plantgraph.qa.strategies.base import AskedQuestion, Strategy
from plantgraph.qa.v2tb.final_answer_b import render_final_answer_request_b, to_outcome_b

B_SUFFIX = "_b"


def a_name_of(b_strategy_name: str) -> str:
    """The A strategy a B strategy derives from: `graph_agent_lines_b` gives `graph_agent_lines`.

    Raises:
        ValueError: the name does not end in `_b`.
    """
    if not b_strategy_name.endswith(B_SUFFIX):
        raise ValueError(
            f"expected a B strategy name ending in {B_SUFFIX!r}, found {b_strategy_name!r}"
        )
    return b_strategy_name.removesuffix(B_SUFFIX)


def run_final_step_b(
    *,
    pin: ModelPin,
    context: str,
    question_text: str,
    answer_type: AnswerType,
    wall: ContextWall | None,
    send: SendChatRequest,
    primer: bool = False,
    class_names: Collection[str] | None = None,
    template_path: Path | None = None,
) -> FinalStepResult:
    """Copy of the frozen `run_final_step`, with the B request renderer and the B parser."""
    request = render_final_answer_request_b(
        pin=pin,
        context=context,
        question_text=question_text,
        answer_type=answer_type,
        primer=primer,
        class_names=class_names,
        template_path=template_path,
    )
    prompt_chars = len(request.messages[0].content)
    decision = check_fit(prompt_chars, wall)
    if not decision.should_call:
        if decision.outcome is None:
            raise RuntimeError("fit.check_fit returned should_call=False without an outcome")
        return FinalStepResult(
            outcome=decision.outcome, final_answer=None, response=None, trace=decision.trace
        )
    try:
        response = send(request)
    except ContextOverflow as error:
        decision = handle_overflow(prompt_chars, error)
        return FinalStepResult(
            outcome=Outcome.DID_NOT_FIT, final_answer=None, response=None, trace=decision.trace
        )
    outcome, final_answer = to_outcome_b(response.text, answer_type)
    trace = {**decision.trace, "prompt_chars": prompt_chars}
    if outcome is not Outcome.ANSWERED:
        trace["raw_reply"] = response.text
    return FinalStepResult(
        outcome=outcome, final_answer=final_answer, response=response, trace=trace
    )


def answer_question_b(
    strategy: Strategy,
    question: AskedQuestion,
    *,
    pin: ModelPin,
    wall: ContextWall | None,
    send: SendChatRequest,
    primer: bool = False,
    class_names: Collection[str] | None = None,
) -> FinalStepResult:
    """Copy of the frozen `answer_question`: retrieve with `strategy`, then the B final step.

    The V2T template is chosen by the strategy's A name, so a B strategy reads A's template.
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
    try:
        final = run_final_step_b(
            pin=pin,
            context=retrieval.context,
            question_text=question.text,
            answer_type=question.answer_type,
            wall=wall,
            send=send,
            primer=primer,
            class_names=class_names,
            template_path=template_path_for(a_name_of(strategy.name)),
        )
    except (RequestTimedOut, QuestionDeadline) as error:
        cause = "request" if isinstance(error, RequestTimedOut) else "deadline"
        return FinalStepResult(
            outcome=Outcome.TIMED_OUT,
            final_answer=None,
            response=None,
            trace={**trace, "timed_out": cause},
        )
    return final.model_copy(update={"trace": {**trace, **final.trace}})
