"""The pre-registered claims of EXP-0009 (PREREG A, design §12.1) computed from the loaded runs.

Everything statistical is EXP-0008's own code, reused and not copied: `build_sealed` for the A2
claims (Q4, K1-K3, Q5), `scale_rows` for Q4-B, and `cluster_paired_bootstrap` for SB1 and SB2. All
use `qa/cascade/stats.py`: 5,000 resamples, seed 1, and the two-stage cluster bootstrap (plants
first, then questions inside each drawn plant). A scale pools its five plants with equal weight.

Accuracy here is **acc@C**: correct and within the 120 s cutoff of setting A, as in EXP-0008.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from plantgraph.qa.cascade.evaluate import Evaluation, LatencyBound, evaluate_policy
from plantgraph.qa.cascade.limits import SETTING_A
from plantgraph.qa.cascade.report_claims import V2T_CLAIMS
from plantgraph.qa.cascade.report_scopes import SCOPE_HEADLINE, restrict
from plantgraph.qa.cascade.report_sealed import build_sealed
from plantgraph.qa.cascade.report_sealed_models import ScaleRow, SealedReport
from plantgraph.qa.cascade.report_sealed_scale import scale_rows
from plantgraph.qa.cascade.report_sealed_views import (
    SealedCorpus,
    group_scales,
    scope_views,
)
from plantgraph.qa.cascade.stats import Interval, interval_of
from plantgraph.qa.cascade.stats_cluster import cluster_paired_bootstrap
from plantgraph.qa.exp0009.analysis_load import A2_PRIMARY, ArmRuns, PlantData
from plantgraph.qa.exp0009.analysis_models import ClaimRow, ClaimStatus
from plantgraph.qa.exp0009.analysis_scope import (
    X_FAMILIES,
    X_ISOLATION_FAMILIES,
    r_headline_ids,
    stripped,
    stripped_id,
    x_ids,
)
from plantgraph.qa.models import Question
from plantgraph.qa.v2tb.policy_b import B_POLICY_NAME

CUTOFF_S = SETTING_A.cutoff_s
SCALE_LABELS = {100: "S100", 1000: "S1000"}
SCOPE_R = "R (EXP-0008 headline set, X families out)"
SCOPE_R_X = "R and X (every X family)"
SCOPE_R_X_NO_POSITION = "R and X without POSITION_OF_VALVE"
SCOPE_X_ISOLATION = "X isolation families"

RULE_NO_LOSS = "the interval contains 0 or lies above it"
RULE_ABOVE_ZERO = "the interval lies above 0"
RULE_DESCRIPTIVE = "descriptive: the difference and its interval, no margin"
EXP0008_RULES = {
    "K1": "as EXP-0008: no accuracy loss against always-agent, cost and latency clearly lower",
    "K2": "as EXP-0008: the interval against random escalation lies above 0",
    "K3": "as EXP-0008: median latency <= 10 s and p90 <= 60 s",
    "Q5": "as EXP-0008: the interval of always-agent minus always-Cypher lies above 0",
}


# ---- pass rules (pure) ------------------------------------------------------------------------


def no_accuracy_loss(interval: Interval) -> bool:
    """Q4's rule: the interval contains 0 or lies above it, so no loss can be shown."""
    return interval.ci_high >= 0.0


def clearly_above_zero(interval: Interval) -> bool:
    """SB2's rule: the whole interval lies above 0."""
    return interval.ci_low > 0.0


def _status(passed: bool) -> ClaimStatus:
    return ClaimStatus.PASS if passed else ClaimStatus.FAIL


# ---- one arm, narrowed to a question set -------------------------------------------------------


def scope_corpus(
    plant: PlantData, arm: ArmRuns, questions: Sequence[Question], ids: frozenset[str]
) -> SealedCorpus:
    """The arm's policies re-evaluated on `ids` only, in the shape EXP-0008's report code reads.

    The sheet count is the one G0k checked against the build, so no corpus file is opened.

    Raises:
        ValueError: no question of the arm lies in `ids`.
    """
    kept = [q for q in questions if q.question_id in ids]
    if not kept:
        raise ValueError(f"expected questions of the scope on {plant.spec.plant_id}, found none")
    joins = {name: restrict(joined, ids) for name, joined in arm.joins.items()}
    evaluations = {name: evaluate_policy(j, CUTOFF_S) for name, j in joins.items()}
    return SealedCorpus(
        plant.spec.plant_id, plant.spec.predicted_sheets, kept, None, joins, evaluations
    )


def scale_groups(plants: Sequence[PlantData]) -> dict[str, list[str]]:
    """Scale label -> the A ids of its plants, the 100-sheet scale first (plan order)."""
    groups: dict[str, list[str]] = {}
    for plant in plants:
        groups.setdefault(SCALE_LABELS[plant.spec.scale], []).append(plant.spec.plant_id)
    return groups


