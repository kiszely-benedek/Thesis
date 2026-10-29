"""The sealed test's pre-registered claims: constants and the pure rules that judge them.

Design `sealed-test-run.md` section 9 fixed the wording before any test answer existed. This
file is part of the F1 freeze: change a constant or a rule after F1 and the test numbers
become post hoc (design section 10, item 5). Each rule takes numbers and returns a `Verdict`;
none of them reads a file or a run.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.evaluate import LatencyBound
from plantgraph.qa.cascade.report_models import Verdict
from plantgraph.qa.cascade.stats import Interval
from plantgraph.qa.models import QuestionFamily


class ClaimPolicies(BaseModel):
    """Which policy each sealed claim is about (names as in the policy files)."""

    model_config = ConfigDict(frozen=True)

    #: The policy under test: the single primary claim (Q4) is about this one.
    primary: str
    #: K1's comparator (always send the question to the agent tier) and Q5's typed-API arm.
    tier2_comparator: str
    #: Q5's free-form-Cypher arm ("Cypher alone").
    cypher_comparator: str
    #: K2's policy: the one whose random-escalation reference is used. A policy routed by need
    #: label has no such reference (`report_references._has_references`), so V2T names its
    #: unrouted sibling here.
    random_reference: str


#: The frozen F1 system (sealed on v1, ADR-0053).
F1_CLAIMS = ClaimPolicies(
    primary="cascade_v3",
    tier2_comparator="always_g_luna",
    cypher_comparator="always_c_luna",
    random_reference="cascade_v3",
)
#: The tuned V2T system (ADR-0061); its reference policies are in `policies_v2t/references/`.
V2T_CLAIMS = ClaimPolicies(
    primary="cascade_v4_iso",
    tier2_comparator="always_g_v2t",
    cypher_comparator="always_c_v2t",
    random_reference="cascade_v4",
)
CLAIM_PRESETS = {"f1": F1_CLAIMS, "v2t": V2T_CLAIMS}
#: Kept for callers that mean the F1 system.
PRIMARY_POLICY = F1_CLAIMS.primary

#: ADR-0044 U2: this family is left out of every headline figure.
HEADLINE_EXCLUDED_FAMILY = QuestionFamily.LOOP_ACTUATED_VALVE

#: Names in `splits.json`, in display order.
SPLIT_DEV_OLD = "dev-old"
SPLIT_DEV_NEW = "dev-new"
SPLIT_HELD_OUT = "held-out"
SPLIT_HELD_OUT_WORDING = "held-out-wording"
SPLIT_ORDER = (SPLIT_DEV_OLD, SPLIT_DEV_NEW, SPLIT_HELD_OUT, SPLIT_HELD_OUT_WORDING)
#: The headline set is the union of these splits (wordings are a separate, should-tier table).
HEADLINE_SPLITS = (SPLIT_DEV_OLD, SPLIT_DEV_NEW, SPLIT_HELD_OUT)
#: The generalisation gap is dev minus held-out.
DEV_SPLITS = (SPLIT_DEV_OLD, SPLIT_DEV_NEW)

#: Q4: cost elasticity must stay below this ("cost grows less than half as fast as the plant").
MAX_COST_ELASTICITY = 0.5

#: Claims whose arms were dropped before the test; reported as such, never judged.
NOT_RUN_CLAIMS = {
    "Q1": "need-aware Hierarchical was dropped (ADR-0047, ADR-0048)",
    "Q2": "need-aware Hierarchical was dropped (ADR-0047, ADR-0048)",
    "Q3": "hier_agent was dropped (ADR-0047)",
}


def cost_elasticity(
    cost_small: float, cost_large: float, sheets_small: int, sheets_large: int
) -> float:
    """E = ln(cost_large / cost_small) / ln(sheets_large / sheets_small).

    Doubling the cost while the plant grows tenfold gives e = ln 2 / ln 10 = 0.301.

    Raises:
        ValueError: a cost is not positive, or the two sheet counts are not increasing.
    """
    if cost_small <= 0 or cost_large <= 0:
        raise ValueError(f"expected positive costs, found {cost_small} and {cost_large}")
    if not 0 < sheets_small < sheets_large:
        raise ValueError(f"expected 0 < small < large sheets, found {sheets_small}, {sheets_large}")
    return math.log(cost_large / cost_small) / math.log(sheets_large / sheets_small)


def _interval_text(interval: Interval, fmt: str) -> str:
    return f"{interval.estimate:{fmt}} [{interval.ci_low:{fmt}}, {interval.ci_high:{fmt}}]"


def _no_loss(difference: Interval) -> bool:
    """The interval contains 0 or lies above it: no accuracy loss can be shown."""
    return difference.ci_high >= 0


def _clearly_lower(difference: Interval) -> bool:
    """The interval excludes 0 and lies below it."""
    return difference.ci_high < 0


def _ok(flag: bool) -> str:
    return "ok" if flag else "not met"


def _verdict(
    rule: str, scope: str, passed: bool, failures: list[str], details: list[str]
) -> Verdict:
    """PASS reads "supported"; FAIL reads the pre-registered wording of what failed."""
    headline = f"{rule} [{scope}]: " + ("supported" if passed else "; ".join(failures))
    return Verdict(
        rule=rule, status="PASS" if passed else "FAIL", headline=headline, details=details
    )


def judge_scale_claim(
    policy: str,
    scope: str,
    accuracy_diff: Interval,
    elasticity: Interval,
    primary: str = PRIMARY_POLICY,
) -> Verdict:
    """Q4 (primary for the `primary` policy) and Q4': accuracy and cost hold from small to large."""
    rule = "Q4 (primary)" if policy == primary else "Q4'"
    accuracy_ok = _no_loss(accuracy_diff)
    cost_ok = elasticity.estimate < MAX_COST_ELASTICITY
    failures = []
    if not accuracy_ok:
        failures.append("accuracy falls with scale")
    if not cost_ok:
        failures.append("cost grows near-linearly with the plant")
    details = [
        f"acc@C large minus small {_interval_text(accuracy_diff, '+.3f')} "
        f"(needs the interval to contain 0 or lie above): {_ok(accuracy_ok)}",
        f"cost elasticity {_interval_text(elasticity, '.3f')} "
        f"(needs < {MAX_COST_ELASTICITY}): {_ok(cost_ok)}",
    ]
    return _verdict(f"{rule} {policy}", scope, accuracy_ok and cost_ok, failures, details)


