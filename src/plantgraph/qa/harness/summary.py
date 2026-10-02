"""A short, derived summary of a run's rows, printed when the run ends.

Not the report: `report.py` (QA-T11) owns accuracy, intervals and the CSV. This
only counts what happened, so a dry run can be eyeballed at once.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.harness.gold import ROUTING_HIT_TRACE_KEY
from plantgraph.qa.harness.routing_gold import (
    EVIDENCE_NODE_RECALL_TRACE_KEY,
    RELAXED_ROUTING_HIT_TRACE_KEY,
)
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
    #: strategy -> share of rows whose routed sheets hold *some* valid path (`routing_gold.py`).
    relaxed_routing_recall: dict[str, float]
    #: strategy -> mean share of evidence items present in the serialized context.
    evidence_node_recall: dict[str, float]
    #: metric name -> strategy -> k-bin -> mean; the three routing metrics above, by k-bin.
    routing_metrics_by_k_bin: dict[str, dict[str, dict[str, float]]]
    #: strategy -> rate name -> share of the rows that report the trace key (see `_RATES`).
    trace_rates: dict[str, dict[str, float]]
    #: strategy -> mean total cost per question (final call plus retrieval-side calls), USD;
    #: rows with an unreported cost are left out.
    mean_total_cost_usd: dict[str, float]
    #: True when the hard spend cap ended the run early; rerun to resume.
    stopped_by_spend_cap: bool


#: Row-trace keys the harness adds, by the metric name used in the summary.
_ROUTING_METRIC_KEYS = {
    "routing_recall": ROUTING_HIT_TRACE_KEY,
    "relaxed_routing_recall": RELAXED_ROUTING_HIT_TRACE_KEY,
    "evidence_node_recall": EVIDENCE_NODE_RECALL_TRACE_KEY,
}

#: Rate name -> (key under `trace["retrieval"]`, whether a row counts as 1).
#: A row without the key (a strategy that does not report it, or retrieval failed) is left out.
_RATES: dict[str, tuple[str, Callable[[Any], bool]]] = {
    "over_budget_rate": ("over_budget", bool),
    "truncated_rate": ("truncated", bool),
    "route_fallback_rate": ("route_fallback", lambda value: value is not None),
    "router_fallback_rate": ("fallback_used", bool),
}


def summarize_rows(
    run_id: str,
    rows: list[QuestionResult],
    questions: list[Question],
    n_new_rows: int,
    *,
    stopped_by_spend_cap: bool = False,
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
        routing_recall=_mean_by_strategy(rows, ROUTING_HIT_TRACE_KEY),
        relaxed_routing_recall=_mean_by_strategy(rows, RELAXED_ROUTING_HIT_TRACE_KEY),
        evidence_node_recall=_mean_by_strategy(rows, EVIDENCE_NODE_RECALL_TRACE_KEY),
        routing_metrics_by_k_bin={
            metric: _mean_by_strategy_and_k_bin(rows, key, bin_of)
            for metric, key in _ROUTING_METRIC_KEYS.items()
        },
        trace_rates=_trace_rates(rows),
        mean_total_cost_usd=_mean_total_cost(rows),
        stopped_by_spend_cap=stopped_by_spend_cap,
    )


def _mean_total_cost(rows: list[QuestionResult]) -> dict[str, float]:
    costs: dict[str, list[float]] = {}
    for row in rows:
        total = row.total_cost_usd
        if total is not None:
            costs.setdefault(row.strategy, []).append(total)
    return {strategy: sum(found) / len(found) for strategy, found in costs.items()}


def _mean_by_strategy(rows: list[QuestionResult], key: str) -> dict[str, float]:
    """Mean of the numeric (or boolean) trace value `key`, over the rows that have it."""
    values: dict[str, list[float]] = {}
    for row in rows:
        value = row.trace.get(key)
        if isinstance(value, bool | float):
            values.setdefault(row.strategy, []).append(float(value))
    return {strategy: sum(found) / len(found) for strategy, found in values.items()}


def _mean_by_strategy_and_k_bin(
    rows: list[QuestionResult], key: str, bin_of: dict[str, str]
) -> dict[str, dict[str, float]]:
    by_bin: dict[str, dict[str, list[QuestionResult]]] = {}
    for row in rows:
        by_bin.setdefault(row.strategy, {}).setdefault(bin_of[row.question_id], []).append(row)
    result: dict[str, dict[str, float]] = {}
    for strategy, bins in by_bin.items():
        means = {k_bin: _mean_by_strategy(group, key) for k_bin, group in bins.items()}
        result[strategy] = {k_bin: mean[strategy] for k_bin, mean in means.items() if mean}
    return {strategy: bins for strategy, bins in result.items() if bins}


def _trace_rates(rows: list[QuestionResult]) -> dict[str, dict[str, float]]:
    """Per strategy, each rate in `_RATES` over the rows whose retrieval trace reports its key."""
    rates: dict[str, dict[str, float]] = {}
    for strategy in sorted({row.strategy for row in rows}):
        own = [row.trace.get("retrieval", {}) for row in rows if row.strategy == strategy]
        for name, (key, is_set) in _RATES.items():
            reported = [trace[key] for trace in own if key in trace]
            if reported:
                rates.setdefault(strategy, {})[name] = sum(map(is_set, reported)) / len(reported)
    return rates
