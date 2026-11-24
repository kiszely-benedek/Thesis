"""§10.6 (7): the frozen offline cascade decides alike under `policy_b()` and `cascade_v4_iso`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cascade_toy import CORPUS
from cascade_v4_toy import (
    AGENT_V2T,
    CYPHER_V2T,
    agent_rows,
    cypher_rows,
    write_tier,
)
from plantgraph.qa.cascade.evaluate import evaluate_decisions
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, decide_all, load_policy
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.v2tb.answer_b import B_SUFFIX
from plantgraph.qa.v2tb.policy_b import policy_b

#: one label per toy question: two start at the first tier, one at the agent tier (as A routes)
_NEED_LABELS = {
    "T1:q1": NeedLabel.GENERIC,
    "T1:q2": NeedLabel.UPSTREAM_TO_FIRST_VALVE,
    "T1:q3": NeedLabel.DOWNSTREAM_ALL,
    "T1:q4": NeedLabel.UPSTREAM_TO_FIRST_VALVE,
}


def _renamed(rows: list[dict[str, Any]], suffix: str) -> list[dict[str, Any]]:
    return [{**row, "strategy": row["strategy"] + suffix} for row in rows]


def _joined(tmp_path: Path, policy: CascadePolicy, suffix: str) -> JoinedCorpus:
    """The toy tier runs (rows named for the policy's strategies), joined under `policy`."""
    cypher, agent = policy.tiers
    sources = {
        cypher.name: TierSource(
            write_tier(
                tmp_path,
                "c",
                cypher.strategy,
                "pin_cypher_luna_low.json",
                _renamed(cypher_rows(), suffix),
            )  # fmt: skip
        ),
        agent.name: TierSource(
            write_tier(
                tmp_path,
                "a",
                agent.strategy,
                "pin_agent_luna_final_high.json",
                _renamed(agent_rows(), suffix),
            )  # fmt: skip
        ),
    }
    return join_corpus(policy, sources, CORPUS, tmp_path / "questions", known_labels=_NEED_LABELS)


def test_the_b_policy_decides_like_the_a_policy_on_the_same_tier_rows(tmp_path: Path) -> None:
    policy_a = load_policy(V2T_POLICIES_DIR / "cascade_v4_iso.json")
    joined_a = _joined(tmp_path / "a", policy_a, "")
    joined_b = _joined(tmp_path / "b", policy_b(), B_SUFFIX)

    decisions_a = decide_all(
        policy_a, joined_a.question_ids, joined_a.need_labels, joined_a.signals
    )
    decisions_b = decide_all(
        policy_b(), joined_b.question_ids, joined_b.need_labels, joined_b.signals
    )

    assert [d.model_dump(exclude={"policy"}) for d in decisions_b] == [
        d.model_dump(exclude={"policy"}) for d in decisions_a
    ]
    assert {d.policy for d in decisions_b} == {"cascade_v4_iso_b"}
    assert any(
        len(d.tiers_tried) == 2 for d in decisions_b
    )  # the toy escalates, so it is not vacuous
    assert evaluate_decisions(joined_b, decisions_b).summary.model_dump(
        exclude={"corpus_id", "policy"}
    ) == evaluate_decisions(joined_a, decisions_a).summary.model_dump(
        exclude={"corpus_id", "policy"}
    )


def test_the_b_policy_names_the_b_strategies_the_toy_rows_were_given(tmp_path: Path) -> None:
    joined = _joined(tmp_path, policy_b(), B_SUFFIX)

    strategies = {tier.strategy for tier in policy_b().tiers}
    assert strategies == {CYPHER_V2T + B_SUFFIX, AGENT_V2T + B_SUFFIX}
    assert set(joined.runs) == {tier.name for tier in policy_b().tiers}
