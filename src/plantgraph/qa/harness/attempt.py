"""Answering one work item: build the senders, run the strategy, score, and account for the cost.

Split out of `runner.py`, which decides *which* items to run and in what order. Answering and
scoring are two steps: `run_unscored` needs no gold (the demo's live cascade calls it alone),
`attempt` is `run_unscored` followed by the scoring.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import (
    ChatRequest,
    ChatResponse,
    ProviderError,
    QuestionDeadline,
    RequestTimedOut,
)
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.attempt_models import AttemptSettings, UnscoredAnswer
from plantgraph.qa.harness.gold import GoldScoring
from plantgraph.qa.harness.routing_gold import RoutingGold, add_routing_metrics
from plantgraph.qa.harness.usage_meter import TimingRow, UsageMeter
from plantgraph.qa.models import (
    CorpusRecord,
    Outcome,
    Question,
    QuestionResult,
    RunConfig,
)
from plantgraph.qa.scoring import score_answer
from plantgraph.qa.strategies.base import AskedQuestion, Strategy, answer_question


@dataclass(frozen=True)
class LoadedCorpus:
    """One corpus's view for the strategies and its gold scoring inputs for the harness."""

    view: NetworkxGraphView
    gold: GoldScoring
    routing_gold: RoutingGold
    record: CorpusRecord
    #: The checked database for CypherRAG; `None` when the run does not include it.
    cypher: CypherSource | None


@dataclass(frozen=True)
class WorkItem:
    """One answer to produce: a strategy, a question and which repeat."""

    strategy: Strategy
    question: Question
    repeat: int


@dataclass(frozen=True)
class Answered:
    """A finished item: its `answers.jsonl` row and its `timings.jsonl` row."""

    row: QuestionResult
    timing: TimingRow


#: The meter of the item this thread is answering. Strategies are built once and keep one
#: retrieval sender, so the sender finds the right item's meter here (one per thread).
_ACTIVE_METER: ContextVar[UsageMeter | None] = ContextVar("active_meter", default=None)


def active_remaining_s() -> float | None:
    """The time budget left for the question this thread is answering (`None` without one).

    The agent loop reads it before each step, so it can stop early enough for the final answer.
    """
    meter = _ACTIVE_METER.get()
    return None if meter is None else meter.remaining_s


def sender_factory(client: ChatClient, config: RunConfig) -> Callable[[str], SendChatRequest]:
    """For a strategy name, a sender for its own LLM calls (query writing, router fallback).

    They go through the run's client, so the cache, the paid-call guard and the log all apply.
    The call is metered on the item the calling thread is inside `attempt` for.
    """
    return sender_for_run(client, config.run_id)


def sender_for_run(client: ChatClient, run_id: str) -> Callable[[str], SendChatRequest]:
    """`sender_factory` for a caller that has a run id but no `RunConfig` (the live cascade)."""

    def sender_for(strategy_name: str) -> SendChatRequest:
        def send(request: ChatRequest) -> ChatResponse:
            meter = _ACTIVE_METER.get()
            if meter is None:
                raise RuntimeError(
                    "expected a retrieval call to be made inside `attempt`, which sets the "
                    "item's meter; found none"
                )
            # the strategy sees only the text; the harness reads the question id from the meter
            return meter.timed_call(
                lambda timeout_s: client.complete(
                    request,
                    run_id=run_id,
                    question_id=meter.question_id,
                    strategy=strategy_name,
                    timeout_s=timeout_s,
                ),
                is_final=False,
            )

        return send

    return sender_for


def attempt(
    item: WorkItem,
    config: RunConfig,
    corpus: LoadedCorpus,
    client: ChatClient,
    meter: UsageMeter,
) -> Answered | ProviderError:
    """Answer one item and score it; a provider error that outlived the retries is returned.

    `meter` belongs to this item alone.
    """
    settings = AttemptSettings.from_config(config)
    answer = run_unscored(item.strategy, item.question, settings, client, meter)
    if isinstance(answer, ProviderError):
        return answer
    return Answered(_scored_row(item, settings, corpus, answer), _timing_row(item, answer))


def run_unscored(
    strategy: Strategy,
    asked: AskedQuestion,
    settings: AttemptSettings,
    client: ChatClient,
    meter: UsageMeter,
) -> UnscoredAnswer | ProviderError:
    """Retrieve and answer one question without scoring it: no gold is needed or read.

    A question that ran out of time comes back as a `TIMED_OUT` answer, not an exception.
    `meter` belongs to this question alone.
    """
    token = _ACTIVE_METER.set(meter)
    try:
        return _answer_unscored(strategy, asked, settings, client, meter)
    finally:
        _ACTIVE_METER.reset(token)


