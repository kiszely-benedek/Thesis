"""Need routing: the derived label-free policies decide exactly like the label-routed original."""

from __future__ import annotations

import itertools

import pytest

from plantgraph.demo.app.need_routing import NeedRoute, route_question, split_by_start
from plantgraph.qa.cascade.labels import anchor_finder
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, Signals, TierSpec
from plantgraph.qa.cascade.policy import decide
from plantgraph.qa.models import Outcome
from plantgraph.qa.need.labels import NeedLabel
from qa_need_toy import ISOLATION_QUESTION, need_toy

QID = "q1"
ISOLATE_UP = NeedLabel.UPSTREAM_TO_FIRST_VALVE
ISOLATE_DOWN = NeedLabel.DOWNSTREAM_TO_FIRST_VALVE
STRICT = frozenset(
    {AcceptRule.ANSWERED, AcceptRule.NOT_ABSTAINED, AcceptRule.ROWS, AcceptRule.COMPLETE}
)


def _policy(
    start: dict[NeedLabel, int] | None = None,
    last: dict[NeedLabel, int] | None = None,
    fallback: bool = True,
) -> CascadePolicy:
    """Two tiers shaped like cascade_v4_iso: Cypher with strict rules, then an agent."""
    cypher = TierSpec(name="cypher", strategy="c", pin_sha256="a", accept=STRICT)
    agent = TierSpec(
        name="agent", strategy="g", pin_sha256="b", accept=frozenset({AcceptRule.ANSWERED})
    )
    return CascadePolicy(
        name="toy",
        tiers=(cypher, agent),
        fallback_to_first_answer=fallback,
        start_tier_by_label=start or {},
        last_tier_by_label=last or {},
    )


def _signals(tier: str, outcome: Outcome, rows: int, abstain: bool, cut: bool) -> Signals:
    # Cost and latency differ per tier so a wrongly summed tier shows up.
    cypher = tier == "cypher"
    return Signals(
        question_id=QID,
        tier=tier,
        outcome=outcome,
        n_rows=rows if cypher else None,
        not_present=abstain,
        runaway=False,
        cost_usd=0.01 if cypher else 0.05,
        latency_s=1.5 if cypher else 20.0,
        final_latency_s=1.0,
        latency_complete=True,
        need_label=None,
        truncated=cut if cypher else None,
    )


def _all_signals() -> list[dict[str, dict[str, Signals]]]:
    """Every outcome / rows / abstain / truncated combination, for both tiers."""
    combos = list(itertools.product(Outcome, (0, 3), (False, True), (False, True)))
    return [
        {"cypher": {QID: _signals("cypher", *first)}, "agent": {QID: _signals("agent", *second)}}
        for first in combos
        for second in combos
    ]


@pytest.mark.parametrize("fallback", [True, False])
def test_derived_policy_decides_like_the_original_for_every_label(fallback: bool) -> None:
    original = _policy(start={ISOLATE_UP: 1, ISOLATE_DOWN: 1}, fallback=fallback)
    routed = split_by_start(original)
    assert sorted(routed.by_start) == [0, 1]
    for label in NeedLabel:
        derived = routed.by_start[routed.start_for(label)]
        assert derived.start_tier_by_label == {}
        for signals in _all_signals():
            want = decide(original, QID, label, signals)
            got = decide(derived, QID, None, signals)
            assert (got.answered_by, got.tiers_tried, got.cost_usd, got.latency_s) == (
                want.answered_by,
                want.tiers_tried,
                want.cost_usd,
                want.latency_s,
            )


def test_start_one_policy_drops_the_first_tier_and_the_fallback() -> None:
    routed = split_by_start(_policy(start={ISOLATE_UP: 1}))
    assert [tier.name for tier in routed.by_start[1].tiers] == ["agent"]
    assert not routed.by_start[1].fallback_to_first_answer
    assert routed.by_start[0].fallback_to_first_answer
    assert routed.start_for(NeedLabel.PATH) == 0


def test_last_tier_by_label_is_refused() -> None:
    with pytest.raises(ValueError, match="last_tier_by_label"):
        split_by_start(_policy(last={NeedLabel.PATH: 0}))


def test_start_index_outside_the_tiers_is_refused() -> None:
    with pytest.raises(ValueError, match="start tier index"):
        split_by_start(_policy(start={ISOLATE_UP: 2}))


def _route(text: str) -> NeedRoute:
    finder = anchor_finder(need_toy().view())
    routed = split_by_start(_policy(start={ISOLATE_UP: 1, ISOLATE_DOWN: 1}))
    return route_question(text, finder, routed)


def test_isolation_from_upstream_routes_to_start_one() -> None:
    route = _route(ISOLATION_QUESTION)
    assert (route.need_label, route.start_index, route.start_tier) == (ISOLATE_UP, 1, "agent")
    assert route.routed


@pytest.mark.parametrize(
    "text",
    [
        "To cut P-3 off from all downstream equipment, which valves must be closed?",
        "Before maintenance on P-3, which valves have to be shut to stop every incoming flow?",
    ],
)
def test_other_isolation_wordings_start_at_zero(text: str) -> None:
    route = _route(text)
    assert (route.start_index, route.start_tier) == (0, "cypher")
    assert not route.routed
