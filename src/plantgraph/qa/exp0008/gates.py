"""Gate G1 (re-validation of V2T-A2) as a pure function over two plants' reports (review-fixes §5).

G1 passes if, on both validation plants, cascade_v4_iso scores at least as many correct answers as
F1's cascade_v3, and no dev family is below 50 % on both plants at once. The evidence is read from
the reports the first measurement's tools already write: `tune-report` (V2T) and `dev-report` (F1).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

#: a family is "weak" on a plant when its accuracy is below this share
WEAK_FAMILY_SHARE = 0.5
V2T_POLICY = "cascade_v4_iso"


class PlantEvidence(BaseModel):
    """What G1 needs from one validation plant."""

    model_config = ConfigDict(frozen=True)

    plant: str
    n_questions: int
    v2t_correct: int
    f1_correct: int
    #: family -> (correct, total) for cascade_v4_iso
    v2t_by_family: dict[str, tuple[int, int]]


class G1Verdict(BaseModel):
    """The gate's outcome and the numbers behind it, for pre-registration part B."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    plants: list[PlantEvidence]
    plants_where_v2t_below_f1: list[str]
    families_weak_on_every_plant: list[str]


def read_evidence(plant: str, tune_report: Path, dev_report: Path) -> PlantEvidence:
    """Evidence of one plant from its V2T `tune_report.json` and F1 `dev_report.json`.

    Raises:
        ValueError: a report lacks the policy or the rows G1 reads.
    """
    tune = json.loads(tune_report.read_text(encoding="utf-8"))
    f1 = json.loads(dev_report.read_text(encoding="utf-8"))
    try:
        policy = tune["results"][V2T_POLICY]
        families = {k: (v["correct"], v["total"]) for k, v in policy["by_family"].items()}
        return PlantEvidence(
            plant=plant,
            n_questions=int(tune["n_questions"]),
            v2t_correct=int(policy["n_correct_in_limit"]),
            f1_correct=sum(int(row["cascade_correct"]) for row in f1["rows"]),
            v2t_by_family=families,
        )
    except (KeyError, TypeError) as error:
        raise ValueError(
            f"expected {V2T_POLICY} by_family in {tune_report} and rows in {dev_report}, "
            f"found a missing key {error}"
        ) from error


def _weak(evidence: PlantEvidence) -> set[str]:
    return {
        family
        for family, (correct, total) in evidence.v2t_by_family.items()
        if total and correct / total < WEAK_FAMILY_SHARE
    }


def g1_verdict(plants: list[PlantEvidence]) -> G1Verdict:
    """Apply the two G1 rules.

    Raises:
        ValueError: fewer than two plants (the gate is defined on both validation plants).
    """
    if len(plants) < 2:
        raise ValueError(f"expected both validation plants, found {len(plants)}")
    below = [p.plant for p in plants if p.v2t_correct < p.f1_correct]
    weak_everywhere = sorted(set.intersection(*(_weak(p) for p in plants)))
    return G1Verdict(
        passed=not below and not weak_everywhere,
        plants=plants,
        plants_where_v2t_below_f1=below,
        families_weak_on_every_plant=weak_everywhere,
    )


def describe(verdict: G1Verdict) -> str:
    """One line for the log: the counts per plant and why it failed, if it did."""
    counts = "; ".join(
        f"{p.plant}: v4_iso {p.v2t_correct} vs v3 {p.f1_correct} of {p.n_questions}"
        for p in verdict.plants
    )
    why = ""
    if verdict.plants_where_v2t_below_f1:
        why += f"; below F1 on {verdict.plants_where_v2t_below_f1}"
    if verdict.families_weak_on_every_plant:
        why += f"; below 50% on every plant: {verdict.families_weak_on_every_plant}"
    return counts + why
