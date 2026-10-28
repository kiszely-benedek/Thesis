"""The V2T tuning protocol as data: which plants, which run ids and which spend caps.

Protocol (design `qa-tuning-v2.md` 7, ADR-0061): the tuning plant T is tuned on for up to three
rounds; the validation plants V are held back and run once at the end. Each round runs the agent
tier once and the Cypher tier twice, once per limit setting (A: 30 s timeout, B: 120 s).
Caps are `cap_usd(n, c)` of `caps.py`; the two cap files here are written once and hashed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.ingest.headline_v2 import TEST_SEED_RANGE
from plantgraph.qa.exp0007.caps import CapEntry, CapFile, cap_usd

#: Measured on D100g2 with F1 (the dev check): dollars per question, harness mean.
MEASURED_CYPHER_USD = 0.000475
MEASURED_AGENT_USD = 0.000866
#: V2T's upper estimate (design 7.5): Cypher adds a repair call to every question; the agent's
#: truncated questions cost 4x as much. Caps use this, so a costlier V2T does not stop at its cap.
HIGH_CYPHER_USD = 0.00086
HIGH_AGENT_USD = 0.0025
#: The larger plant is priced 10 % above its per-question estimate (design 7.5).
LARGE_PLANT_MARGIN = 1.1
SMOKE_QUESTIONS = 2
SMOKE_CAP_USD = 0.02
MAX_ROUNDS = 3

ARMS = ("AG", "CYP-A", "CYP-B")  # agent; Cypher at setting A; Cypher at setting B


class TuneCorpus(BaseModel):
    """One plant of the protocol."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    sheets: int
    seed: int
    role: Literal["tuning", "validation"]


TUNING_PLANT = TuneCorpus(corpus_id="X100g2s211", sheets=100, seed=211, role="tuning")
VALIDATION_PLANTS = (
    TuneCorpus(corpus_id="X100g2s212", sheets=100, seed=212, role="validation"),
    TuneCorpus(corpus_id="X1000g2s213", sheets=1000, seed=213, role="validation"),
)


def require_corpus(corpus_id: str, final_v: bool) -> TuneCorpus:
    """The plant of this protocol named `corpus_id`; V plants only with `final_v`.

    Raises:
        ValueError: an unknown id, a validation plant without `final_v`, or a test-range seed.
    """
    known = {c.corpus_id: c for c in (TUNING_PLANT, *VALIDATION_PLANTS)}
    if corpus_id not in known:
        raise ValueError(f"expected one of {sorted(known)}, found {corpus_id!r}")
    corpus = known[corpus_id]
    if corpus.seed in TEST_SEED_RANGE:
        raise ValueError(f"expected a non-test seed, found {corpus.seed} (test range is reserved)")
    if corpus.role == "validation" and not final_v:
        raise ValueError(f"{corpus_id} is held back for the final step: pass --final-v")
    return corpus


def tuning_run_id(round_no: int, arm: str, corpus_id: str) -> str:
    """Run id of one tuning run, e.g. `T7R2-CYP-A-X100g2s211`."""
    return f"T7R{round_no}-{arm}-{corpus_id}"


def smoke_run_id(arm: str, corpus_id: str) -> str:
    """Run id of the two-question smoke that precedes round 1."""
    return f"T7S-{arm}-{corpus_id}"


def final_run_id(arm: str, corpus_id: str) -> str:
    """Run id of a V2T run on a validation plant."""
    return f"V7-{arm}-{corpus_id}"


def f1_run_id(arm: str, corpus_id: str) -> str:
    """Run id of an F1 run on a validation plant (arm `AG` or `CYP`)."""
    return f"V7F1-{arm}-{corpus_id}"


def _entry(run_id: str, arm: str, n: int, measured: float, high: float, margin: float) -> CapEntry:
    cost = high * margin
    return CapEntry(
        run_id=run_id,
        tier="ag" if arm == "AG" else "cyp",
        n_questions=n,
        v1_cost_per_question_usd=measured,
        correction=high / measured,
        cost_per_question_usd=cost,
        cap_usd=cap_usd(n, cost),
        basis=f"1.3 x {n} x {cost:.6f} (measured F1 {measured:.6f}, upper estimate {high:.6f}"
        + (f", x{margin} large plant)" if margin != 1.0 else ")"),
    )


def _v2t_arm_entry(run_id: str, arm: str, n: int, margin: float = 1.0) -> CapEntry:
    if arm == "AG":
        return _entry(run_id, arm, n, MEASURED_AGENT_USD, HIGH_AGENT_USD, margin)
    return _entry(run_id, arm, n, MEASURED_CYPHER_USD, HIGH_CYPHER_USD, margin)


def tuning_caps(n_questions: int, rounds: int = MAX_ROUNDS) -> CapFile:
    """Caps of every run the tuning rounds may make on T, plus round 1's two smokes."""
    plant = TUNING_PLANT.corpus_id
    entries = [
        _v2t_arm_entry(smoke_run_id(arm, plant), arm, SMOKE_QUESTIONS).model_copy(
            update={"cap_usd": SMOKE_CAP_USD}
        )
        for arm in ("AG", "CYP-A")
    ]
    for round_no in range(1, rounds + 1):
        entries += [
            _v2t_arm_entry(tuning_run_id(round_no, arm, plant), arm, n_questions) for arm in ARMS
        ]
    return CapFile(stage="tune", entries=entries)


def final_caps(questions: dict[str, int]) -> CapFile:
    """Caps of the final step: V2T (three runs) and F1 (two runs) on each validation plant.

    Args:
        questions: validation plant id -> number of questions drawn for it.
    """
    entries: list[CapEntry] = []
    for plant in VALIDATION_PLANTS:
        n = questions[plant.corpus_id]
        margin = LARGE_PLANT_MARGIN if plant.sheets >= 1000 else 1.0
        entries += [
            _v2t_arm_entry(final_run_id(arm, plant.corpus_id), arm, n, margin) for arm in ARMS
        ]
        entries += [
            _entry(
                f1_run_id("AG", plant.corpus_id),
                "AG",
                n,
                MEASURED_AGENT_USD,
                MEASURED_AGENT_USD,
                margin,
            ),
            _entry(
                f1_run_id("CYP", plant.corpus_id),
                "CYP",
                n,
                MEASURED_CYPHER_USD,
                MEASURED_CYPHER_USD,
                margin,
            ),
        ]
    return CapFile(stage="final-v", entries=entries)


def round_total_usd(caps: CapFile, round_no: int) -> float:
    """Sum of the caps of one round (round 1 also counts the smokes)."""
    wanted = (f"T7R{round_no}-", "T7S-") if round_no == 1 else (f"T7R{round_no}-",)
    return round(sum(e.cap_usd for e in caps.entries if e.run_id.startswith(wanted)), 2)
