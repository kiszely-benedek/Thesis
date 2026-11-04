"""What D4 records per model call, and the aggregates reported in a decision file.

A **parse failure** is an answer that is not the JSON object the prompt asked for; the pair then
counts as "not accepted" (design 5.4) and is reported here, never hidden.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict


class PairCall(BaseModel):
    """One model call about one pair card (a cache hit is a call too)."""

    model_config = ConfigDict(frozen=True)

    card: str
    answer_text: str
    same_item: bool | None  # None when the answer did not parse
    reason: str | None
    parse_ok: bool
    from_cache: bool
    cost_usd: float | None  # as the provider billed it when the call was made; None if not reported
    latency_s: float  # of the original live call, also on a cache hit


class LlmStats(BaseModel):
    """Aggregates over the calls of one decider run."""

    model_config = ConfigDict(frozen=True)

    pin_hash: str
    prompt_sha256: str  # hash of the system prompt, to be pre-registered
    n_calls: int
    n_cache_hits: int
    n_parse_failures: int
    parse_failure_rate: float | None
    cost_usd_spent: float  # live calls only: money this run really spent
    cost_usd_recorded: float  # all calls, cache hits at their original cost
    n_live_calls_without_cost: int  # live calls whose provider reported no cost
    latency_p50_s: float | None
    latency_p95_s: float | None


def summarize(calls: Sequence[PairCall], pin_hash: str, prompt_sha256: str) -> LlmStats:
    """Aggregate `calls`; percentiles and the rate are None for an empty run."""
    live = [call for call in calls if not call.from_cache]
    failures = sum(1 for call in calls if not call.parse_ok)
    latencies = sorted(call.latency_s for call in calls)
    return LlmStats(
        pin_hash=pin_hash,
        prompt_sha256=prompt_sha256,
        n_calls=len(calls),
        n_cache_hits=len(calls) - len(live),
        n_parse_failures=failures,
        parse_failure_rate=failures / len(calls) if calls else None,
        cost_usd_spent=sum(call.cost_usd or 0.0 for call in live),
        cost_usd_recorded=sum(call.cost_usd or 0.0 for call in calls),
        n_live_calls_without_cost=sum(1 for call in live if call.cost_usd is None),
        latency_p50_s=_percentile(latencies, 0.50),
        latency_p95_s=_percentile(latencies, 0.95),
    )


def _percentile(sorted_values: Sequence[float], q: float) -> float | None:
    """Nearest-rank percentile: the smallest value with at least a fraction `q` at or below it."""
    if not sorted_values:
        return None
    rank = max(math.ceil(q * len(sorted_values)), 1)
    return sorted_values[rank - 1]
