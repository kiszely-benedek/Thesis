"""The E2E report: pre-registered claims E1-E4 (PREREG section 5) over the R5 and V arms.

The logic here is pure (no files): it takes `ArmData` per arm and the question list. Reading the
runs is in `e2e_report_load.py`, the Markdown in `e2e_report_render.py`, the CLI in
`e2e_report.py`. The statistics are the EXP-0007 claims code (`paired_bootstrap`,
`wilson_interval`) and its two-stage generalisation over plants (`stats_cluster.py`); nothing
is computed by hand.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean

from plantgraph.exp0004.e2e_report_models import (
    R5_ARM,
    RESOLVER_ARMS,
    ArmData,
    ArmRow,
    ClaimRow,
    E2EReport,
    GroupRow,
    PlantRow,
    v_arm,
)
from plantgraph.qa.cascade.stats import PairedDifference, wilson_interval
from plantgraph.qa.cascade.stats_cluster import (
    cluster_mean_interval,
    cluster_paired_bootstrap,
    same_sign_count,
)
from plantgraph.qa.models import Question

#: E4's non-inferiority margin, fixed in PREREG section 5.
E4_MARGIN = -0.03

UNEXPOSED = "unexposed (k_identity = 0 or None)"
EXPOSED = "exposed (k_identity > 0)"


def check_same_questions(arms: Sequence[ArmData]) -> list[str]:
    """The shared question ids, sorted; refuses arms that answered different question sets.

    Raises:
        ValueError: some arm's question ids differ from the first arm's.
    """
    reference = set(arms[0].correct)
    for arm in arms[1:]:
        extra, missing = set(arm.correct) - reference, reference - set(arm.correct)
        if extra or missing:
            raise ValueError(
                f"expected arm {arm.label} to hold the same questions as {arms[0].label}, "
                f"found {len(extra)} extra {sorted(extra)[:3]} "
                f"and {len(missing)} missing {sorted(missing)[:3]}"
            )
    return sorted(reference)


@dataclass(frozen=True)
class PlantArms:
    """One plant's arms (keyed by label) and its questions; `plant_id` is its corpus family id."""

    plant_id: str
    arms: Mapping[str, ArmData]
    questions: Sequence[Question]


@dataclass(frozen=True)
class _Spec:
    """A claim before it is measured: which arm minus which, and the rule that passes it."""

    claim: str
    plus: str
    minus: str
    description: str
    rule: str
    passes: Callable[[PairedDifference], bool]


def _specs() -> list[_Spec]:
    """E1-E4 exactly as pre-registered; E4 is judged for D2 and D4 separately."""
    d0 = v_arm("d0")
    specs = [
        _Spec("E1", d0, R5_ARM, "acc(V,D0) - acc(R5)", "CI upper < 0", lambda d: d.ci_high < 0)
    ]
    for resolver, number in (("d2", "E2"), ("d4", "E3")):
        description = f"acc(V,{resolver.upper()}) - acc(V,D0)"
        specs.append(
            _Spec(number, v_arm(resolver), d0, description, "CI lower > 0", lambda d: d.ci_low > 0)
        )
    for resolver in ("d2", "d4"):
        specs.append(
            _Spec(
                f"E4 ({resolver.upper()})",
                v_arm(resolver),
                R5_ARM,
                f"acc(V,{resolver.upper()}) - acc(R5)",
                f"CI lower > {E4_MARGIN}",
                lambda d: d.ci_low > E4_MARGIN,
            )
        )
    return specs


def _series(arm: ArmData, ids: Sequence[str]) -> list[float]:
    return [float(arm.correct[qid]) for qid in ids]


def _plant_series(
    plants: Sequence[PlantArms], ids_by_plant: Sequence[Sequence[str]], label: str
) -> list[list[float]]:
    """One 0/1 series per plant for the arm `label`, over that plant's shared question ids."""
    return [_series(p.arms[label], ids) for p, ids in zip(plants, ids_by_plant, strict=True)]


