"""A short, derived summary of a run's rows, printed when the run ends.

Not the report: `report.py` (QA-T11) owns accuracy, intervals and the CSV. This
only counts what happened, so a dry run can be eyeballed at once.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.harness.gold import ROUTING_HIT_TRACE_KEY
from plantgraph.qa.models import Outcome, Question, QuestionResult
from plantgraph.qa.questions.availability import k_bin_of


class RunSummary(BaseModel):
    """Row counts of one run, by strategy, k-bin and outcome."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    n_rows: int
    #: Rows written by this invocation (the rest were already on disk).
    n_new_rows: int
    n_provider_errors: int
    #: strategy -> k-bin -> outcome -> number of rows.
    outcomes_by_k_bin: dict[str, dict[str, dict[str, int]]]
    #: strategy -> share of rows with a routing hit; only strategies that route.
    routing_recall: dict[str, float]


def summarize_rows(
    run_id: str, rows: list[QuestionResult], questions: list[Question], n_new_rows: int
) -> RunSummary:
    """Count `rows` by strategy, the k-bin of their question, and outcome."""
    bin_of = {question.question_id: k_bin_of(question).value for question in questions}
    counts: dict[str, dict[str, Counter[str]]] = {}
    for row in rows:
        by_bin = counts.setdefault(row.strategy, {})
        by_bin.setdefault(bin_of[row.question_id], Counter())[row.outcome.value] += 1
    return RunSummary(
        run_id=run_id,
        n_rows=len(rows),
        n_new_rows=n_new_rows,
        n_provider_errors=sum(row.outcome is Outcome.PROVIDER_ERROR for row in rows),
        outcomes_by_k_bin={
            strategy: {k_bin: dict(counter) for k_bin, counter in by_bin.items()}
            for strategy, by_bin in counts.items()
        },
        routing_recall=_routing_recall(rows),
    )


def _routing_recall(rows: list[QuestionResult]) -> dict[str, float]:
    hits: dict[str, list[bool]] = {}
    for row in rows:
        hit = row.trace.get(ROUTING_HIT_TRACE_KEY)
        if isinstance(hit, bool):
            hits.setdefault(row.strategy, []).append(hit)
    return {strategy: sum(values) / len(values) for strategy, values in hits.items()}
