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