def judge_k1(scope: str, accuracy: Interval, cost: Interval, latency: Interval) -> Verdict:
    """K1: the cascade minus always-agent. No accuracy loss, and cost and latency clearly lower."""
    accuracy_ok = _no_loss(accuracy)
    cost_ok, latency_ok = _clearly_lower(cost), _clearly_lower(latency)
    failures = []
    if not accuracy_ok:
        failures.append("the cascade loses accuracy")
    if not (cost_ok and latency_ok):
        failures.append("the cascade saves nothing")
    details = [
        f"acc@C {_interval_text(accuracy, '+.3f')}: {_ok(accuracy_ok)}",
        f"$/question {_interval_text(cost, '+.5f')} (needs CI below 0): {_ok(cost_ok)}",
        f"latency s/question {_interval_text(latency, '+.2f')} (needs CI below 0): "
        f"{_ok(latency_ok)}",
    ]
    return _verdict("K1", scope, accuracy_ok and cost_ok and latency_ok, failures, details)


def judge_k2(scope: str, versus_random: Interval | None) -> Verdict:
    """K2: the cascade minus random escalation at the same tier-2 share; CI must exclude 0 above."""
    if versus_random is None:
        return Verdict(
            rule="K2", status="INCOMPLETE", headline=f"K2 [{scope}]: no random-escalation reference"
        )
    passed = versus_random.ci_low > 0
    details = [f"acc@C {_interval_text(versus_random, '+.3f')} (needs CI above 0)"]
    return _verdict("K2", scope, passed, ["the self-flags route no better than chance"], details)


def judge_k3(scope: str, bound: LatencyBound, median: Interval, p90: Interval) -> Verdict:
    """K3: LB-1 and LB-2 hold on the claims corpus (point estimates; the CIs are reported)."""
    median_ok = median.estimate <= bound.median_max_s
    p90_ok = p90.estimate <= bound.p90_max_s
    details = [
        f"median {_interval_text(median, '.1f')} s (limit {bound.median_max_s:g}): "
        f"{_ok(median_ok)}",
        f"p90 {_interval_text(p90, '.1f')} s (limit {bound.p90_max_s:g}): {_ok(p90_ok)}",
    ]
    failures = ["the cascade is not fast enough at plant scale"]
    return _verdict("K3", scope, median_ok and p90_ok, failures, details)


def judge_q5(scope: str, typed_minus_cypher: Interval) -> Verdict:
    """Q5: the typed plant API beats free-form Cypher; the CI must exclude 0 above."""
    passed = typed_minus_cypher.ci_low > 0
    details = [f"acc@C {_interval_text(typed_minus_cypher, '+.3f')} (needs CI above 0)"]
    if typed_minus_cypher.ci_high < 0:
        details.append("the whole interval is below 0: free-form Cypher is the better arm")
    failures = ["free-form Cypher matches the typed API"]
    return _verdict("Q5", scope, passed, failures, details)


def not_run_verdicts() -> list[Verdict]:
    """Q1-Q3 as `NOT_RUN` lines, each with the reason its arm is gone."""
    return [
        Verdict(rule=name, status="NOT_RUN", headline=f"{name}: not run - {reason}")
        for name, reason in NOT_RUN_CLAIMS.items()
    ]