def _answer_unscored(
    strategy: Strategy,
    asked: AskedQuestion,
    settings: AttemptSettings,
    client: ChatClient,
    meter: UsageMeter,
) -> UnscoredAnswer | ProviderError:
    def send(request: ChatRequest) -> ChatResponse:
        return meter.timed_call(
            lambda timeout_s: client.complete(
                request,
                run_id=settings.run_id,
                question_id=asked.question_id,
                strategy=strategy.name,
                timeout_s=timeout_s,
            ),
            is_final=True,
        )

    meter.begin(asked.question_id)
    started = time.monotonic()
    try:
        step = answer_question(
            strategy,
            asked,
            pin=settings.answer_pin,
            wall=settings.context_wall,
            send=send,
            primer=settings.primer,
        )
    except ProviderError as error:
        return error
    except (RequestTimedOut, QuestionDeadline) as error:
        cause = "request" if isinstance(error, RequestTimedOut) else "deadline"
        wall_s = time.monotonic() - started
        return _timed_out(strategy, settings, meter, {"timed_out": cause}, wall_s=wall_s)
    wall_s = time.monotonic() - started
    if step.outcome is Outcome.TIMED_OUT:  # the final call ran out; retrieval's trace is kept
        return _timed_out(strategy, settings, meter, dict(step.trace), wall_s=wall_s)
    trace = dict(step.trace)
    response = step.response
    return UnscoredAnswer(
        strategy=strategy.name,
        outcome=step.outcome,
        final_answer=step.final_answer,
        prompt_tokens=response.prompt_tokens if response else 0,
        completion_tokens=response.completion_tokens if response else 0,
        cost_usd=response.cost_usd if response else None,
        latency_s=response.latency_s if response else 0.0,
        # 0 when retrieval failed before any prompt was built
        context_chars=int(trace.get("prompt_chars", 0)),
        trace=trace,
        retrieval_usage=meter.end(),
        wall_s=wall_s,
        local_compute_s=max(0.0, wall_s - meter.seconds_in_calls),
        spent_usd=meter.spent_usd,
        final_call_cached=response.from_cache if response else None,
    )


def _scored_row(
    item: WorkItem, settings: AttemptSettings, corpus: LoadedCorpus, answer: UnscoredAnswer
) -> QuestionResult:
    """Score against gold; a `TIMED_OUT` answer is wrong and gets no routing metrics."""
    question = item.question
    if answer.outcome is Outcome.TIMED_OUT:
        return answer.as_row(settings, question.question_id, item.repeat, False, None)
    scored = score_answer(
        question,
        answer.outcome,
        answer.final_answer,
        connector_tags=corpus.gold.connector_tags,
        valid_edges=corpus.gold.valid_edges,
    )
    trace = dict(answer.trace)
    add_routing_metrics(trace, question, corpus.routing_gold)
    with_metrics = replace(answer, trace=trace)
    return with_metrics.as_row(
        settings, question.question_id, item.repeat, scored.correct, scored.f1
    )


def _timing_row(item: WorkItem, answer: UnscoredAnswer) -> TimingRow:
    usage = answer.retrieval_usage
    return TimingRow(
        question_id=item.question.question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        # wall-clock, so it lives in timings.jsonl and never in the byte-identical answers
        local_compute_s=answer.local_compute_s,
        spent_usd=answer.spent_usd,
        n_cached_retrieval_calls=usage.n_cached if usage else 0,
    )


def _timed_out(
    strategy: Strategy,
    settings: AttemptSettings,
    meter: UsageMeter,
    trace: dict[str, Any],
    *,
    wall_s: float,
) -> UnscoredAnswer:
    """The answer of a question that ran out of its call-time budget.

    `trace` holds `timed_out` (the cause) and any retrieval trace gathered before the timeout.
    Everything in it comes from recorded latencies, so a replay gives the same bytes.
    """
    usage = meter.end()
    # `latency_s` is the final call's share, like on every row, so the cascade's total
    # (final + retrieval-side latency) comes to the recorded elapsed time, not twice that
    final_call_s = max(0.0, meter.recorded_elapsed_s - usage.llm_latency_s)
    return UnscoredAnswer(
        strategy=strategy.name,
        outcome=Outcome.TIMED_OUT,
        final_answer=None,
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        latency_s=final_call_s,
        context_chars=0,
        trace={
            **trace,
            "question_deadline_s": settings.question_deadline_s,
            "recorded_elapsed_s": meter.recorded_elapsed_s,
        },
        retrieval_usage=usage,
        wall_s=wall_s,
        local_compute_s=max(0.0, wall_s - meter.seconds_in_calls),
        spent_usd=meter.spent_usd,
        final_call_cached=None,
    )


def provider_error_row(item: WorkItem, config: RunConfig, error: ProviderError) -> QuestionResult:
    """The row recorded for an item whose provider error survived the second try."""
    return QuestionResult(
        run_id=config.run_id,
        question_id=item.question.question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        outcome=Outcome.PROVIDER_ERROR,
        final_answer=None,
        correct=False,
        f1=None,
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        latency_s=0.0,
        context_chars=0,
        trace={"provider_error": str(error)},
    )