def require_b(plant: PlantData) -> ArmRuns:
    """The plant's B runs.

    Raises:
        ValueError: B did not run on this plant.
    """
    if plant.b is None:
        raise ValueError(f"expected B runs on {plant.spec.plant_id}, found none")
    return plant.b


def run_ids(plants: Sequence[PlantData], *, b: bool) -> tuple[str, ...]:
    """The run folders an arm's claim reads."""
    arms = [require_b(p) if b else p.a2 for p in plants]
    return tuple(rid for arm in arms for rid in arm.run_ids)


# ---- A2: Q4, K1, K2, K3, Q5 --------------------------------------------------------------------


def a2_sealed_report(plants: Sequence[PlantData]) -> SealedReport:
    """EXP-0008's sealed report on scope R of V2T-A2: `headline` is the only scope it holds."""
    corpora = [
        scope_corpus(p, p.a2, p.a2_questions, r_headline_ids(p.a2_questions, p.a2_splits))
        for p in plants
    ]
    return build_sealed(corpora, LatencyBound(cutoff_s=CUTOFF_S), V2T_CLAIMS, scale_groups(plants))


def scale_claim(claim: str, arm: str, scope: str, row: ScaleRow, runs: tuple[str, ...]) -> ClaimRow:
    """Q4 or Q4-B from a scale row: S1000 minus S100 accuracy, judged by the no-loss rule."""
    interval = row.accuracy_diff
    small, large = row.accuracy_small, row.accuracy_large
    detail = (
        f"acc@C S100 {small.estimate:.3f} ({row.n_plants_small} plants), "
        f"S1000 {large.estimate:.3f} ({row.n_plants_large} plants)"
    )
    return ClaimRow(
        claim=claim, arm=arm, scope=scope, rule=RULE_NO_LOSS, runs=runs, detail=detail,
        status=_status(no_accuracy_loss(interval)), interval=interval,
    )  # fmt: skip


def _primary_scale_row(report: SealedReport) -> ScaleRow:
    for row in report.scale_rows:
        if row.policy == V2T_CLAIMS.primary:
            return row
    raise ValueError(f"expected a scale row of {V2T_CLAIMS.primary}, found none")


def _paired_interval(report: SealedReport, claim: str) -> Interval | None:
    for pair in report.paired_rows:
        if pair.claim == claim and pair.corpus_id == report.claims_corpus:
            return interval_of(pair.comparison.accuracy_at_cutoff)
    return None


def _k3_interval(report: SealedReport) -> Interval | None:
    for row in report.scope_rows:
        if row.corpus_id == report.claims_corpus and row.policy == V2T_CLAIMS.primary:
            return row.latency_median
    return None


def a2_claim_rows(report: SealedReport, plants: Sequence[PlantData]) -> list[ClaimRow]:
    """Q4 first, then K1, K2, K3 and Q5 with EXP-0008's verdicts and their pooled intervals."""
    runs = run_ids(plants, b=False)
    sizes = {scale: scopes[SCOPE_HEADLINE] for scale, scopes in report.scope_sizes.items()}
    q4 = scale_claim("Q4", "V2T-A2", SCOPE_R, _primary_scale_row(report), runs)
    rows = [q4.model_copy(update={"n_questions": sum(sizes.values())})]
    intervals = {
        "K1": _paired_interval(report, "K1"),
        "K2": _paired_interval(report, "K2"),
        "K3": _k3_interval(report),
        "Q5": _paired_interval(report, "Q5"),
    }
    for verdict in (v for v in report.claims if v.rule in intervals):
        rows.append(
            ClaimRow(
                claim=verdict.rule, arm="V2T-A2", scope=SCOPE_R, rule=EXP0008_RULES[verdict.rule],
                status=ClaimStatus(verdict.status), interval=intervals[verdict.rule],
                unit="seconds" if verdict.rule == "K3" else "acc@C",
                n_questions=sizes[report.claims_corpus], detail=" | ".join(verdict.details),
                runs=runs,
            )
        )  # fmt: skip
    return rows


def exp0008_verdict_lines(report: SealedReport) -> list[str]:
    """EXP-0008's own verdict headlines (Q4 with its cost elasticity, K1-K3, Q5), verbatim."""
    return [v.headline for v in report.claims if v.status != "NOT_RUN"]


# ---- B: Q4-B and its sensitivity row ------------------------------------------------------------


def b_scope_ids(plant: PlantData, *, with_position: bool) -> frozenset[str]:
    """B's scope R plus its X questions, with or without POSITION_OF_VALVE."""
    families = X_FAMILIES if with_position else X_ISOLATION_FAMILIES
    return r_headline_ids(plant.b_questions, plant.b_splits) | x_ids(plant.b_questions, families)


