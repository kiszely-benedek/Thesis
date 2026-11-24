"""Answering and scoring one item of a B run: the B twin of `harness/attempt.py`.

The frozen functions call `answer_question` and `score_answer` by name, so they cannot be pointed at
the B final step or the B scorer (design §10, finding F4). The four that reach those calls are
copied here, each naming its original; everything around them is the frozen code: the meter, the
timer, the timed-out and timing rows, the sender (the same `ContextVar`, so a strategy's own calls
are metered on the right item).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import (
    ChatRequest,
    ChatResponse,
    ProviderError,
    QuestionDeadline,
    RequestTimedOut,
)
from plantgraph.qa.harness.attempt import (
    _ACTIVE_METER,
    Answered,
    LoadedCorpus,
    WorkItem,
    _timed_out,
    _timing_row,
)
from plantgraph.qa.harness.attempt_models import AttemptSettings, UnscoredAnswer
from plantgraph.qa.harness.routing_gold import add_routing_metrics
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.local_timer import LocalTimer, deactivate
from plantgraph.qa.models import Outcome, QuestionResult, RunConfig
from plantgraph.qa.strategies.base import AskedQuestion, Strategy
from plantgraph.qa.v2tb.answer_b import answer_question_b
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.scoring_b import score_answer_b


@dataclass(frozen=True)
class LoadedCorpusB(LoadedCorpus):
    """A `LoadedCorpus` plus the index the B scorer resolves descriptors with (gold side)."""

    plant_index: PlantIndex | None = None


def attempt_b(
    item: WorkItem,
    config: RunConfig,
    corpus: LoadedCorpusB,
    client: ChatClient,
    meter: UsageMeter,
) -> Answered | ProviderError:
    """Copy of `attempt`: answer one item with the B final step and score it with the B scorer."""
    settings = replace(AttemptSettings.from_config(config), class_names=corpus.class_names)
    answer = run_unscored_b(item.strategy, item.question, settings, client, meter)
    if isinstance(answer, ProviderError):
        return answer
    return Answered(_scored_row_b(item, settings, corpus, answer), _timing_row(item, answer))


def run_unscored_b(
    strategy: Strategy,
    asked: AskedQuestion,
    settings: AttemptSettings,
    client: ChatClient,
    meter: UsageMeter,
) -> UnscoredAnswer | ProviderError:
    """Copy of `run_unscored`: retrieve and answer one question, scoring nothing."""
    token = _ACTIVE_METER.set(meter)
    timer = LocalTimer()
    timer_token = timer.activate()
    try:
        answer = _answer_unscored_b(strategy, asked, settings, client, meter)
    finally:
        deactivate(timer_token)
        _ACTIVE_METER.reset(token)
    return answer if isinstance(answer, ProviderError) else replace(answer, local_timer=timer)


def _answer_unscored_b(
    strategy: Strategy,
    asked: AskedQuestion,
    settings: AttemptSettings,
    client: ChatClient,
    meter: UsageMeter,
) -> UnscoredAnswer | ProviderError:
    """Copy of `_answer_unscored`, calling `answer_question_b`."""

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
    started = time.perf_counter()
    try:
        step = answer_question_b(
            strategy,
            asked,
            pin=settings.answer_pin,
            wall=settings.context_wall,
            send=send,
            primer=settings.primer,
            class_names=settings.class_names,
        )
    except ProviderError as error:
        return error
    except (RequestTimedOut, QuestionDeadline) as error:
        cause = "request" if isinstance(error, RequestTimedOut) else "deadline"
        wall_s = time.perf_counter() - started
        return _timed_out(strategy, settings, meter, {"timed_out": cause}, wall_s=wall_s)
    wall_s = time.perf_counter() - started
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
        context_chars=int(trace.get("prompt_chars", 0)),
        trace=trace,
        retrieval_usage=meter.end(),
        wall_s=wall_s,
        local_compute_s=max(0.0, wall_s - meter.seconds_in_calls),
        spent_usd=meter.spent_usd,
        final_call_cached=response.from_cache if response else None,
    )


def _scored_row_b(
    item: WorkItem, settings: AttemptSettings, corpus: LoadedCorpusB, answer: UnscoredAnswer
) -> QuestionResult:
    """Copy of `_scored_row`, scoring with `score_answer_b`; a `TIMED_OUT` answer is wrong."""
    question = item.question
    if answer.outcome is Outcome.TIMED_OUT:
        return answer.as_row(settings, question.question_id, item.repeat, False, None)
    if corpus.plant_index is None:
        raise ValueError(f"expected a plant index for corpus {question.corpus_id!r}, found none")
    scored = score_answer_b(
        question,
        answer.outcome,
        answer.final_answer,
        corpus.plant_index,
        connector_tags=corpus.gold.connector_tags,
        valid_edges=corpus.gold.valid_edges,
    )
    trace = dict(answer.trace)
    add_routing_metrics(trace, question, corpus.routing_gold)
    with_metrics = replace(answer, trace=trace)
    return with_metrics.as_row(
        settings, question.question_id, item.repeat, scored.correct, scored.f1
    )
