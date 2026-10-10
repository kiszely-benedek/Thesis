"""Helpers for the demo tests: a tiny finished run on disk, as the harness would leave it."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from plantgraph.llm.models import ModelPin
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import (
    AnswerType,
    CallUsage,
    FinalAnswer,
    Outcome,
    Question,
    QuestionFamily,
    QuestionResult,
    RunConfig,
)

PIN = ModelPin(backend="openrouter", model_id="toy/model", max_output_tokens=100)


def question(
    question_id: str, text: str, answer_type: AnswerType, evidence_sheets: list[str]
) -> Question:
    return Question(
        question_id=question_id,
        corpus_id="TOY",
        family=QuestionFamily.CONNECTED,
        template_id="t",
        template_version="1",
        text=text,
        answer_type=answer_type,
        answerable=True,
        reference=None,
        evidence_sheets=evidence_sheets,
        generator_seed=0,
    )


def row(
    question_id: str,
    strategy: str,
    cost: float,
    answer: str | list[str] | None = None,
    retrieval_cost: float = 0.0,
) -> QuestionResult:
    return QuestionResult(
        run_id="r",
        question_id=question_id,
        strategy=strategy,
        repeat=0,
        outcome=Outcome.ANSWERED,
        final_answer=None if answer is None else FinalAnswer(answer=answer, not_present=False),
        correct=False,
        f1=None,
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=cost,
        latency_s=1.0,
        context_chars=0,
        retrieval_usage=CallUsage(cost_usd=retrieval_cost),
    )


def write_run(
    root: Path, run_id: str, corpus_id: str, rows: list[QuestionResult], pin: ModelPin = PIN
) -> Path:
    """Write `run_config.json` and `answers.jsonl` for a run; returns its folder."""
    run = RunDir(root / run_id)
    config = RunConfig(
        run_id=run_id,
        experiment="toy",
        reported=False,
        corpora=[corpus_id],
        strategies={s: {} for s in {r.strategy for r in rows}},
        answer_pin=pin,
        question_set_sha256="0" * 64,
        git_commit="x",
        git_dirty=False,
        created_at=datetime(2026, 10, 10, tzinfo=UTC),
    )
    run.freeze(config)
    for item in rows:
        run.append_row(item)
    return run.path