def b_scale_claim(plants: Sequence[PlantData], *, with_position: bool) -> ClaimRow:
    """Q4-B: V2T-B accuracy S1000 minus S100 over R and X (the sensitivity row drops POSITION)."""
    corpora = [
        scope_corpus(p, require_b(p), p.b_questions, b_scope_ids(p, with_position=with_position))
        for p in plants
    ]
    groups = group_scales(corpora, scale_groups(plants))
    if len(groups) != 2:
        raise ValueError(f"expected two scales for Q4-B, found {len(groups)}")
    views = {c.corpus_id: scope_views(c, CUTOFF_S) for c in corpora}
    row = next(r for r in scale_rows(groups[0], groups[1], views) if r.policy == B_POLICY_NAME)
    scope = SCOPE_R_X if with_position else SCOPE_R_X_NO_POSITION
    claim = "Q4-B" if with_position else "Q4-B sensitivity (no POSITION_OF_VALVE)"
    return scale_claim(claim, "V2T-B", scope, row, run_ids(plants, b=True))


# ---- SB1 and SB2: B minus A2, question for question ---------------------------------------------


def _flags(evaluation: Evaluation, wanted: frozenset[str]) -> dict[str, float]:
    """Stripped question id -> acc@C (1.0 or 0.0), for the wanted stripped ids."""
    flags = {
        stripped_id(s.decision.question_id): float(s.correct_at_cutoff) for s in evaluation.scored
    }
    return {key: flags[key] for key in wanted if key in flags}


def paired_flags(plant: PlantData, a2_ids: frozenset[str]) -> tuple[list[float], list[float]]:
    """(B flags, A2 flags) of the same questions, in one fixed order.

    Raises:
        ValueError: a question is missing from either arm's runs.
    """
    wanted = stripped(a2_ids)
    a2 = _flags(plant.a2.evaluations[A2_PRIMARY], wanted)
    b = _flags(require_b(plant).evaluations[B_POLICY_NAME], wanted)
    if set(a2) != wanted or set(b) != wanted:
        raise ValueError(
            f"expected the same {len(wanted)} questions in both arms on {plant.spec.plant_id}, "
            f"found {len(a2)} in A2 and {len(b)} in B"
        )
    order = sorted(wanted)
    return [b[k] for k in order], [a2[k] for k in order]


def paired_claim(
    claim: str,
    scope: str,
    rule: str,
    plants: Sequence[PlantData],
    a2_ids_of: Callable[[PlantData], frozenset[str]],
    judge: Callable[[Interval], ClaimStatus],
) -> ClaimRow:
    """B minus A2 pooled over `plants` with the two-stage bootstrap (plants, then questions)."""
    pairs = [paired_flags(p, a2_ids_of(p)) for p in plants]
    difference = cluster_paired_bootstrap([b for b, _a in pairs], [a for _b, a in pairs])
    interval = interval_of(difference)
    return ClaimRow(
        claim=claim, arm="V2T-B minus V2T-A2", scope=scope, rule=rule, status=judge(interval),
        interval=interval, n_questions=sum(len(b) for b, _a in pairs),
        runs=run_ids(plants, b=True) + run_ids(plants, b=False),
    )  # fmt: skip


def _r_ids_of(plant: PlantData) -> frozenset[str]:
    return r_headline_ids(plant.a2_questions, plant.a2_splits)


def _x_isolation_ids_of(plant: PlantData) -> frozenset[str]:
    return x_ids(plant.a2_questions, X_ISOLATION_FAMILIES)


def _describe(_interval: Interval) -> ClaimStatus:
    return ClaimStatus.DESCRIPTIVE


def _judge_sb2(interval: Interval) -> ClaimStatus:
    return _status(clearly_above_zero(interval))


def sb_claim_rows(plants: Sequence[PlantData]) -> list[ClaimRow]:
    """SB1 (descriptive) and SB2 (the interval lies above 0), pooled, then per scale."""
    rows = [
        paired_claim("SB1", SCOPE_R, RULE_DESCRIPTIVE, plants, _r_ids_of, _describe),
        paired_claim(
            "SB2", SCOPE_X_ISOLATION, RULE_ABOVE_ZERO, plants, _x_isolation_ids_of, _judge_sb2
        ),
    ]
    by_scale: Mapping[str, list[PlantData]] = {
        label: [p for p in plants if SCALE_LABELS[p.spec.scale] == label]
        for label in scale_groups(plants)
    }
    for label, subset in by_scale.items():
        rows.append(
            paired_claim(f"SB1 {label}", SCOPE_R, RULE_DESCRIPTIVE, subset, _r_ids_of, _describe)
        )
        rows.append(
            paired_claim(
                f"SB2 {label}",
                SCOPE_X_ISOLATION,
                RULE_DESCRIPTIVE,
                subset,
                _x_isolation_ids_of,
                _describe,
            )
        )
    return rows
