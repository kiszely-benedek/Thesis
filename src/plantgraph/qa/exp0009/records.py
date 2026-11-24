"""The measurement record of a run: a completeness check, and an offline re-score (design §19.11).

Both arms keep EXP-0008's four files per run: `calls.jsonl` (one line per model call, with tokens,
cost, latency and provider), `answers.jsonl` (one scored row per question), `timings.jsonl` and
`environment.jsonl`. With those and the gold answers, correctness, precision, recall and F1 can be
recomputed after the run without a single new model call. `check_run_records` proves the files are
complete; `rescore` proves the stored `correct` flags are reproducible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.llm.models import CallRecord
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.gold import build_gold_scoring
from plantgraph.qa.harness.jsonl_tail import parse_jsonl
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import AnswerType, Question, QuestionResult
from plantgraph.qa.scoring import normalize_scalar, score_answer
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.scoring_b import resolve_item, score_answer_b

#: the answer types whose answer is a list of items, for which precision and recall make sense
_SET_TYPES = (AnswerType.TAG_SET, AnswerType.VALVE_SET, AnswerType.UNIT_SET, AnswerType.SHEET_SET)


def check_run_records(run_dir: Path) -> list[str]:
    """What is missing from a run's record; an empty list means the record is complete.

    Checks that every answer row has at least one call record (same question id and strategy),
    that every call record carries tokens, cost, latency and provider (a cached reply keeps the
    values recorded when it was first paid for), and that the timing and environment files exist.
    """
    run = RunDir(run_dir)
    problems = [
        f"{path.name} is missing or empty"
        for path in (run.timings_path, run.environment_path, run.calls_path, run.answers_path)
        if not path.is_file() or path.stat().st_size == 0
    ]
    if problems:
        return problems
    calls = list(parse_jsonl(run.calls_path, CallRecord.model_validate_json))
    problems += [p for call in calls for p in _call_problems(call)]
    called = {(c.question_id, c.strategy) for c in calls}
    problems += [
        f"no call record for answered question {row.question_id} ({row.strategy})"
        for row in run.read_rows()
        if (row.question_id, row.strategy) not in called
    ]
    return problems


def _call_problems(call: CallRecord) -> list[str]:
    where = f"call {call.question_id}/{call.strategy}"
    response = call.response
    if response is None:
        return [] if call.error_kind else [f"{where} has no response and no error kind"]
    missing = [
        name
        for name in ("prompt_tokens", "completion_tokens", "cost_usd", "latency_s", "provider")
        if getattr(response, name) is None
    ]
    return [f"{where} lacks response.{name}" for name in missing]


def require_complete_records(run_dir: Path) -> None:
    """Raise with the first problems of an incomplete record.

    Raises:
        ValueError: the record is incomplete.
    """
    problems = check_run_records(run_dir)
    if problems:
        raise ValueError(
            f"expected a complete record in {run_dir}, found {len(problems)} problem(s): "
            f"{problems[:3]}"
        )


# ---- the offline re-score ---------------------------------------------------------------------


@dataclass(frozen=True)
class RescoreInputs:
    """The gold-side inputs a re-score needs: connector numbers, flow edges, the B index."""

    connector_tags: frozenset[str]
    valid_edges: frozenset[tuple[str, str]]
    #: the plant index of a B corpus (`score_answer_b`); `None` scores with the frozen scorer
    index: PlantIndex | None = None


class RowScore(BaseModel):
    """One re-scored row, beside what the run stored."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    stored_correct: bool
    correct: bool
    precision: float | None
    recall: float | None
    f1: float | None


class RescoreReport(BaseModel):
    """The re-score of one run."""

    model_config = ConfigDict(frozen=True)

    rows: list[RowScore]

    @property
    def mismatches(self) -> list[str]:
        """Question ids whose re-scored `correct` differs from the stored one."""
        return [r.question_id for r in self.rows if r.correct != r.stored_correct]


def inputs_from_corpus(corpus_id: str, ingest_json: Path, *, is_b: bool) -> RescoreInputs:
    """Rebuild a corpus (no model, no Neo4j) and read its gold-side scoring inputs."""
    artifacts = load_corpus_artifacts(corpus_id, ingest_json)
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(f"expected a ground-truth plant for {corpus_id!r}, found none")
    view = NetworkxGraphView(corpus_id, artifacts.localized_sheets, artifacts.resolution)
    gold = build_gold_scoring(plant, view)
    return RescoreInputs(gold.connector_tags, gold.valid_edges, PlantIndex(plant) if is_b else None)


def rescore(
    run_dir: Path, questions: Mapping[str, Question], inputs: RescoreInputs
) -> RescoreReport:
    """Score every answer row again from `answers.jsonl` and the question file alone.

    Raises:
        ValueError: a row names a question that is not in `questions`.
    """
    rows = [_rescore_row(row, questions, inputs) for row in RunDir(run_dir).read_rows()]
    return RescoreReport(rows=rows)


def _rescore_row(
    row: QuestionResult, questions: Mapping[str, Question], inputs: RescoreInputs
) -> RowScore:
    question = questions.get(row.question_id)
    if question is None:
        raise ValueError(f"expected question {row.question_id} in the question file, found none")
    if inputs.index is None:
        scored = score_answer(
            question, row.outcome, row.final_answer,
            connector_tags=inputs.connector_tags, valid_edges=inputs.valid_edges,
        )  # fmt: skip
    else:
        scored = score_answer_b(
            question, row.outcome, row.final_answer, inputs.index,
            connector_tags=inputs.connector_tags, valid_edges=inputs.valid_edges,
        )  # fmt: skip
    precision, recall = _precision_recall(question, row, inputs)
    return RowScore(
        question_id=row.question_id,
        stored_correct=row.correct,
        correct=scored.correct,
        precision=precision,
        recall=recall,
        f1=scored.f1,
    )


def _precision_recall(
    question: Question, row: QuestionResult, inputs: RescoreInputs
) -> tuple[float | None, float | None]:
    """Precision and recall of a set answer over its items (nodes for VALVE_SET)."""
    answer = row.final_answer
    if question.answer_type not in _SET_TYPES or answer is None or answer.not_present:
        return None, None
    if not isinstance(answer.answer, list) or not isinstance(question.reference, list):
        return None, None
    gold, given = _as_sets(question.answer_type, question.reference, answer.answer, inputs)
    hits = len(gold & given)
    return (hits / len(given) if given else 0.0), (hits / len(gold) if gold else 0.0)


def _as_sets(
    answer_type: AnswerType, reference: list[str], answer: list[str], inputs: RescoreInputs
) -> tuple[set[str], set[str]]:
    if answer_type is AnswerType.VALVE_SET and inputs.index is not None:
        index = inputs.index
        return (
            {n for item in reference for n in resolve_item(index, item)},
            {n for item in answer for n in resolve_item(index, item)},
        )
    return {normalize_scalar(x) for x in reference}, {normalize_scalar(x) for x in answer}
