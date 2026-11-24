"""The data effect: V2T-A2 on v2.2 plants minus V2T-A2 on EXP-0008's v2.1 plants (descriptive).

The same frozen system answers two generations of the plant generator. v2.2 adds handbook rules,
header networks and untagged valves, so the difference isolates what the **data** changed. It is
measured on the question families both experiments share, per scale, and it is unpaired (the
questions differ), with the two-stage cluster bootstrap of the other claims.

EXP-0008's sealed runs (`m6a/runs/S7-*-H<scale>g21p<k>`) are read as saved; nothing is re-run.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from plantgraph.qa.cascade.evaluate import Evaluation
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policies
from plantgraph.qa.cascade.stats import Interval
from plantgraph.qa.cascade.stats_cluster import cluster_unpaired_bootstrap
from plantgraph.qa.exp0009.analysis_claims import SCALE_LABELS
from plantgraph.qa.exp0009.analysis_load import (
    A2_PRIMARY,
    ArmRuns,
    FinderFactory,
    PlantData,
    load_arm,
    read_question_files,
)
from plantgraph.qa.exp0009.analysis_models import ClaimRow, ClaimStatus
from plantgraph.qa.exp0009.analysis_scope import r_headline_ids
from plantgraph.qa.models import Question, QuestionFamily

EXP0008_RUNS = Path("m6a") / "runs"
EXP0008_PLANT = re.compile(r"H(100|1000)g21p([1-5])")
RULE = "descriptive: unpaired, the same two-stage bootstrap, shared families only"


@dataclass(frozen=True)
class V21Plant:
    """One EXP-0008 sealed plant with V2T-A2's cascade evaluated on it."""

    plant_id: str
    scale: int
    questions: tuple[Question, ...]
    headline: frozenset[str]
    arm: ArmRuns


def v21_plant_ids(exp0008_root: Path) -> list[str]:
    """The sealed v2.1 plants that have a Cypher run, the 100-sheet ones first, then by number.

    Raises:
        ValueError: none found (the root is not EXP-0008's, or its sealed runs are gone).
    """
    found = []
    for path in (exp0008_root / EXP0008_RUNS).glob("S7-CYP-*"):
        match = EXP0008_PLANT.fullmatch(path.name.removeprefix("S7-CYP-"))
        if match is not None:
            found.append((int(match.group(1)), int(match.group(2)), match.group(0)))
    if not found:
        raise ValueError(
            f"expected EXP-0008 sealed runs under {exp0008_root / EXP0008_RUNS}, found none"
        )
    return [plant_id for _scale, _k, plant_id in sorted(found)]


def load_v21(exp0008_root: Path, finder_for: FinderFactory) -> list[V21Plant]:
    """Join and evaluate `cascade_v4_iso` on each EXP-0008 sealed plant."""
    policy = load_policies(V2T_POLICIES_DIR)[A2_PRIMARY]
    questions_root = exp0008_root / "questions"
    plants = []
    for plant_id in v21_plant_ids(exp0008_root):
        runs = exp0008_root / EXP0008_RUNS
        tiers = {"cypher-v2t": runs / f"S7-CYP-{plant_id}", "agent-v2t": runs / f"S7-AG-{plant_id}"}
        arm = load_arm(plant_id, tiers, [policy], questions_root, finder_for(plant_id))
        questions, splits = read_question_files(questions_root, plant_id)
        scale = 1000 if "1000g" in plant_id else 100
        plants.append(V21Plant(plant_id, scale, questions, r_headline_ids(questions, splits), arm))
    return plants


def _families(questions: Sequence[Question], ids: frozenset[str]) -> set[QuestionFamily]:
    return {q.family for q in questions if q.question_id in ids}


def shared_families(v22: Sequence[PlantData], v21: Sequence[V21Plant]) -> frozenset[QuestionFamily]:
    """The families that scope R holds on some v2.2 plant and the headline set on some v2.1 plant.

    Raises:
        ValueError: the two generations share no family.
    """
    new = {
        f
        for p in v22
        for f in _families(p.a2_questions, r_headline_ids(p.a2_questions, p.a2_splits))
    }
    old = {f for p in v21 for f in _families(p.questions, p.headline)}
    shared = frozenset(new & old)
    if not shared:
        raise ValueError(f"expected shared families, found none ({len(new)} v2.2, {len(old)} v2.1)")
    return shared


def family_flags(
    evaluation: Evaluation,
    questions: Sequence[Question],
    ids: frozenset[str],
    families: frozenset[QuestionFamily],
) -> list[float]:
    """acc@C (1.0 or 0.0) per question of `ids` whose family is shared, in file order."""
    family_of = {q.question_id: q.family for q in questions}
    return [
        float(s.correct_at_cutoff)
        for s in evaluation.scored
        if s.decision.question_id in ids and family_of[s.decision.question_id] in families
    ]


def _difference(new: float, old: float) -> float:
    return new - old


def data_effect_rows(v22: Sequence[PlantData], v21: Sequence[V21Plant]) -> list[ClaimRow]:
    """One descriptive row per scale: v2.2 minus v2.1 acc@C on the shared families."""
    shared = shared_families(v22, v21)
    names = ", ".join(sorted(f.value for f in shared))
    rows = []
    for scale, label in SCALE_LABELS.items():
        new_plants = [p for p in v22 if p.spec.scale == scale]
        old_plants = [p for p in v21 if p.scale == scale]
        new = [
            family_flags(
                p.a2.evaluations[A2_PRIMARY],
                p.a2_questions,
                r_headline_ids(p.a2_questions, p.a2_splits),
                shared,
            )
            for p in new_plants
        ]
        old = [
            family_flags(p.arm.evaluations[A2_PRIMARY], p.questions, p.headline, shared)
            for p in old_plants
        ]
        interval: Interval = cluster_unpaired_bootstrap(new, old, _difference)
        rows.append(
            ClaimRow(
                claim=f"Data effect {label}", arm="V2T-A2, v2.2 minus v2.1",
                status=ClaimStatus.DESCRIPTIVE, rule=RULE, interval=interval,
                scope=f"{len(shared)} shared families: {names}",
                n_questions=sum(map(len, new)) + sum(map(len, old)),
                detail=f"{len(new_plants)} v2.2 plants against {len(old_plants)} v2.1 plants",
                runs=tuple(r for p in new_plants for r in p.a2.run_ids)
                + tuple(r for p in old_plants for r in p.arm.run_ids),
            )
        )  # fmt: skip
    return rows
