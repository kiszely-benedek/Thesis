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
#: The harness reserves one question's cost per item in flight (4 at concurrency 4) and refuses a
#: question that could reach the cap, so a cap below this many questions' cost stops even a replay.
RESERVED_QUESTIONS = 5
#: Dollars per question that needs a model call, by cost key. A key is a tier ("cyp", "ag", "ctx"),
#: optionally followed by "-" and a variant: the identity arm for P4, the plant size for ContextRAG.
#: Plain "cyp" / "ag": R5's figures at 1,000 sheets (`exp0004/e2e_caps.py`), the dearest scale.
#: "cyp-dN" / "ag-dN": the first P4 measurement's real spend per question that needed a call
#: (`EXP-0004-E2E.md`, Spend table): Cypher 0.0741/148, 0.0347/102, 0.0938/83; agent as printed.
#: "ctx-HNg21": ContextRAG high on N sheets, the R4 ladder's $/q (`EXP-0007-R4-ladder.md`); the
#: plain "ctx" is the dearest of them, H10.
COST_PER_QUESTION_USD = {
    "cyp": 0.00075,
    "ag": 0.00189,
    "cyp-d0": round(0.0741 / 148, 6),
    "cyp-d2": round(0.0347 / 102, 6),
    "cyp-d4": round(0.0938 / 83, 6),
    "ag-d0": 0.00195,
    "ag-d2": 0.00266,
    "ag-d4": 0.00431,
    "ctx": 0.02172,
    "ctx-H1g21": 0.00274,
    "ctx-H3g21": 0.00600,
    "ctx-H10g21": 0.02172,
}
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
    """Misses x cost per question x 1.5, rounded up to 0.0001 USD.

    Never below `MIN_RUN_CAP_USD` or the reservations of the questions in flight
    (`RESERVED_QUESTIONS` x the cost per question: with 3 misses and a 0.02 cost, a cap of
    0.09 would stop the run at its fourth in-flight question, found by the smoke on `ag-d2`).

    Raises:
        ValueError: an unknown tier.
    """
    if tier not in COST_PER_QUESTION_USD:
        raise ValueError(f"expected a tier in {sorted(COST_PER_QUESTION_USD)}, found {tier!r}")
    cost = COST_PER_QUESTION_USD[tier]
    raw = max(n_questions_with_miss * cost * SAFETY_FACTOR, RESERVED_QUESTIONS * cost)
    return max(MIN_RUN_CAP_USD, math.ceil(raw * 1e4) / 1e4)
