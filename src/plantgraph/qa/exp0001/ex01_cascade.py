"""Derive cascade_v3's EX01 answers offline from the two tier arms' rows (no extra model call).

The cascade asks its cheap first tier (a Cypher query) and moves to the second (the graph agent)
only when the first answer is not accepted. Both tiers were asked every question here, so the
cascade's answer and cost can be read off afterwards. The accept rules and the walk are the
frozen ones in `qa.cascade` (`policy.decide`, `accept.walk_question`); this module feeds them.
"""

from __future__ import annotations

from plantgraph.qa.cascade.models import CascadePolicy, Decision, Signals
from plantgraph.qa.cascade.policy import decide
from plantgraph.qa.exp0001.ex01_arms import ARM_OF_STRATEGY
from plantgraph.qa.exp0001.ex01_models import CASCADE_ARM, Ex01AnswerRow
from plantgraph.qa.models import Outcome

Key = tuple[str, int]  # (qid, repeat)


def tier_arms(policy: CascadePolicy) -> dict[str, str]:
    """Policy tier name -> the arm whose rows feed it.

    Raises:
        ValueError: a tier runs a strategy that has no EX01 arm.
    """
    unknown = [t.strategy for t in policy.tiers if t.strategy not in ARM_OF_STRATEGY]
    if unknown:
        raise ValueError(
            f"expected policy {policy.name!r} to use strategies in {sorted(ARM_OF_STRATEGY)}, "
            f"found {unknown}"
        )
    return {tier.name: ARM_OF_STRATEGY[tier.strategy] for tier in policy.tiers}


def derive_cascade_rows(rows: list[Ex01AnswerRow], policy: CascadePolicy) -> list[Ex01AnswerRow]:
    """One `cascade_v3` row per (question, repeat) for which every tier has a row.

    Raises:
        ValueError: a tier row has no recorded cost, so the cascade's cost would be too low.
    """
    arm_of_tier = tier_arms(policy)
    by_arm = {(row.arm, row.qid, row.repeat): row for row in rows}
    derived: list[Ex01AnswerRow] = []
    for qid, repeat in _keys_with_all_tiers(rows, set(arm_of_tier.values())):
        tier_rows = {tier: by_arm[(arm, qid, repeat)] for tier, arm in arm_of_tier.items()}
        derived.append(_cascade_row(policy, qid, repeat, tier_rows))
    return derived


def _keys_with_all_tiers(rows: list[Ex01AnswerRow], arms: set[str]) -> list[Key]:
    present: dict[Key, set[str]] = {}
    for row in rows:
        if row.outcome is Outcome.PROVIDER_ERROR:
            continue  # no answer and no cost: the cascade cannot be derived for this item
        present.setdefault((row.qid, row.repeat), set()).add(row.arm)
    return sorted(key for key, found in present.items() if arms <= found)


def _cascade_row(
    policy: CascadePolicy, qid: str, repeat: int, tier_rows: dict[str, Ex01AnswerRow]
) -> Ex01AnswerRow:
    signals = {tier: {qid: _signals(tier, row)} for tier, row in tier_rows.items()}
    decision = decide(policy, qid, None, signals)
    tried = [tier_rows[tier] for tier in decision.tiers_tried]
    source = tier_rows[decision.answered_by] if decision.answered_by else tried[0]
    return source.model_copy(
        update={
            "arm": CASCADE_ARM,
            "cost_usd": decision.cost_usd,
            "latency_s": sum(row.latency_s for row in tried),
            "local_compute_s": sum(row.local_compute_s for row in tried),
            "trace": _trace(decision),
        }
    )


def _trace(decision: Decision) -> dict[str, object]:
    return {"answered_by": decision.answered_by, "tiers_tried": list(decision.tiers_tried)}


def _signals(tier: str, row: Ex01AnswerRow) -> Signals:
    """The gold-free view of a tier row that the frozen accept rules read."""
    if row.cost_usd is None:
        raise ValueError(
            f"expected a cost on {row.arm!r} {row.qid} repeat {row.repeat}, found none"
        )
    answered = row.outcome is Outcome.ANSWERED
    return Signals(
        question_id=row.qid,
        tier=tier,
        outcome=row.outcome,
        n_rows=_query_row_count(row.trace),
        not_present=row.not_present if answered else None,
        runaway=row.outcome is Outcome.PARSE_FAILURE,
        cost_usd=row.cost_usd,
        latency_s=row.latency_s + row.local_compute_s,
        final_latency_s=row.latency_s,
        latency_complete=True,
        need_label=None,
    )


def _query_row_count(trace: dict[str, object]) -> int | None:
    """Rows the Cypher query returned (in the retrieval trace); `None` for a tier without one."""
    retrieval = trace.get("retrieval")
    n_rows = retrieval.get("n_rows") if isinstance(retrieval, dict) else None
    return n_rows if isinstance(n_rows, int) else None
