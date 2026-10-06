"""Does a tier's answer pass the policy's acceptance rules, and which tiers does a question reach?

Reads `Signals` only. This is the minimum the join needs to know which tier rows are
required; the full policy engine builds on it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, Signals
from plantgraph.qa.models import Outcome
from plantgraph.qa.need.labels import NeedLabel

#: tier name -> question id -> signals of that tier's answer.
SignalsByTier = Mapping[str, Mapping[str, Signals]]


def is_accepted(signals: Signals, rules: frozenset[AcceptRule]) -> bool:
    """True when every rule holds.

    Raises:
        ValueError: `ROWS` on a tier whose answers carry no query row count.
    """
    if AcceptRule.ANSWERED in rules and signals.outcome is not Outcome.ANSWERED:
        return False
    if AcceptRule.ROWS in rules:
        if signals.n_rows is None:
            raise ValueError(
                f"expected tier {signals.tier!r} to report a query row count for the 'rows' "
                f"rule, found none on {signals.question_id!r}"
            )
        if signals.n_rows == 0:
            return False
    return not (AcceptRule.NOT_ABSTAINED in rules and signals.not_present is not False)


@dataclass(frozen=True)
class Walk:
    """The tiers one question reaches under a policy."""

    #: Tiers with a row, in order, up to and including the one that was accepted (if any).
    tried: tuple[str, ...]
    #: The first reached tier that has no row; `None` when the walk is complete.
    missing_tier: str | None


def start_index(policy: CascadePolicy, need_label: NeedLabel | None) -> int:
    """Index of the first tier tried; 0 unless the policy starts some labels later.

    Raises:
        ValueError: the policy needs a label and none is known.
    """
    if not policy.start_tier_by_label:
        return 0
    if need_label is None:
        raise ValueError(
            f"expected a need label for policy {policy.name!r} (it starts tiers by label), "
            "found none; pass an anchor finder or include a need-aware run in the join"
        )
    return policy.start_tier_by_label.get(need_label, 0)


def walk_question(
    policy: CascadePolicy, question_id: str, need_label: NeedLabel | None, signals: SignalsByTier
) -> Walk:
    """Follow one question through the tiers until one is accepted or a row is missing."""
    tried: list[str] = []
    for tier in policy.tiers[start_index(policy, need_label) :]:
        tier_signals = signals.get(tier.name, {}).get(question_id)
        if tier_signals is None:
            return Walk(tuple(tried), tier.name)
        tried.append(tier.name)
        if is_accepted(tier_signals, tier.accept):
            break
    return Walk(tuple(tried), None)
