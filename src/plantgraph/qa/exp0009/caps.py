"""Run caps from question counts, with no dry run (design §19.9, ADR-0068 decision 1).

A cap is the questions in a run's file x the tier's cost per question x 1.5. EXP-0008 counted the
cache misses with a free dry run first; every EXP-0009 stage starts from an empty cache, so the
misses would equal the question count anyway. The ledger (`ledger.py`) then cuts the cap to the
money the step and the program still have.
"""

from __future__ import annotations

import math

from plantgraph.qa.exp0008.caps import MIN_RUN_CAP_USD, RESERVED_QUESTIONS, SAFETY_FACTOR

#: V2T-A2's dollars per question, per tier and nominal scale: EXP-0008's sealed runs, measured
#: with `exp0008.ledger.paid_usd_of_calls` (design §19.9, "per tier, sealed (cost key)").
A2_COST_PER_QUESTION_USD = {
    "cyp-100": 0.000756,
    "ag-100": 0.001588,
    "cyp-1000": 0.000725,
    "ag-1000": 0.001711,
}
#: Assumed until P1a measures it: B's two extra prompt paragraphs and brackets cost this much more.
B_OVERHEAD = 1.10
#: GLM's dev cost ratio to the Luna pins, as a range (CASCADE-V2/V3, BAKEOFF-2; design §20)
GLM_COST_RATIO_LOW, GLM_COST_RATIO_HIGH = 1.2, 1.9
#: step -> ceiling in dollars: 1.5 x the estimate of §19.9 (P1a 1.48, P1b 1.41, P1c 14.06);
#: P1g is the user's GLM comparison arm, whose $2.50 is a hard cap fixed in design §20
STEP_CEILING_USD = {"P1a": 2.22, "P1b": 2.12, "P1c": 21.09, "P1g": 2.50}


def cost_key(tier: str, scale: int) -> str:
    """`cyp-100`, `ag-1000`, ...

    Raises:
        ValueError: an unknown tier or scale.
    """
    key = f"{tier}-{scale}"
    if key not in A2_COST_PER_QUESTION_USD:
        raise ValueError(
            f"expected a cost key in {sorted(A2_COST_PER_QUESTION_USD)}, found {key!r}"
        )
    return key


def cost_per_question_usd(
    tier: str, scale: int, *, arm: str, measured: dict[str, float] | None = None
) -> float:
    """Dollars per question of one arm's tier; `measured` (from P1b, per `arm-tier-scale`) wins.

    The GLM arm has no measurement before it runs: its key is A2's at the top of the cost ratio,
    so that the harness's reservation per question in flight is never too small.

    Raises:
        ValueError: an unknown arm, tier or scale.
    """
    if arm not in ("A2", "B", "GLM"):
        raise ValueError(f"expected arm 'A2', 'B' or 'GLM', found {arm!r}")
    key = cost_key(tier, scale)
    if arm == "GLM":
        return round(A2_COST_PER_QUESTION_USD[key] * GLM_COST_RATIO_HIGH, 6)
    if measured and f"{arm}-{key}" in measured:
        return measured[f"{arm}-{key}"]
    base = A2_COST_PER_QUESTION_USD[key]
    return round(base * B_OVERHEAD, 6) if arm == "B" else base


def run_cap_usd(n_questions: int, cost_per_question: float) -> float:
    """N x cost x 1.5, rounded up to 0.0001; never below the harness's reservation.

    The harness reserves one question's cost per item in flight and refuses a question that could
    reach the cap, so a cap under `RESERVED_QUESTIONS` questions' cost would stop even a replay.

    Raises:
        ValueError: no questions, or a non-positive cost.
    """
    if n_questions < 1 or cost_per_question <= 0:
        raise ValueError(
            f"expected a positive question count and cost, found {n_questions} and "
            f"{cost_per_question}"
        )
    raw = max(
        n_questions * cost_per_question * SAFETY_FACTOR, RESERVED_QUESTIONS * cost_per_question
    )
    return max(MIN_RUN_CAP_USD, math.ceil(raw * 1e4) / 1e4)
