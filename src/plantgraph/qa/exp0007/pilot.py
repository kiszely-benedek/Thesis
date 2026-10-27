"""The pilot's token and dollar correction t_v2 / t_v1 (ADR-0060 point 6; plan section 5).

Ten questions, one per family, are answered on D100g2 by each tier. The same families' mean cost
in the existing v1 dev runs (10 questions per family, F1 prompts and pins) is the baseline.
`R_tier = sum over families of v2 cost / sum over families of v1 mean cost`, once on tokens and once
on dollars; the caps use the larger of the two, never below 1 (a cap must not shrink against v1).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.exp0007.run_costs import QuestionCost, family_means, read_question_costs

#: The ten pilot families (plan section 5): five token-heavy for the agent on v1, three where v2
#: changes the answer's neighbourhood, two light ones.
PILOT_FAMILIES = (
    "UPSTREAM_ISOLATION",
    "CROSS_UNIT",
    "UPSTREAM_SOURCES",
    "LOOPS_NEAR_ITEM",
    "DOWNSTREAM_IN_UNIT",
    "FLOW_PATH",
    "INSTRUMENTS_OF_ITEM",
    "LOOP_MEASURED_EQUIPMENT",
    "LOOKUP_TYPE",
    "SHEETS_OF_TAG",
)
#: v1 dev runs on D100 that carry F1's prompt hashes and the Luna pins (plan section 5).
V1_BASELINE_RUNS = {"cyp": "CYPL2-D100", "ag": "AGL3-D100"}
#: The plan's measured sums of per-family mean tokens over the pilot families; the baseline reader
#: must reproduce them, which proves it reads the same runs the plan measured.
EXPECTED_V1_TOKEN_SUMS = {"cyp": 20_787, "ag": 99_407}
#: The correction that stops the protocol (plan section 8, stop rule 2).
MAX_CORRECTION = 3.0


class TierCorrection(BaseModel):
    """One tier's pilot ratios and the factor the caps use."""

    model_config = ConfigDict(frozen=True)

    tier: str
    tokens_v2: float
    tokens_v1: float
    usd_v2: float
    usd_v1: float
    r_tokens: float
    r_usd: float
    #: max(r_tokens, r_usd, 1.0): what multiplies the v1 cost per question in the caps.
    r: float


def correction_of(
    tier: str, v2_costs: list[QuestionCost], v1_costs: list[QuestionCost]
) -> TierCorrection:
    """The ratios of a tier's pilot cost to the v1 per-family means.

    Raises:
        ValueError: a pilot family has no pilot question or no v1 row.
    """
    v2_by_family = family_means(v2_costs)
    v1_by_family = family_means(v1_costs)
    missing = [f for f in PILOT_FAMILIES if f not in v2_by_family or f not in v1_by_family]
    if missing:
        raise ValueError(f"expected pilot and v1 rows for every pilot family, none for {missing}")
    tokens_v2 = sum(v2_by_family[f][0] for f in PILOT_FAMILIES)
    tokens_v1 = sum(v1_by_family[f][0] for f in PILOT_FAMILIES)
    usd_v2 = sum(v2_by_family[f][1] for f in PILOT_FAMILIES)
    usd_v1 = sum(v1_by_family[f][1] for f in PILOT_FAMILIES)
    r_tokens, r_usd = tokens_v2 / tokens_v1, usd_v2 / usd_v1
    return TierCorrection(
        tier=tier,
        tokens_v2=tokens_v2,
        tokens_v1=tokens_v1,
        usd_v2=usd_v2,
        usd_v1=usd_v1,
        r_tokens=r_tokens,
        r_usd=r_usd,
        r=max(r_tokens, r_usd, 1.0),
    )


def read_v1_baseline(cv1_runs: Path, tier: str) -> list[QuestionCost]:
    """The v1 dev run's costs for a tier, checked against the plan's measured token sum.

    Raises:
        ValueError: the per-family token sum differs from `EXPECTED_V1_TOKEN_SUMS`.
    """
    costs = read_question_costs(cv1_runs / V1_BASELINE_RUNS[tier])
    means = family_means(costs)
    found = round(sum(means[f][0] for f in PILOT_FAMILIES))
    if found != EXPECTED_V1_TOKEN_SUMS[tier]:
        raise ValueError(
            f"expected the v1 {tier} baseline to sum to {EXPECTED_V1_TOKEN_SUMS[tier]} tokens over "
            f"the pilot families (plan section 5), found {found}"
        )
    return costs


def _write_lines(out: Path, lines: list[str]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))  # bytes: LF stays LF on Windows


def filter_questions(source: Path, out: Path, families: list[str]) -> int:
    """Copy the lines of a questions file whose family is in `families`; returns how many.

    Raises:
        ValueError: a family has no question in the source (the pilot needs one of each).
    """
    kept = [
        line
        for line in source.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["family"] in families
    ]
    found = {json.loads(line)["family"] for line in kept}
    if found != set(families):
        missing = sorted(set(families) - found)
        raise ValueError(f"expected a question for every family, found none for {missing}")
    _write_lines(out, kept)
    return len(kept)


def head_questions(source: Path, out: Path, n: int) -> None:
    """The first `n` lines of a questions file: the 2-question smoke of a stage.

    Raises:
        ValueError: the source has fewer than `n` questions.
    """
    lines = source.read_text(encoding="utf-8").splitlines()[:n]
    if len(lines) < n:
        raise ValueError(f"expected at least {n} questions in {source}, found {len(lines)}")
    _write_lines(out, lines)
