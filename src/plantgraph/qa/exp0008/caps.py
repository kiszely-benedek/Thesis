"""Step caps from the free dry runs and the registered ceilings (review-fixes §6).

Before a paid run the launcher dry-runs it over a copy of the cache, with a fake transport, and
counts the questions that would need a paid call. The run's cap is that count times a cost per
question times 1.5. The step's ceiling (design §6, "Step cap" column) and the ledger bound it again
at the moment the run starts (`ledger.run_cap_usd`).
"""

from __future__ import annotations

import math

SAFETY_FACTOR = 1.5
#: the harness needs a positive cap even when the dry run found every call cached (a pure replay)
MIN_RUN_CAP_USD = 0.01
#: Dollars per question that needs a model call. cyp/ag: the first measurement's R5 figures at
#: 1,000 sheets (`exp0004/e2e_caps.py`), the dearest scale, so they bound every EXP-0008 plant.
#: ctx: ContextRAG high on the small ladder, $2.67 over 236 questions (EXP-0007-R4-ladder.md).
COST_PER_QUESTION_USD = {"cyp": 0.00075, "ag": 0.00189, "ctx": 2.67 / 236}
#: Step ceilings, the "Step cap" column of review-fixes §6 (M6c = d0/d50 $1.34 + C1 $0.10).
STEP_CEILING_USD = {
    "M1": 2.00,
    "M2": 0.05,
    "M5": 4.90,
    "M6a": 10.00,
    "M6b": 6.27,
    "M6c": 1.44,
    "M8a": 0.80,
    "M8b": 7.28,
    "M9": 0.25,
}


def run_cap_usd(n_questions_with_miss: int, tier: str) -> float:
    """Misses x cost per question x 1.5, rounded up to 0.0001 USD, at least `MIN_RUN_CAP_USD`.

    Raises:
        ValueError: an unknown tier.
    """
    if tier not in COST_PER_QUESTION_USD:
        raise ValueError(f"expected a tier in {sorted(COST_PER_QUESTION_USD)}, found {tier!r}")
    raw = n_questions_with_miss * COST_PER_QUESTION_USD[tier] * SAFETY_FACTOR
    return max(MIN_RUN_CAP_USD, math.ceil(raw * 1e4) / 1e4)