def _claim(
    spec: _Spec, plants: Sequence[PlantArms], ids_by_plant: Sequence[Sequence[str]]
) -> ClaimRow:
    """Pooled paired difference of one claim; every claim draws the same plants and questions."""
    plus = _plant_series(plants, ids_by_plant, spec.plus)
    minus = _plant_series(plants, ids_by_plant, spec.minus)
    difference = cluster_paired_bootstrap(plus, minus)
    per_plant = [fmean(x) - fmean(y) for x, y in zip(plus, minus, strict=True)]
    return ClaimRow(
        claim=spec.claim,
        description=spec.description,
        rule=spec.rule,
        difference=difference,
        passed=spec.passes(difference),
        n_plants=len(plants),
        n_same_sign=same_sign_count(per_plant, difference.mean) if len(plants) > 1 else None,
    )


def build_claims(
    plants: Sequence[PlantArms], ids_by_plant: Sequence[Sequence[str]]
) -> list[ClaimRow]:
    """E1-E4 over the plants (one plant: the registered paired bootstrap, unchanged)."""
    return [_claim(spec, plants, ids_by_plant) for spec in _specs()]


def _arm_row(
    label: str, plants: Sequence[PlantArms], ids_by_plant: Sequence[Sequence[str]]
) -> ArmRow:
    series = _plant_series(plants, ids_by_plant, label)
    n_correct = sum(round(sum(values)) for values in series)
    n = sum(len(values) for values in series)
    return ArmRow(
        label=label,
        n=n,
        n_correct=n_correct,
        # one plant keeps the registered Wilson interval; several get the two-stage bootstrap
        accuracy=wilson_interval(n_correct, n)
        if len(plants) == 1
        else cluster_mean_interval(series),
        spend_usd=sum(p.arms[label].spend_usd for p in plants),
    )


def _group_rows(arms: Sequence[ArmData], groups: Mapping[str, Sequence[str]]) -> list[GroupRow]:
    """A row per (group, arm); a group is a list of question ids."""
    return [
        GroupRow(
            group=name,
            arm=arm.label,
            n=len(members),
            n_correct=sum(arm.correct[qid] for qid in members),
        )
        for name, members in groups.items()
        for arm in arms
    ]


def family_groups(questions: Sequence[Question], ids: Sequence[str]) -> dict[str, list[str]]:
    """Question ids per family value, families in sorted order."""
    by_id = {q.question_id: q for q in questions}
    groups: dict[str, list[str]] = {}
    for qid in ids:
        groups.setdefault(by_id[qid].family.value, []).append(qid)
    return dict(sorted(groups.items()))


def exposure_groups(questions: Sequence[Question], ids: Sequence[str]) -> dict[str, list[str]]:
    """Exposed (`k_identity > 0`) vs the rest; `None` counts as unexposed."""
    by_id = {q.question_id: q for q in questions}
    groups: dict[str, list[str]] = {EXPOSED: [], UNEXPOSED: []}
    for qid in ids:
        k_identity = by_id[qid].k_identity
        exposed = k_identity is not None and k_identity > 0
        groups[EXPOSED if exposed else UNEXPOSED].append(qid)
    return groups


def _added(seen: GroupRow | None, row: GroupRow) -> GroupRow:
    """`row` with the counts of an earlier plant's row for the same (group, arm) added."""
    if seen is None:
        return row
    return row.model_copy(update={"n": seen.n + row.n, "n_correct": seen.n_correct + row.n_correct})


def _sum_groups(per_plant: Sequence[Sequence[GroupRow]]) -> list[GroupRow]:
    """Group rows of several plants added up per (group, arm), in first-seen order."""
    totals: dict[tuple[str, str], GroupRow] = {}
    for row in (row for rows in per_plant for row in rows):
        totals[(row.group, row.arm)] = _added(totals.get((row.group, row.arm)), row)
    return list(totals.values())


