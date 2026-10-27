"""Tokens and dollars per question, read from a stored run's `answers.jsonl`.

A question's cost counts every model call behind it: the final call and, for the tiers, the
retrieval calls (the Cypher-writing call, the agent's steps), which sit in `retrieval_usage`.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None


class _Row(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_id: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    retrieval_usage: _Usage | None = None


class QuestionCost(BaseModel):
    """What one question cost: its family, all tokens, and all dollars."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    family: str
    tokens: int
    usd: float


def family_of(question_id: str) -> str:
    """The family in a question id (`<corpus>:<FAMILY>:...`).

    Raises:
        ValueError: the id has no family part.
    """
    parts = question_id.split(":")
    if len(parts) < 3 or not parts[1]:
        raise ValueError(
            f"expected a question id '<corpus>:<FAMILY>:<anchors>', found {question_id!r}"
        )
    return parts[1]


def _cost_of_row(row: _Row) -> QuestionCost:
    retrieval = row.retrieval_usage or _Usage()
    final_tokens = (row.prompt_tokens or 0) + (row.completion_tokens or 0)
    tokens = final_tokens + retrieval.prompt_tokens + retrieval.completion_tokens
    usd = (row.cost_usd or 0.0) + (retrieval.cost_usd or 0.0)
    return QuestionCost(
        question_id=row.question_id, family=family_of(row.question_id), tokens=tokens, usd=usd
    )


def read_question_costs(run_dir: Path) -> list[QuestionCost]:
    """One `QuestionCost` per row of the run's `answers.jsonl`, in file order.

    Raises:
        FileNotFoundError: the run has no `answers.jsonl`.
    """
    path = run_dir / "answers.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"expected {path}, found none")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [_cost_of_row(_Row.model_validate_json(line)) for line in lines if line]


def mean_usd_per_question(costs: list[QuestionCost]) -> float:
    """Dollars per question over all rows.

    Raises:
        ValueError: no rows.
    """
    if not costs:
        raise ValueError("expected at least one question cost, found none")
    return sum(c.usd for c in costs) / len(costs)


def family_means(costs: list[QuestionCost]) -> dict[str, tuple[float, float]]:
    """Family -> (mean tokens, mean dollars) per question."""
    grouped: dict[str, list[QuestionCost]] = defaultdict(list)
    for cost in costs:
        grouped[cost.family].append(cost)
    return {
        f: (sum(c.tokens for c in rows) / len(rows), sum(c.usd for c in rows) / len(rows))
        for f, rows in grouped.items()
    }
