"""Pre-registration part B: the numbers only P1a and P1b supply, written at F10 (design §19.8).

Part A (claims, plants, rules, caps) is committed before the first paid step. Part B records what
tuning and validation measured and what follows from it by rule: the gates G1, G1-B and G1-B2
with their numbers, whether B runs sealed, the tuning log, the replay verdicts, the measured
dollars per question and the E10 hashes. It is plain text; the hash file beside it is the
evidence of its content.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.exp0009.gates import FamilyCells, GateResult


class TuningRound(BaseModel):
    """One B tuning round on D100g22."""

    model_config = ConfigDict(frozen=True)

    number: int
    change: str
    b_dev_accuracy: float
    b_minus_a2_on_r: float


class PartB(BaseModel):
    """Everything part B states, as data."""

    model_config = ConfigDict(frozen=True)

    code_commit: str
    gates: list[GateResult]
    b_sealed: bool
    a2_cells: FamilyCells
    b_cells: FamilyCells
    rounds: list[TuningRound]
    chosen_round: int
    replay_verdicts: dict[str, str]
    #: `arm-tier-scale` -> measured dollars per question
    cost_per_question_usd: dict[str, float]
    sealed_caps_usd: dict[str, float]
    val1000_pool_peak_gib: float | None
    e10_files: int
    e10_sha256_file_sha256: str


def choose_round(rounds: list[TuningRound]) -> TuningRound:
    """The E10 candidate: the highest B dev accuracy, a tie going to the earlier round.

    Raises:
        ValueError: no rounds.
    """
    if not rounds:
        raise ValueError("expected at least one tuning round, found none")
    return max(rounds, key=lambda r: (r.b_dev_accuracy, -r.number))


def _cells_table(cells: FamilyCells) -> str:
    plants = sorted(cells)
    families = sorted({f for c in cells.values() for f in c})
    head = "| family | " + " | ".join(plants) + " |\n|---|" + "---|" * len(plants)
    rows = [
        f"| {f} | " + " | ".join(_cell(cells[p].get(f)) for p in plants) + " |" for f in families
    ]
    return "\n".join([head, *rows])


def _cell(cell: tuple[int, int] | None) -> str:
    return "-" if cell is None else f"{cell[0]}/{cell[1]}"


def render_part_b(part: PartB) -> str:
    """The text of `PREREG_B.md`."""
    gates = "\n".join(
        f"- {g.gate}: **{'PASS' if g.passed else 'FAIL'}**, {g.detail}" for g in part.gates
    )
    rounds = "\n".join(
        f"| {r.number} | {r.change} | {r.b_dev_accuracy:.4f} | {r.b_minus_a2_on_r:+.4f} |"
        for r in part.rounds
    )
    costs = "\n".join(f"| {k} | {v:.6f} |" for k, v in sorted(part.cost_per_question_usd.items()))
    caps = "\n".join(f"| {k} | {v:.2f} |" for k, v in sorted(part.sealed_caps_usd.items()))
    replays = "\n".join(f"- {k}: {v}" for k, v in sorted(part.replay_verdicts.items())) or "- none"
    memory = (
        "not measured"
        if part.val1000_pool_peak_gib is None
        else f"{part.val1000_pool_peak_gib:.2f} GiB"
    )
    sealed = "yes" if part.b_sealed else "no (G1-B or G1-B2 failed: A2 alone runs sealed, ADR-0067)"
    return f"""# EXP-0009 pre-registration, part B (written by the launcher at F10)

Code commit (HEAD when the freeze was written): `{part.code_commit}`

## Validation gates

{gates}

B sealed: **{sealed}**.

A2, correct/total per family:

{_cells_table(part.a2_cells)}

B, correct/total per family:

{_cells_table(part.b_cells)}

## B tuning log (D100g22, at most three rounds)

| round | change | B dev accuracy | B - A2 on R-dev |
|---|---|---|---|
{rounds}

E10 candidate: round {part.chosen_round}.

## Replay verdicts

{replays}

## Measured dollars per question (both tiers of an arm are keyed `arm-tier-scale`)

| key | USD per question |
|---|---|
{costs}

Recomputed sealed caps:

| run | cap USD |
|---|---|
{caps}

Peak memory of the VAL1000g22 question pool: {memory}.

## E10 freeze

`E10.sha256` lists {part.e10_files} files; its own sha256 is `{part.e10_sha256_file_sha256}`.
`B_FILES.sha256` lists every B source file and the cascade policy.
`PREREG.sha256` covers part A, part B, the seeds, the plan, the position prior, the E10 and B hash
files and the judge prompt.
"""