def _sum_outcomes(per_plant: Sequence[ArmData]) -> dict[str, dict[str, int]]:
    """Tier -> outcome -> questions, added up over one arm's plants."""
    totals: dict[str, Counter[str]] = {}
    for arm in per_plant:
        for tier, counts in arm.outcomes.items():
            totals.setdefault(tier, Counter()).update(counts)
    return {tier: dict(counts) for tier, counts in totals.items()}


def _plant_rows(
    plants: Sequence[PlantArms], ids_by_plant: Sequence[Sequence[str]], labels: Sequence[str]
) -> list[PlantRow]:
    """Each plant's own arm accuracies (shown before the pooled table)."""
    return [
        PlantRow(
            plant_id=p.plant_id,
            arms=[
                _arm_row(
                    label,
                    [p],
                    [ids],
                )
                for label in labels
            ],
        )
        for p, ids in zip(plants, ids_by_plant, strict=True)
    ]


def build_pooled_e2e_report(plants: Sequence[PlantArms], policy: str, cutoff_s: float) -> E2EReport:
    """All tables for R5 and V-d0/d2/d4 over one or more plants.

    Each plant's arms must answer the same questions. With several plants the claims use the
    two-stage cluster bootstrap (plants, then questions; `stats_cluster.py`), the per-plant
    results come first and the pooled accuracy is the equal-weight mean of the plants.

    Raises:
        ValueError: no plant, or a plant whose arms answered different question sets.
    """
    if not plants:
        raise ValueError("expected at least one plant for the E2E report, found none")
    labels = [R5_ARM, *(v_arm(r) for r in RESOLVER_ARMS)]
    ids_by_plant = [check_same_questions([p.arms[label] for label in labels]) for p in plants]
    return E2EReport(
        cutoff_s=cutoff_s,
        policy=policy,
        n_questions=sum(len(ids) for ids in ids_by_plant),
        n_plants=len(plants),
        plants=_plant_rows(plants, ids_by_plant, labels) if len(plants) > 1 else [],
        arms=[_arm_row(label, plants, ids_by_plant) for label in labels],
        claims=build_claims(plants, ids_by_plant),
        families=_sum_groups(
            [
                _group_rows(_ordered(p, labels), family_groups(p.questions, ids))
                for p, ids in zip(plants, ids_by_plant, strict=True)
            ]
        ),
        exposure=_sum_groups(
            [
                _group_rows(_ordered(p, labels), exposure_groups(p.questions, ids))
                for p, ids in zip(plants, ids_by_plant, strict=True)
            ]
        ),
        outcomes={label: _sum_outcomes([p.arms[label] for p in plants]) for label in labels},
        notes=_notes(len(plants)),
    )


def _ordered(plant: PlantArms, labels: Sequence[str]) -> list[ArmData]:
    return [plant.arms[label] for label in labels]


def build_e2e_report(
    arms: Mapping[str, ArmData], questions: Sequence[Question], policy: str, cutoff_s: float
) -> E2EReport:
    """The single-plant report (the first measurement's): `build_pooled_e2e_report` on one plant."""
    return build_pooled_e2e_report([PlantArms("", arms, questions)], policy, cutoff_s)


def _notes(n_plants: int) -> list[str]:
    notes = [
        "Exposed means the question's k_identity is greater than 0; a missing "
        "(None) k_identity counts as unexposed.",
        "Accuracy and outcome counts cover the same questions (R5's headline scope).",
        "New spend is the sum of cost_usd over calls not served from the cache, "
        "over all questions of the run (not only the headline scope). The V arms reused "
        "R5's cache, so their figure counts only the calls R5 had not already paid for: "
        "it is not a cost per arm and must not be compared with R5's full spend.",
    ]
    if n_plants > 1:
        notes += [
            f"Pooled over {n_plants} plants: the value is the equal-weight mean of the plants; "
            "intervals are two-stage cluster bootstraps (plants, then questions) with the "
            "EXP-0007 seed and resample count, and every claim uses the same draws. With few "
            "plants the bootstrap understates between-plant variance (about 4/5 at five).",
            "'Plants with the pooled sign' is descriptive and judges nothing.",
        ]
    return notes
