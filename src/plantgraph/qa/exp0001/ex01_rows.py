"""Turn one answered EX01 item into an `Ex01AnswerRow`."""

from __future__ import annotations

import json
from pathlib import Path

from plantgraph.llm.models import CallRecord, ProviderError
from plantgraph.qa.cascade.signals import abandoned_cost_usd
from plantgraph.qa.exp0001.ex01_models import Ex01AnswerRow
from plantgraph.qa.harness.attempt_models import AttemptSettings, UnscoredAnswer
from plantgraph.qa.models import AnswerValue, Outcome


def answer_text_of(answer: AnswerValue) -> str | None:
    """A free-text answer as a string; a list or number (a model ignoring the format) as JSON."""
    if answer is None or isinstance(answer, str):
        return answer
    return json.dumps(answer)


def row_from_answer(
    answer: UnscoredAnswer,
    settings: AttemptSettings,
    *,
    qid: str,
    arm: str,
    repeat: int,
    provider: str | None,
) -> Ex01AnswerRow:
    """The row of a finished item; cost and latency count every model call of the question."""
    # `as_row` is the harness's own sum of the final and retrieval-side calls
    summed = answer.as_row(settings, qid, repeat, False, None)
    cost = summed.total_cost_usd
    final = answer.final_answer
    return Ex01AnswerRow(
        run_id=settings.run_id,
        qid=qid,
        arm=arm,
        repeat=repeat,
        outcome=answer.outcome,
        answer_text=None if final is None else answer_text_of(final.answer),
        not_present=False if final is None else final.not_present,
        cost_usd=None if cost is None else cost + abandoned_cost_usd(summed),
        latency_s=summed.total_llm_latency_s,
        local_compute_s=answer.local_compute_s,
        prompt_tokens=answer.prompt_tokens,
        completion_tokens=answer.completion_tokens,
        context_chars=answer.context_chars,
        provider=provider,
        trace=answer.trace,
    )


def provider_error_row(
    error: ProviderError, settings: AttemptSettings, *, qid: str, arm: str, repeat: int
) -> Ex01AnswerRow:
    """The row of an item whose provider error outlived the retry."""
    return Ex01AnswerRow(
        run_id=settings.run_id,
        qid=qid,
        arm=arm,
        repeat=repeat,
        outcome=Outcome.PROVIDER_ERROR,
        answer_text=None,
        not_present=False,
        cost_usd=None,
        latency_s=0.0,
        prompt_tokens=0,
        completion_tokens=0,
        context_chars=0,
        trace={"provider_error": str(error)},
    )


def last_provider(calls_path: Path, question_id: str, strategy: str) -> str | None:
    """The host of the question's most recent model call, read from `calls.jsonl`.

    The runner answers one item at a time, so the question's last logged call is its final call.
    """
    if not calls_path.exists():
        return None
    for line in reversed(calls_path.read_text(encoding="utf-8").splitlines()):
        record = CallRecord.model_validate_json(line)
        if record.question_id == question_id and record.strategy == strategy:
            return None if record.response is None else record.response.provider
    return None
