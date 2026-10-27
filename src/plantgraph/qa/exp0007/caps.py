"""Spend caps of the paid stages: the formula and the verified cap file (ADR-0060 point 7).

Formula: `cap = ceil to 0.05 of (1.3 x n x c)`, with `n` the questions of the run and `c` the
corrected cost per question (v1 cost per question times the pilot's correction factor). The values
are written to a JSON cap file whose sha256 the user sees before the stage; a paid script refuses
to start unless it is given that file **and** the sha256 it was shown, so a cap cannot change
between approval and the first call.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict

#: Caps are rounded up to the next 5 cents, with 30 % headroom over the estimate.
CAP_STEP_USD = 0.05
SAFETY_FACTOR = 1.3


class CapEntry(BaseModel):
    """The cap of one run and how it was computed."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    tier: str
    n_questions: int
    #: Mean cost per question of the v1 baseline run(s), before the correction.
    v1_cost_per_question_usd: float
    #: The pilot's correction factor for the tier (1.0 when none applies).
    correction: float
    #: c in the formula; also what the harness reserves per question in flight.
    cost_per_question_usd: float
    cap_usd: float
    basis: str


class CapFile(BaseModel):
    """All caps of one stage."""

    model_config = ConfigDict(frozen=True)

    stage: str
    entries: list[CapEntry]

    @property
    def total_usd(self) -> float:
        """The sum of the stage's caps: what the OpenRouter balance must cover."""
        return round(sum(e.cap_usd for e in self.entries), 2)


def cap_usd(n_questions: int, cost_per_question_usd: float) -> float:
    """`ceil_0.05(1.3 * n * c)`, at least one step.

    Raises:
        ValueError: `n_questions` below 1 or a negative cost.
    """
    if n_questions < 1 or cost_per_question_usd < 0:
        raise ValueError(
            f"expected n >= 1 and cost >= 0, found n={n_questions}, cost={cost_per_question_usd}"
        )
    steps = math.ceil(round(SAFETY_FACTOR * n_questions * cost_per_question_usd / CAP_STEP_USD, 9))
    return round(max(steps, 1) * CAP_STEP_USD, 2)


def make_entry(
    run_id: str,
    tier: str,
    n_questions: int,
    v1_cost: float,
    correction: float,
    floor_cost: float | None = None,
) -> CapEntry:
    """One entry; `floor_cost` (a measured v2 cost per question) wins when it is larger."""
    corrected = v1_cost * correction
    cost = max(corrected, floor_cost) if floor_cost is not None else corrected
    basis = f"v1 {v1_cost:.6f} x {correction:.3f}"
    if floor_cost is not None and floor_cost > corrected:
        basis = f"measured v2 {floor_cost:.6f} (above {basis})"
    return CapEntry(
        run_id=run_id,
        tier=tier,
        n_questions=n_questions,
        v1_cost_per_question_usd=v1_cost,
        correction=correction,
        cost_per_question_usd=cost,
        cap_usd=cap_usd(n_questions, cost),
        basis=basis,
    )


def write_cap_file(path: Path, caps: CapFile) -> str:
    """Write the cap file and return its sha256.

    Raises:
        FileExistsError: the file exists (a written cap file is never replaced).
    """
    if path.exists():
        raise FileExistsError(f"expected no cap file at {path}, found one: never overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((caps.model_dump_json(indent=2) + "\n").encode("utf-8"))
    return sha256_of(path)


def sha256_of(path: Path) -> str:
    """Sha256 hex digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified(path: Path, expected_sha256: str) -> CapFile:
    """The cap file, if it exists and hashes to what the user was shown.

    Raises:
        FileNotFoundError: the file is missing.
        ValueError: its sha256 differs from `expected_sha256`.
    """
    if not path.exists():
        raise FileNotFoundError(f"expected a cap file at {path}, found none")
    found = sha256_of(path)
    if found != expected_sha256:
        raise ValueError(f"expected cap file {path} to hash to {expected_sha256}, found {found}")
    return CapFile.model_validate_json(path.read_text(encoding="utf-8"))


def entry_for(caps: CapFile, run_id: str) -> CapEntry:
    """The entry of `run_id`.

    Raises:
        KeyError: the stage has no cap for that run.
    """
    for entry in caps.entries:
        if entry.run_id == run_id:
            return entry
    raise KeyError(f"expected a cap for run {run_id!r}, found {[e.run_id for e in caps.entries]}")
