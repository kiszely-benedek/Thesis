"""Turn one stored answer row into `Signals`: runaway, total cost, abstention, query rows.

The cost includes an estimate for calls abandoned at their timeout (`TIMED_OUT` rows).
"""

from __future__ import annotations

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.models import Signals
from plantgraph.qa.models import Outcome, QuestionResult
from plantgraph.qa.need.labels import NeedLabel

#: Upper-bound cost of one call abandoned at its timeout (cascade-v2 note, section 6.5): the
#: measured mean cost of a 16k-token runaway. An abandoned call may still be billed by the provider.
ABANDONED_CALL_COST_USD = 0.0106


def is_runaway(row: QuestionResult, pin: ModelPin) -> bool:
    """True for a parse failure, or when the final call used up the pin's whole output cap.

    A runaway is a model that kept reasoning until it was cut off, leaving no answer.
    """
    return row.outcome is Outcome.PARSE_FAILURE or row.completion_tokens >= pin.max_output_tokens


def abandoned_cost_usd(row: QuestionResult) -> float:
    """Estimated charge for the calls the harness gave up on (their real cost is not recorded)."""
    usage = row.retrieval_usage
    return 0.0 if usage is None else usage.n_abandoned * ABANDONED_CALL_COST_USD


def query_row_count(row: QuestionResult) -> int | None:
    """Rows a Cypher query returned (from the trace); `None` when the tier ran no query."""
    retrieval = row.trace.get("retrieval")
    if not isinstance(retrieval, dict):
        return None
    n_rows = retrieval.get("n_rows")
    return n_rows if isinstance(n_rows, int) else None


def extract_signals(
    row: QuestionResult,
    tier: str,
    pin: ModelPin,
    need_label: NeedLabel | None,
    local_compute_s: float | None = None,
) -> Signals:
    """The gold-free view of `row`; `local_compute_s` is from `timings.jsonl` (`None`: absent).

    Raises:
        ValueError: a cost is missing, so the total would silently be too low.
    """
    recorded_cost = row.total_cost_usd
    if recorded_cost is None:
        raise ValueError(
            f"expected a cost on every call of {row.question_id!r} in tier {tier!r}, "
            "found a retrieval call with no cost"
        )
    cost = recorded_cost + abandoned_cost_usd(row)
    return Signals(
        question_id=row.question_id,
        tier=tier,
        outcome=row.outcome,
        n_rows=query_row_count(row),
        not_present=None if row.final_answer is None else row.final_answer.not_present,
        runaway=is_runaway(row, pin),
        cost_usd=cost,
        # every model call counts, not just the final one; local compute only when recorded
        latency_s=row.total_llm_latency_s + (local_compute_s or 0.0),
        final_latency_s=row.latency_s,
        latency_complete=local_compute_s is not None,
        need_label=need_label,
    )
