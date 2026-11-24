"""Stage arithmetic of the launcher: run ids, cost estimates, tuning-round rules (§19.7, §19.9).

Pure functions, so every decision the shell scripts need has a test. The shell only sequences.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from plantgraph.qa.exp0009 import caps, ledger

#: Dollars per question over both tiers, the basis of §19.9's estimate table: EXP-0008's validation
#: runs (0.00213) and its sealed runs per scale (0.00234 at 100 sheets, 0.00244 at 1,000).
ESTIMATE_PER_QUESTION_USD = {"dev": 0.00213, "100": 0.00234, "1000": 0.00244}
#: §19.6's derived counts: questions per run on a dev/validation plant and on a sealed plant
DEV_COUNTS = {"A2": 153, "B": 163}
SEALED_COUNTS = {"A2": 275, "B": 285}
MAX_ROUNDS = 3
MIN_GAIN_POINTS = 1.0  # from round 2, a round must add this many points of B dev accuracy


@dataclass(frozen=True)
class RunGroup:
    """Runs of one kind in a stage: how many, how many questions each, at which cost basis."""

    label: str
    arm: str
    n_runs: int
    n_questions: int
    basis: str  # a key of ESTIMATE_PER_QUESTION_USD

    @property
    def estimate_usd(self) -> float:
        """Questions x runs x dollars per question (B at A2's x 1.10, until measured)."""
        rate = ESTIMATE_PER_QUESTION_USD[self.basis] * (caps.B_OVERHEAD if self.arm == "B" else 1)
        return self.n_runs * self.n_questions * rate


def stage_groups(stage: str, counts: Mapping[str, int] | None = None) -> list[RunGroup]:
    """The run groups of a paid stage; `counts` overrides the derived question counts.

    Raises:
        ValueError: an unknown stage.
    """
    dev = {**DEV_COUNTS, **(counts or {})}
    sealed = {**SEALED_COUNTS, **(counts or {})}
    if stage == "P1a":
        return [
            RunGroup("A2 baseline, D100g22", "A2", 1, dev["A2"], "dev"),
            RunGroup("B rounds, D100g22B (at most 3)", "B", MAX_ROUNDS, dev["B"], "dev"),
        ]
    if stage == "P1b":
        return [
            RunGroup("A2 validation pair", "A2", 2, dev["A2"], "dev"),
            RunGroup("B validation pair", "B", 2, dev["B"], "dev"),
        ]
    if stage == "P1c":
        return [
            RunGroup(f"{arm} sealed, {scale}-sheet plants", arm, 5, sealed[arm], str(scale))
            for arm in ("A2", "B")
            for scale in (100, 1000)
        ]
    raise ValueError(f"expected a paid stage P1a, P1b or P1c, found {stage!r}")


def render_estimate(
    stage: str, root: Path, counts: Mapping[str, int] | None = None, balance: str = "not read"
) -> str:
    """The event NOTE printed before a paid stage: questions, keys, estimate, ceiling, ledgers."""
    groups = stage_groups(stage, counts)
    total = sum(g.estimate_usd for g in groups)
    ceiling = caps.STEP_CEILING_USD[stage]
    rows = [
        f"{g.label}: {g.n_runs} run(s) x {g.n_questions} q, key {g.basis}, ${g.estimate_usd:.2f}"
        for g in groups
    ]
    return (
        f"estimate {stage}: " + "; ".join(rows) + f"; total ${total:.2f}, step ceiling "
        f"${ceiling:.2f}; ledger {ledger.summary(root)}; balance {balance}"
    )


# ---- P1c's projection from P1b's measured costs (F1) -----------------------------------------

#: What the GLM comparison arm (P1g) may still need from the runs ledger after P1c.
GLM_RESERVE_USD = caps.STEP_CEILING_USD["P1g"]
SEALED_PLANTS_PER_SCALE = 5


@dataclass(frozen=True)
class SealedProjection:
    """P1c's expected spend from the measured costs, and each run's recomputed cap."""

    #: `arm-tier-scale` -> the cap of one sealed run (questions x measured cost x 1.5)
    run_caps_usd: dict[str, float]
    #: the expected spend of all ten plants: questions x measured cost, no safety factor
    projected_usd: float


def project_p1c(measured: dict[str, float] | None, b_sealed: bool) -> SealedProjection:
    """P1c's expected spend and per-run caps, from `measured` dollars per question (P1b)."""
    arms = ("A2", "B") if b_sealed else ("A2",)
    run_caps: dict[str, float] = {}
    projected = 0.0
    for arm in arms:
        for scale in (100, 1000):
            for tier in ("cyp", "ag"):
                cost = caps.cost_per_question_usd(tier, scale, arm=arm, measured=measured)
                run_caps[f"{arm}-{tier}-{scale}"] = caps.run_cap_usd(SEALED_COUNTS[arm], cost)
                projected += SEALED_PLANTS_PER_SCALE * SEALED_COUNTS[arm] * cost
    return SealedProjection(run_caps_usd=run_caps, projected_usd=round(projected, 4))


def p1c_projection_problems(
    projection: SealedProjection, runs_left_usd: float, ceiling_usd: float | None = None
) -> list[str]:
    """Why P1c's projected spend does not fit the step ceiling or the ledger left."""
    ceiling = caps.STEP_CEILING_USD["P1c"] if ceiling_usd is None else ceiling_usd
    problems = []
    if projection.projected_usd > ceiling:
        problems.append(
            f"projected P1c spend ${projection.projected_usd:.2f} exceeds the step ceiling "
            f"${ceiling:.2f}"
        )
    room = runs_left_usd - GLM_RESERVE_USD
    if projection.projected_usd > room:
        problems.append(
            f"projected P1c spend ${projection.projected_usd:.2f} exceeds what the runs ledger "
            f"leaves (${runs_left_usd:.2f}) less the ${GLM_RESERVE_USD:.2f} GLM reserve"
        )
    return problems


# ---- the tuning rounds (P1a) ------------------------------------------------------------------


def next_round_allowed(accuracies: Sequence[float]) -> tuple[bool, str]:
    """May another B tuning round start, given the B dev accuracy of each finished round?

    A round from round 2 on that adds less than one point ends tuning; round 3 always ends it, so
    a fourth is refused. Accuracies are shares (0.80), the gain is in points.
    """
    if not accuracies:
        return False, "no round has run yet"
    if len(accuracies) >= MAX_ROUNDS:
        return False, f"round {MAX_ROUNDS} always ends tuning"
    if len(accuracies) >= 2 and (accuracies[-1] - accuracies[-2]) * 100 < MIN_GAIN_POINTS:
        return False, "the last round added less than 1 point"
    return True, "tuning may continue"


def require_new_b_code(hashes_by_round: Mapping[int, str], candidate: str) -> None:
    """Refuse a round whose `b_code.sha256` equals an earlier round's.

    Raises:
        ValueError: names the earlier round.
    """
    for number, digest in sorted(hashes_by_round.items()):
        if digest == candidate:
            raise ValueError(f"expected changed B files for the new round, found round {number}'s")


def run_id(prefix: str, plant: str, tier: str | None = None, round_no: int | None = None) -> str:
    """`U9-1-CYP-D100g22B`, `V9-AG-VAL100g22`, `S9-CYP-H100g22p1B` and the like."""
    middle = "-".join(str(x) for x in (round_no, tier) if x is not None)
    return f"{prefix}-{middle}-{plant}" if middle else f"{prefix}-{plant}"
