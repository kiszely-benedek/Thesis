"""Pre-registration part B: the numbers only the first stages supply, written at M3.

Part A (claims, thresholds, design, gates, seeds) is committed before the button. Part B records
what M1 to M2b measured and what follows from it by rule: the G1 verdict, the identity thresholds,
the judge pilot's cost, the audit's capacity, the step caps and the E9 freeze hashes. It is plain
text that the user commits afterwards; the hash file beside it is the evidence of its content.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.audit.budget import (
    HARD_CAP_USD,
    PILOT_CAP_USD,
    WORST_CASE_CALL_USD,
    sizing_cost_per_call,
)
from plantgraph.qa.exp0008.gates import G1Verdict, describe


class PartB(BaseModel):
    """Everything part B states, as data (so it can be tested, then rendered)."""

    model_config = ConfigDict(frozen=True)

    code_commit: str
    g1: G1Verdict
    tau1: float
    tau2: float
    pilot_rows: int
    pilot_mean_call_usd: float
    pilot_spent_usd: float
    g2_defects_found: str
    g2_controls_correct: str
    judge_template_sha256: str
    judge_pin_sha256: str
    step_caps_usd: dict[str, float]
    e9_sha256_file_sha256: str
    e9_files: int


def audit_capacity_calls(pilot_spent_usd: float, pilot_mean_call_usd: float) -> int:
    """How many audit calls the rest of the $10 buys at the pilot's measured cost.

    The sizing cost is the measured mean with the audit's safety factor. If the worst-case call
    alone (the 24,000-character prompt) no longer fits, the capacity is 0.
    """
    left = HARD_CAP_USD - pilot_spent_usd
    if left < WORST_CASE_CALL_USD:
        return 0
    return math.floor(left / sizing_cost_per_call(pilot_mean_call_usd))


def render_part_b(part: PartB) -> str:
    """The text of `PREREG_B.md`."""
    capacity = audit_capacity_calls(part.pilot_spent_usd, part.pilot_mean_call_usd)
    sizing = sizing_cost_per_call(part.pilot_mean_call_usd)
    caps = "\n".join(f"| {step} | {cap:.2f} |" for step, cap in part.step_caps_usd.items())
    return f"""# EXP-0008 pre-registration, part B (written by the launcher at M3)

Code commit (HEAD when the freeze was written): `{part.code_commit}`

## Gate G1 (re-validation of V2T-A2)

Result: **{"PASS" if part.g1.passed else "FAIL"}**. {describe(part.g1)}.

## Identity thresholds (EXP-0004 M2, exact scores)

tau1 = {part.tau1!r}, tau2 = {part.tau2!r}.

## Judge pilot (gate G2) and the audit's size

- Pilot rows judged: {part.pilot_rows}.
- Known defects judged correct or ambiguous: {part.g2_defects_found}; controls judged correct:
  {part.g2_controls_correct}.
- Measured mean cost per call: ${part.pilot_mean_call_usd:.5f}.
- Spent by the pilot: ${part.pilot_spent_usd:.4f} (pilot cap ${PILOT_CAP_USD:.2f}).
- Sizing cost per call (mean x safety factor): ${sizing:.5f}.
- Audit capacity under the ${HARD_CAP_USD:.0f} hard cap: {capacity} calls, in the registered order
  (every wrong row, then the random right sample of at least 2 per family per scale, then ContextRAG
  wrong rows, then more right samples); the runner stops at the cap.
- Judge prompt sha256: `{part.judge_template_sha256}`; judge pin sha256: `{part.judge_pin_sha256}`.

## Step caps (USD, ceilings; each run's own cap comes from its free dry run and the ledger)

| step | cap |
|---|---|
{caps}

## E9 freeze

`E9.sha256` lists {part.e9_files} files; its own sha256 is `{part.e9_sha256_file_sha256}`.
`PREREG.sha256` covers part A, part B, the seeds, `E9.commit`, `E9.sha256` and the judge prompt.
"""
