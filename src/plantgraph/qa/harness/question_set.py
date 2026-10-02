"""Read the sampled question files a run will ask (written by `qa.questions`)."""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.models import Question
from plantgraph.qa.questions.cli import QUESTIONS_FILENAME


def questions_path(questions_root: Path, corpus_id: str) -> Path:
    """Where `qa.questions` writes a corpus's sampled questions."""
    return questions_root / corpus_id / QUESTIONS_FILENAME


def load_questions(path: Path, corpus_id: str) -> list[Question]:
    """Read one corpus's `questions.jsonl`.

    Raises:
        ValueError: a question belongs to another corpus, or an id is repeated.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    questions = [Question.model_validate_json(line) for line in lines]
    wrong = [q.question_id for q in questions if q.corpus_id != corpus_id]
    if wrong:
        raise ValueError(f"expected only {corpus_id!r} questions in {path}, found {wrong[:3]}")
    ids = [question.question_id for question in questions]
    if len(set(ids)) != len(ids):
        raise ValueError(f"expected unique question ids in {path}, found repeats")
    return questions
