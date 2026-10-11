"""Table I2: per-question local compute of a strategy on a corpus, split by where the time went."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from plantgraph.infra.report_inputs import RunData
from plantgraph.infra.report_models import StrategyComputeRow

#: strategy name -> (needs a database server, needs the graph in process memory); design section 2.
STRATEGY_NEEDS: dict[str, tuple[bool, bool]] = {
    "cypher_rag_plant": (True, False),
    "graph_agent_low_steps": (False, True),
    "hierarchical_need_rules_plant": (False, True),
}


def percentile(values: Sequence[float], share: float) -> float:
    """The `share` quantile (0..1) by linear interpolation between the closest ranks."""
    if not values:
        raise ValueError("expected at least one value for a percentile, found none")
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def usable(run: RunData) -> bool:
    """A full replay counts only if its answers are byte-identical to its source run's."""
    return run.basis != "replay" or run.replay_status == "identical"


def compute_row(run: RunData) -> StrategyComputeRow:
    """Summarise one run's `timings.jsonl`.

    Raises:
        ValueError: the run has no timings, or its strategy has no known infrastructure needs.
    """
    if not run.timings:
        raise ValueError(f"expected timing rows in run {run.run_id}, found none")
    if run.strategy not in STRATEGY_NEEDS:
        raise ValueError(
            f"expected a strategy in {sorted(STRATEGY_NEEDS)}, found {run.strategy!r}; "
            "add its infrastructure needs to STRATEGY_NEEDS"
        )
    needs_database, needs_memory_graph = STRATEGY_NEEDS[run.strategy]
    local = [row.local_compute_s for row in run.timings]
    local_sum = sum(local)
    latency_s = run.llm_latency_s + local_sum
    has_split = run.basis != "old_run"  # only the original runs lack the split timers
    db_client = sum(row.db_client_s for row in run.timings)
    graph_api = sum(row.graph_api_s for row in run.timings)
    return StrategyComputeRow(
        role=run.role,
        strategy=run.strategy,
        corpus_id=run.corpus_id,
        basis=run.basis,
        needs_database=needs_database,
        needs_memory_graph=needs_memory_graph,
        n_questions=len(local),
        local_median_s=statistics.median(local),
        local_p90_s=percentile(local, 0.9),
        local_max_s=max(local),
        local_sum_s=local_sum,
        db_client_sum_s=db_client if has_split else None,
        db_server_sum_s=sum(row.db_server_s for row in run.timings) if has_split else None,
        graph_api_sum_s=graph_api if has_split else None,
        other_sum_s=local_sum - db_client - graph_api if has_split else None,
        local_share_of_latency=local_sum / latency_s if latency_s > 0 else 0.0,
        token_usd_per_question=run.answers_cost_usd / len(local),
        n_cost_missing=run.n_cost_missing,
    )
