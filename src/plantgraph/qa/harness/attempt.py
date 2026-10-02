"""Answering one work item: build the senders, run the strategy, score, and account for the cost.

Split out of `runner.py`, which decides *which* items to run and in what order.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ChatRequest, ChatResponse, ProviderError
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


def sender_factory(
    client: ChatClient, config: RunConfig, meter: UsageMeter
) -> Callable[[str], SendChatRequest]:
    """For a strategy name, a sender for its own LLM calls (query writing, router fallback).

    They go through the run's client, so the cache, the paid-call guard and the log all apply.
    """

    def sender_for(strategy_name: str) -> SendChatRequest:
        def send(request: ChatRequest) -> ChatResponse:
            # the strategy sees only the text; the harness reads the question id from the meter
            return meter.timed_call(
                lambda: client.complete(
                    request,
                    run_id=config.run_id,
                    question_id=meter.question_id,
                    strategy=strategy_name,
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
    """Answer one item; a provider error that outlived the transport retries is returned."""
    question_id = item.question.question_id

    def send(request: ChatRequest) -> ChatResponse:
        return meter.timed_call(
            lambda: client.complete(
                request, run_id=config.run_id, question_id=question_id, strategy=item.strategy.name
            ),
            is_final=True,
        )

    meter.begin(question_id)
    started = time.monotonic()
    try:
        step = answer_question(
            item.strategy, item.question, pin=config.answer_pin, wall=config.context_wall, send=send
        )
    except ProviderError as error:
        return error
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
    timing = TimingRow(
        question_id=question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        # wall-clock, so it lives in timings.jsonl and never in the byte-identical answers
        local_compute_s=max(0.0, wall_s - meter.seconds_in_calls),
        spent_usd=meter.spent_usd,
        n_cached_retrieval_calls=usage.n_cached,
    )
    return Answered(row, timing)


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
