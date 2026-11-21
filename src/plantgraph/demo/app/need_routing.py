"""Demo-side need routing: pick the first cascade tier from the question's need label.

A *need label* names the shape of evidence a question asks for (e.g. "everything upstream up
to the first valve"). The frozen policy `cascade_v4_iso` starts some labels at a later tier, but
the frozen live cascade refuses any policy that routes by label (a typed question has no label).
So the demo labels the question itself with the same frozen rules, then runs a label-free policy
that already starts at the right tier. Design `demo-v2.md` section 2.2 explains why this is exact.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.labels import AnchorFinder, classify_need
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.need.labels import NeedLabel


class RoutedPolicy(BaseModel):
    """A label-routed policy plus one label-free policy per start tier it can use."""

    model_config = ConfigDict(frozen=True)

    #: The policy as loaded; shown to the user, never run directly.
    evaluated: CascadePolicy
    #: Start tier index -> label-free policy that begins at that tier.
    by_start: dict[int, CascadePolicy]

    def start_for(self, label: NeedLabel) -> int:
        """Index of the first tier tried for `label`; 0 when the policy does not route it."""
        return self.evaluated.start_tier_by_label.get(label, 0)


class NeedRoute(BaseModel):
    """Where one question starts: its need label and the first tier tried."""

    model_config = ConfigDict(frozen=True)

    need_label: NeedLabel
    start_index: int
    #: Name of the first tier tried.
    start_tier: str

    @property
    def routed(self) -> bool:
        """True when the question skips the first tier."""
        return self.start_index > 0


def split_by_start(policy: CascadePolicy) -> RoutedPolicy:
    """Derive one label-free policy for every start tier the policy uses (and for 0).

    Raises:
        ValueError: the policy sets `last_tier_by_label`, or a start index is not a tier.
    """
    if policy.last_tier_by_label:
        raise ValueError(
            "expected a policy without last_tier_by_label (only start tiers are routed), "
            f"found {sorted(label.value for label in policy.last_tier_by_label)} "
            f"in {policy.name!r}"
        )
    starts = {0, *policy.start_tier_by_label.values()}
    for start in starts:
        if not 0 <= start < len(policy.tiers):
            raise ValueError(
                f"expected a start tier index in 0..{len(policy.tiers) - 1}, found {start} "
                f"in {policy.name!r}"
            )
    return RoutedPolicy(
        evaluated=policy,
        by_start={start: _derive(policy, start) for start in sorted(starts)},
    )


def _derive(policy: CascadePolicy, start: int) -> CascadePolicy:
    """The policy from tier `start` on, with no label routing."""
    # The original falls back to tier 0's answer only if tier 0 was tried; a later start never
    # tries it, so the derived policy turns the fallback off (same decision, see section 2.2).
    return policy.model_copy(
        update={
            "tiers": policy.tiers[start:],
            "start_tier_by_label": {},
            "fallback_to_first_answer": policy.fallback_to_first_answer and start == 0,
        }
    )


def route_question(text: str, finder: AnchorFinder, routed: RoutedPolicy) -> NeedRoute:
    """Label a free-text question with the frozen rules and say which tier it starts at."""
    label = classify_need(text, finder)
    start = routed.start_for(label)
    return NeedRoute(
        need_label=label,
        start_index=start,
        start_tier=routed.evaluated.tiers[start].name,
    )
