"""The E2E report: pre-registered claims E1-E4 (PREREG section 5) over the R5 and V arms.

The logic here is pure (no files): it takes `ArmData` per arm and the question list. Reading the
runs is in `e2e_report_load.py`, the Markdown in `e2e_report_render.py`, the CLI in
`e2e_report.py`. The statistics are the EXP-0007 claims code (`paired_bootstrap`,
`wilson_interval`); nothing is computed by hand.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from plantgraph.exp0004.e2e_report_models import (
    R5_ARM,
    RESOLVER_ARMS,
    ArmData,
    ArmRow,
    ClaimRow,
    E2EReport,
    GroupRow,
    v_arm,
)
from plantgraph.qa.cascade.stats import PairedDifference, paired_bootstrap, wilson_interval
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


def _series(arm: ArmData, ids: Sequence[str]) -> list[float]:
    return [float(arm.correct[qid]) for qid in ids]


def paired_difference(a: ArmData, b: ArmData, ids: Sequence[str]) -> PairedDifference:
    """acc(a) - acc(b) with the EXP-0007 paired bootstrap (its default seed and resamples)."""
    return paired_bootstrap(_series(a, ids), _series(b, ids))


def _claim(
    claim: str,
    description: str,
    rule: str,
    difference: PairedDifference,
    passes: Callable[[PairedDifference], bool],
) -> ClaimRow:
    return ClaimRow(
        claim=claim,
        description=description,
        rule=rule,
        difference=difference,
        passed=passes(difference),
    )


def build_claims(arms: Mapping[str, ArmData], ids: Sequence[str]) -> list[ClaimRow]:
    """E1-E4 exactly as pre-registered; E4 is judged for D2 and D4 separately."""
    r5, d0 = arms[R5_ARM], arms[v_arm("d0")]
    e1 = paired_difference(d0, r5, ids)
    rows = [_claim("E1", "acc(V,D0) - acc(R5)", "CI upper < 0", e1, lambda d: d.ci_high < 0)]
    for resolver, number in (("d2", "E2"), ("d4", "E3")):
        name = resolver.upper()
        diff = paired_difference(arms[v_arm(resolver)], d0, ids)
        rows.append(
            _claim(
                number, f"acc(V,{name}) - acc(V,D0)", "CI lower > 0", diff, lambda d: d.ci_low > 0
            )
        )
    for resolver in ("d2", "d4"):
        name = resolver.upper()
        diff = paired_difference(arms[v_arm(resolver)], r5, ids)
        rows.append(
            _claim(
                f"E4 ({name})",
                f"acc(V,{name}) - acc(R5)",
                f"CI lower > {E4_MARGIN}",
                diff,
                lambda d: d.ci_low > E4_MARGIN,
            )
        )
    return rows


def _arm_row(arm: ArmData, ids: Sequence[str]) -> ArmRow:
    n_correct = sum(arm.correct[qid] for qid in ids)
    return ArmRow(
        label=arm.label,
        n=len(ids),
        n_correct=n_correct,
        accuracy=wilson_interval(n_correct, len(ids)),
        spend_usd=arm.spend_usd,
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


def build_e2e_report(
    arms: Mapping[str, ArmData], questions: Sequence[Question], policy: str, cutoff_s: float
) -> E2EReport:
    """All tables for the arms R5 and V-d0/d2/d4 (keyed by label), on their common questions."""
    ordered = [arms[R5_ARM], *(arms[v_arm(r)] for r in RESOLVER_ARMS)]
    ids = check_same_questions(ordered)
    return E2EReport(
        cutoff_s=cutoff_s,
        policy=policy,
        n_questions=len(ids),
        arms=[_arm_row(arm, ids) for arm in ordered],
        claims=build_claims(arms, ids),
        families=_group_rows(ordered, family_groups(questions, ids)),
        exposure=_group_rows(ordered, exposure_groups(questions, ids)),
        outcomes={arm.label: arm.outcomes for arm in ordered},
        notes=[
            "Exposed means the question's k_identity is greater than 0; a missing "
            "(None) k_identity counts as unexposed.",
            "Accuracy and outcome counts cover the same questions (R5's headline scope).",
            "New spend is the sum of cost_usd over calls not served from the cache, "
            "over all questions of the run (not only the headline scope). The V arms reused "
            "R5's cache, so their figure counts only the calls R5 had not already paid for: "
            "it is not a cost per arm and must not be compared with R5's full spend.",
        ],
    )
