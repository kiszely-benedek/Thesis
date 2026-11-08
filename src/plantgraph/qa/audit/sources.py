"""Read stored runs into the audit's rows, and build what the judge may see from them.

`make_judge_input` is the single place that chooses which fields of a stored row and its
question reach the judge. Everything the scorer decided (`correct`, the outcome, `f1`, the
trace) is left behind there.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from plantgraph.qa.audit.models import JudgeInput, SourceRow
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import AnswerType, Outcome, Question, QuestionResult, RunConfig

#: Outcomes that carry something a judge can read. The others (retrieval error, did not fit,
#: provider error, time-out) have no answer; they are only counted.
JUDGEABLE_OUTCOMES = (Outcome.ANSWERED, Outcome.PARSE_FAILURE)

_SET_TYPES = frozenset({AnswerType.TAG_SET, AnswerType.UNIT_SET, AnswerType.SHEET_SET})
_SCALE_RE = re.compile(r"^[A-Za-z]+(\d+)")


@dataclass(frozen=True)
class LoadedRun:
    """One stored run: its rows by (question id, strategy) and its questions by id."""

    run_id: str
    results: dict[tuple[str, str], QuestionResult]
    questions: dict[str, Question]


def scale_of(corpus_id: str) -> str:
    """The sheet-count label in a corpus id: `H1000g21p3` gives "1000".

    Raises:
        ValueError: the id has no letters-then-digits prefix.
    """
    match = _SCALE_RE.match(corpus_id)
    if match is None:
        raise ValueError(
            f"expected a corpus id like 'H100g21p1' (letters, then the scale), got {corpus_id!r}"
        )
    return match.group(1)


def load_run(run_dir: Path, questions_root: Path) -> LoadedRun:
    """Read `run_config.json`, `answers.jsonl` and the questions of the run's corpora.

    Raises:
        ValueError: the run repeated its questions (the audit judges one answer per question).
    """
    config = RunConfig.model_validate_json((run_dir / "run_config.json").read_text("utf-8"))
    if config.repeats != 1:
        raise ValueError(f"expected a run with repeats=1, found {config.repeats} in {run_dir}")
    questions: dict[str, Question] = {}
    for corpus_id in config.corpora:
        for question in load_questions(questions_path(questions_root, corpus_id), corpus_id):
            questions[question.question_id] = question
    rows = RunDir(run_dir).read_rows()
    results = {(row.question_id, row.strategy): row for row in rows}
    return LoadedRun(config.run_id, results, questions)


def answer_key(result: QuestionResult, answer_type: AnswerType) -> str:
    """Canonical text of the answer, so equal answers (set order aside) share one key."""
    final = result.final_answer
    if final is None:
        return "raw:" + str(result.trace.get("raw_reply", result.outcome.value))
    value = final.answer
    if answer_type in _SET_TYPES and isinstance(value, list):
        value = sorted(value)
    return json.dumps({"answer": value, "not_present": final.not_present}, sort_keys=True)


def source_rows(run: LoadedRun) -> list[SourceRow]:
    """The judgeable rows of a run, sorted by question and strategy."""
    rows = []
    for (question_id, strategy), result in sorted(run.results.items()):
        if result.outcome not in JUDGEABLE_OUTCOMES:
            continue
        question = run.questions[question_id]
        rows.append(
            SourceRow(
                run_id=run.run_id,
                strategy=strategy,
                question_id=question_id,
                corpus_id=question.corpus_id,
                family=question.family,
                scale=scale_of(question.corpus_id),
                outcome=result.outcome,
                scorer_correct=result.correct,
                answer_key=answer_key(result, question.answer_type),
            )
        )
    return rows


def count_without_answer(run: LoadedRun) -> int:
    """Rows with no answer to judge (retrieval error and the like): counted, never judged."""
    return sum(1 for result in run.results.values() if result.outcome not in JUDGEABLE_OUTCOMES)


def make_judge_input(question: Question, result: QuestionResult, excerpt: str) -> JudgeInput:
    """What the judge sees. The scorer's verdict, outcome, f1 and trace are not copied."""
    final = result.final_answer
    raw_reply = result.trace.get("raw_reply")
    return JudgeInput(
        question_text=question.text,
        answer_type=question.answer_type,
        raw_reply=str(raw_reply) if raw_reply is not None else None,
        parsed_answer=final.answer if final is not None else None,
        not_present=final.not_present if final is not None else False,
        reference=question.reference,
        answerable=question.answerable,
        plant_excerpt=excerpt,
    )
