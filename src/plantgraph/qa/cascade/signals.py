"""Turn one stored answer row into `Signals`: runaway, total cost, abstention, query rows."""

from __future__ import annotations

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.models import Signals
from plantgraph.qa.models import Outcome, QuestionResult
from plantgraph.qa.need.labels import NeedLabel


def is_runaway(row: QuestionResult, pin: ModelPin) -> bool:
    """True for a parse failure, or when the final call used up the pin's whole output cap.

    A runaway is a model that kept reasoning until it was cut off, leaving no answer.
    """
    return row.outcome is Outcome.PARSE_FAILURE or row.completion_tokens >= pin.max_output_tokens


def query_row_count(row: QuestionResult) -> int | None:
    """Rows a Cypher query returned (from the trace); `None` when the tier ran no query."""
    retrieval = row.trace.get("retrieval")
    if not isinstance(retrieval, dict):
        return None
    n_rows = retrieval.get("n_rows")
    return n_rows if isinstance(n_rows, int) else None


def extract_signals(
    row: QuestionResult, tier: str, pin: ModelPin, need_label: NeedLabel | None
) -> Signals:
    """The gold-free view of `row`.

    Raises:
        ValueError: a cost is missing, so the total would silently be too low.
    """
    cost = row.total_cost_usd
    if cost is None:
        raise ValueError(
            f"expected a cost on every call of {row.question_id!r} in tier {tier!r}, "
            "found a retrieval call with no cost"
        )
    return Signals(
        question_id=row.question_id,
        tier=tier,
        outcome=row.outcome,
        n_rows=query_row_count(row),
        not_present=None if row.final_answer is None else row.final_answer.not_present,
        runaway=is_runaway(row, pin),
        cost_usd=cost,
        latency_s=row.latency_s,
        need_label=need_label,
    )
