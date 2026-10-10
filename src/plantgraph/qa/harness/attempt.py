"""Answering one work item: build the senders, run the strategy, score, and account for the cost.

Split out of `runner.py`, which decides *which* items to run and in what order.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass

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
from plantgraph.qa.harness.gold import GoldScoring
from plantgraph.qa.harness.routing_gold import RoutingGold, add_routing_metrics
from plantgraph.qa.harness.usage_meter import TimingRow, UsageMeter
from plantgraph.qa.models import CorpusRecord, Outcome, Question, QuestionResult, RunConfig
from plantgraph.qa.scoring import score_answer
from plantgraph.qa.strategies.base import Strategy, answer_question


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
                    run_id=config.run_id,
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
    """Answer one item; a provider error that outlived the transport retries is returned.

    `meter` belongs to this item alone.
    """
    token = _ACTIVE_METER.set(meter)
    try:
        return _attempt(item, config, corpus, client, meter)
    finally:
        _ACTIVE_METER.reset(token)


def _attempt(
    item: WorkItem,
    config: RunConfig,
    corpus: LoadedCorpus,
    client: ChatClient,
    meter: UsageMeter,
) -> Answered | ProviderError:
    question_id = item.question.question_id

    def send(request: ChatRequest) -> ChatResponse:
        return meter.timed_call(
            lambda timeout_s: client.complete(
                request,
                run_id=config.run_id,
                question_id=question_id,
                strategy=item.strategy.name,
                timeout_s=timeout_s,
            ),
            is_final=True,
        )

    meter.begin(question_id)
    started = time.monotonic()
    try:
        step = answer_question(
            item.strategy,
            item.question,
            pin=config.answer_pin,
            wall=config.context_wall,
            send=send,
            primer=config.primer,
        )
    except ProviderError as error:
        return error
    except (RequestTimedOut, QuestionDeadline) as error:
        return _timed_out(item, config, meter, error, wall_s=time.monotonic() - started)
    wall_s = time.monotonic() - started
    scored = score_answer(
        item.question,
        step.outcome,
        step.final_answer,
        connector_tags=corpus.gold.connector_tags,
        valid_edges=corpus.gold.valid_edges,
    )
    trace = dict(step.trace)
    add_routing_metrics(trace, item.question, corpus.routing_gold)
    usage = meter.end()
    response = step.response
    row = QuestionResult(
        run_id=config.run_id,
        question_id=question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        outcome=step.outcome,
        final_answer=step.final_answer,
        correct=scored.correct,
        f1=scored.f1,
        prompt_tokens=response.prompt_tokens if response else 0,
        completion_tokens=response.completion_tokens if response else 0,
        cost_usd=response.cost_usd if response else None,
        latency_s=response.latency_s if response else 0.0,
        # 0 when retrieval failed before any prompt was built
        context_chars=int(trace.get("prompt_chars", 0)),
        trace=trace,
        retrieval_usage=usage,
    )
    return Answered(row, _timing_row(item, meter, usage.n_cached, wall_s))


def _timing_row(item: WorkItem, meter: UsageMeter, n_cached: int, wall_s: float) -> TimingRow:
    return TimingRow(
        question_id=item.question.question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        # wall-clock, so it lives in timings.jsonl and never in the byte-identical answers
        local_compute_s=max(0.0, wall_s - meter.seconds_in_calls),
        spent_usd=meter.spent_usd,
        n_cached_retrieval_calls=n_cached,
    )


def _timed_out(
    item: WorkItem,
    config: RunConfig,
    meter: UsageMeter,
    error: RequestTimedOut | QuestionDeadline,
    *,
    wall_s: float,
) -> Answered:
    """The ordinary, committed row of a question that ran out of its call-time budget.

    Everything in it comes from recorded latencies, so a replay writes the same bytes.
    """
    usage = meter.end()
    cause = "request" if isinstance(error, RequestTimedOut) else "deadline"
    row = QuestionResult(
        run_id=config.run_id,
        question_id=item.question.question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        outcome=Outcome.TIMED_OUT,
        final_answer=None,
        correct=False,
        f1=None,
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        latency_s=meter.recorded_elapsed_s,
        context_chars=0,
        trace={
            "timed_out": cause,
            "question_deadline_s": config.question_deadline_s,
            "recorded_elapsed_s": meter.recorded_elapsed_s,
        },
        retrieval_usage=usage,
    )
    return Answered(row, _timing_row(item, meter, usage.n_cached, wall_s))


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
