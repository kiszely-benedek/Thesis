"""The policy engine: walk a question through a policy's tiers and say which answer is final.

Reads `Signals` only. It never touches `correct`, the reference answer or any other gold
field; `evaluate.py` is the one place that scores a `Decision` afterwards.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from plantgraph.qa.cascade.accept import SignalsByTier, walk_question
from plantgraph.qa.cascade.models import CascadePolicy, Decision
from plantgraph.qa.models import Outcome
from plantgraph.qa.need.labels import NeedLabel

POLICIES_DIR = Path(__file__).parent / "policies"


def load_policy(path: Path) -> CascadePolicy:
    """Read one policy JSON file."""
    return CascadePolicy.model_validate_json(path.read_text(encoding="utf-8"))


def load_policies(directory: Path = POLICIES_DIR) -> dict[str, CascadePolicy]:
    """Every `*.json` policy in `directory`, keyed by policy name (which must be unique)."""
    policies: dict[str, CascadePolicy] = {}
    for path in sorted(directory.glob("*.json")):
        policy = load_policy(path)
        if policy.name in policies:
            raise ValueError(f"expected unique policy names, found {policy.name!r} twice")
        policies[policy.name] = policy
    return policies


def decide(
    policy: CascadePolicy,
    question_id: str,
    need_label: NeedLabel | None,
    signals: SignalsByTier,
    escalate: bool | None = None,
) -> Decision:
    """The decision for one question: tiers tried, final tier, summed cost and latency.

    `escalate` is for the reference arms only (see `walk_question`); a policy leaves it `None`.

    Raises:
        ValueError: the question reaches a tier that has no row (the join is incomplete).
    """
    walk = walk_question(policy, question_id, need_label, signals, escalate)
    if walk.missing_tier is not None:
        raise ValueError(
            f"expected a row for question {question_id!r} in tier {walk.missing_tier!r} "
            f"(policy {policy.name!r} reaches it), found none"
        )
    answered_by = walk.accepted or _fallback_tier(policy, question_id, walk.tried, signals)
    tried = [signals[tier][question_id] for tier in walk.tried]
    return Decision(
        policy=policy.name,
        question_id=question_id,
        tiers_tried=walk.tried,
        answered_by=answered_by,
        cost_usd=sum(s.cost_usd for s in tried),
        latency_s=sum(s.latency_s for s in tried),
        latency_complete=all(s.latency_complete for s in tried),
    )


def _fallback_tier(
    policy: CascadePolicy, question_id: str, tried: tuple[str, ...], signals: SignalsByTier
) -> str | None:
    """The first tier's own answer, when nothing was accepted and it was tried and ANSWERED."""
    first = policy.tiers[0].name
    if not policy.fallback_to_first_answer or first not in tried:
        return None
    return first if signals[first][question_id].outcome is Outcome.ANSWERED else None


def decide_all(
    policy: CascadePolicy,
    question_ids: list[str],
    need_labels: Mapping[str, NeedLabel],
    signals: SignalsByTier,
    escalate: Mapping[str, bool] | None = None,
) -> list[Decision]:
    """`decide` for every question, in order; `escalate` maps question id to the override."""
    overrides = escalate or {}
    return [
        decide(policy, qid, need_labels.get(qid), signals, overrides.get(qid))
        for qid in question_ids
    ]
