"""The B stratum of the scorer audit (design §19.7, stage P1d).

The **scorer audit** has a second model (the judge) read a sample of answered rows and say whether
the programmatic scorer was right. EXP-0008's selection covers A2's answer types. B's two new
types, VALVE_SET and POSITION, are scored by node resolution, so they get a stratum of their own:
half the main sample's size, every wrong row first, then a seeded random sample of right rows.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.exp0009.records import RowScore
from plantgraph.qa.models import AnswerType, Question, QuestionResult
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.scoring_b import resolve_item

STRATUM_SHARE = 0.5
B_TYPES = (AnswerType.VALVE_SET, AnswerType.POSITION)
#: the fixed seed of the random sample of right rows
SAMPLE_SEED = 20261124


class StratumRow(BaseModel):
    """One B row picked for the judge."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    question_id: str
    correct: bool
    #: the parsed answer as canonical JSON, so identical answers to one question count once
    answer_key: str


def stratum_size(main_rows: int) -> int:
    """ceil(0.5 x the main sample's row count)."""
    return math.ceil(STRATUM_SHARE * main_rows)


def candidate_rows(
    rows: Iterable[QuestionResult], questions: Mapping[str, Question]
) -> list[StratumRow]:
    """B-type answered rows, deduplicated by question and parsed answer (first occurrence wins)."""
    seen: set[tuple[str, str]] = set()
    found: list[StratumRow] = []
    for row in rows:
        question = questions[row.question_id]
        if question.answer_type not in B_TYPES or row.final_answer is None:
            continue
        key = json.dumps(row.final_answer.answer, sort_keys=True)
        if (row.question_id, key) in seen:
            continue
        seen.add((row.question_id, key))
        found.append(
            StratumRow(
                run_id=row.run_id, question_id=row.question_id, correct=row.correct, answer_key=key
            )
        )
    return found


def select_stratum(candidates: Sequence[StratumRow], main_rows: int) -> list[StratumRow]:
    """Every wrong row first (in input order), then a seeded random sample of right rows.

    The result never exceeds `stratum_size(main_rows)`; wrong rows come first, so when they
    alone exceed it the stratum holds only wrong rows.
    """
    size = stratum_size(main_rows)
    wrong = [r for r in candidates if not r.correct]
    right = [r for r in candidates if r.correct]
    random.Random(SAMPLE_SEED).shuffle(right)
    return [*wrong, *right][:size]


def resolution_lines(index: PlantIndex, question: Question, row: QuestionResult) -> list[str]:
    """For the disagreement sheet: each answered item and the nodes the B scorer resolved it to."""
    answer = None if row.final_answer is None else row.final_answer.answer
    if not isinstance(answer, list):
        return [f"answer {answer!r}"]
    return [f"{item} -> {sorted(resolve_item(index, str(item)))}" for item in answer]


def resolution_sheet(
    index: PlantIndex,
    picked: Sequence[StratumRow],
    rows: Mapping[str, QuestionResult],
    questions: Mapping[str, Question],
) -> str:
    """The resolution text of every picked row, one block per row."""
    blocks = []
    for pick in picked:
        lines = resolution_lines(index, questions[pick.question_id], rows[pick.question_id])
        blocks.append("\n".join([f"{pick.question_id} (correct={pick.correct})", *lines]))
    return "\n\n".join(blocks)


def write_stratum(out: Path, picked: Sequence[StratumRow]) -> None:
    """Write the picked rows as JSON lines; never overwrites."""
    with out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(r.model_dump_json() + "\n" for r in picked))


def rows_from_rescore(scores: Iterable[RowScore]) -> int:
    """How many re-scored rows were wrong (the stratum's wrong-row pool, for the report)."""
    return sum(not s.correct for s in scores)
