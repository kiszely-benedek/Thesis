"""The cascade policy of the B arm, `cascade_v4_iso_b`: V2T-A2's `cascade_v4_iso`, renamed.

Same two tiers, same pins, same acceptance rules and the same start tier by need label. The design
says "VALVE_SET is treated as TAG_SET in the escalation rule"; in the code that holds by
construction, because no acceptance rule reads the answer type (`cascade/accept.py` reads the
outcome, the abstention flag, the row count and the truncation flag). The policy is therefore
derived from A's file, so the two cannot drift, and a test pins the equality.

One thing does differ: the frozen offline evaluation finds a tier's rows by the tier's strategy
name (`cascade/checks.py`), and a B run writes `cypher_rag_lines_b` and `graph_agent_lines_b`. So
each tier names the B strategy; tier names, pins and rules are A's.
"""

from __future__ import annotations

from functools import cache

from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policy
from plantgraph.qa.v2tb.answer_b import B_SUFFIX

A_POLICY_NAME = "cascade_v4_iso"
B_POLICY_NAME = "cascade_v4_iso_b"


@cache
def policy_b() -> CascadePolicy:
    """`cascade_v4_iso` under the name `cascade_v4_iso_b`, its tiers reading the B strategies."""
    policy_a = load_policy(V2T_POLICIES_DIR / f"{A_POLICY_NAME}.json")
    tiers = tuple(
        tier.model_copy(update={"strategy": tier.strategy + B_SUFFIX}) for tier in policy_a.tiers
    )
    return policy_a.model_copy(update={"name": B_POLICY_NAME, "tiers": tiers})
