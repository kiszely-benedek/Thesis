"""Agreement between the judge and the scorer, Cohen's kappa, disagreements, and the G2 verdict.

Two readings of "agree", so nothing is hidden: a row *agrees* when the judge's verdict matches
the scorer's (scorer right and judge "correct", or scorer wrong and judge "incorrect"). A judge
verdict "ambiguous_question" agrees with neither and is counted on its own. Kappa is computed
only over rows with a decisive verdict, pooled over the audited rows (it is not re-weighted to
the population: the right rows are a sample, the wrong rows are all or a stratified part).
"""

from __future__ import annotations

import csv
import io
from collections import Counter

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.audit.models import PILOT_DEFECT_STRATA, AuditRecord, JudgeVerdict
from plantgraph.qa.audit.select import AuditPlan

#: Share of a pilot group the judge must get right for gate G2 (review-fixes §5.3).
G2_THRESHOLD = 0.8

_RIGHT_STRATA = frozenset({"right_min", "right_extra"})
_WRONG_STRATA = frozenset({"wrong"})
_CONTEXTRAG_STRATA = frozenset({"contextrag_wrong"})

#: Disagreement classes, named for what the main session then checks against the graph.
SYSTEM_RIGHT_SCORER_WRONG = "system_right_scorer_wrong"
SCORER_RIGHT_JUDGE_INCORRECT = "scorer_right_judge_incorrect"
AMBIGUOUS_QUESTION = "ambiguous_question"


class GroupStats(BaseModel):
    """Judge-versus-scorer counts for one group of rows."""

    model_config = ConfigDict(frozen=True)

    n: int
    n_agree: int
    n_judged_correct: int
    n_judged_incorrect: int
    n_ambiguous: int

    @property
    def agreement(self) -> float | None:
        """Share of rows where judge and scorer agree; `None` for an empty group."""
        return self.n_agree / self.n if self.n else None


class G2Verdict(BaseModel):
    """Gate G2: did the judge find the known defects and keep the controls?"""

    model_config = ConfigDict(frozen=True)

    n_defect: int
    n_defect_found: int
    n_control: int
    n_control_correct: int

    @property
    def passed(self) -> bool:
        """Both shares at least `G2_THRESHOLD`, and both groups non-empty."""
        if self.n_defect == 0 or self.n_control == 0:
            return False
        defect_ok = self.n_defect_found / self.n_defect >= G2_THRESHOLD
        return defect_ok and self.n_control_correct / self.n_control >= G2_THRESHOLD


def disagreement_class(record: AuditRecord) -> str | None:
    """The disagreement class of a row, or `None` if judge and scorer agree."""
    verdict = record.reply.verdict
    scorer_correct = record.item.row.scorer_correct
    if verdict is JudgeVerdict.AMBIGUOUS_QUESTION:
        return AMBIGUOUS_QUESTION
    if scorer_correct and verdict is JudgeVerdict.INCORRECT:
        return SCORER_RIGHT_JUDGE_INCORRECT
    if not scorer_correct and verdict is JudgeVerdict.CORRECT:
        return SYSTEM_RIGHT_SCORER_WRONG
    return None


def group_stats(records: list[AuditRecord]) -> GroupStats:
    """Counts over one group of judged rows."""
    verdicts = Counter(record.reply.verdict for record in records)
    return GroupStats(
        n=len(records),
        n_agree=sum(1 for record in records if disagreement_class(record) is None),
        n_judged_correct=verdicts[JudgeVerdict.CORRECT],
        n_judged_incorrect=verdicts[JudgeVerdict.INCORRECT],
        n_ambiguous=verdicts[JudgeVerdict.AMBIGUOUS_QUESTION],
    )


def cohens_kappa(records: list[AuditRecord]) -> float | None:
    """Cohen's kappa between scorer (right/wrong) and judge (correct/incorrect).

    Rows the judge called ambiguous are left out. `None` when no row is decisive or the
    expected agreement is 1 (one label only), where kappa is undefined.
    """
    decisive = [r for r in records if r.reply.verdict is not JudgeVerdict.AMBIGUOUS_QUESTION]
    if not decisive:
        return None
    total = len(decisive)
    observed = sum(1 for r in decisive if disagreement_class(r) is None) / total
    scorer_yes = sum(1 for r in decisive if r.item.row.scorer_correct) / total
    judge_yes = sum(1 for r in decisive if r.reply.verdict is JudgeVerdict.CORRECT) / total
    expected = scorer_yes * judge_yes + (1 - scorer_yes) * (1 - judge_yes)
    if expected == 1.0:
        return None
    return (observed - expected) / (1 - expected)


def g2_verdict(records: list[AuditRecord]) -> G2Verdict:
    """Gate G2 over the pilot rows among `records`."""
    defects = [r for r in records if r.item.stratum in PILOT_DEFECT_STRATA]
    controls = [r for r in records if r.item.stratum == "pilot_control"]
    found = [r for r in defects if r.reply.verdict is not JudgeVerdict.INCORRECT]
    right = [r for r in controls if r.reply.verdict is JudgeVerdict.CORRECT]
    return G2Verdict(
        n_defect=len(defects),
        n_defect_found=len(found),
        n_control=len(controls),
        n_control_correct=len(right),
    )


def disagreements_by_class_and_family(records: list[AuditRecord]) -> dict[tuple[str, str], int]:
    """Number of disagreements per (class, family)."""
    counts: Counter[tuple[str, str]] = Counter()
    for record in records:
        found = disagreement_class(record)
        if found is not None:
            counts[(found, record.item.row.family.value)] += 1
    return dict(counts)


def disagreement_sheet(records: list[AuditRecord]) -> str:
    """CSV of every disagreement, for the main session to check against the graph."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        ["class", "stratum", "run_id", "strategy", "question_id", "family", "scale"]
        + ["scorer_correct", "judge_verdict", "reference_ok", "reason"]
    )
    for record in records:
        found = disagreement_class(record)
        if found is None:
            continue
        row = record.item.row
        writer.writerow(
            [found, record.item.stratum, row.run_id, row.strategy, row.question_id]
            + [row.family.value, row.scale, row.scorer_correct, record.reply.verdict.value]
            + [record.reply.reference_ok, record.reply.reason]
        )
    return out.getvalue()


def _in_strata(records: list[AuditRecord], strata: frozenset[str]) -> list[AuditRecord]:
    return [record for record in records if record.item.stratum in strata]


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f} %"


def _group_line(name: str, stats: GroupStats) -> str:
    return (
        f"| {name} | {stats.n} | {_percent(stats.agreement)} | {stats.n_judged_correct} | "
        f"{stats.n_judged_incorrect} | {stats.n_ambiguous} |"
    )


def render_report(records: list[AuditRecord], plan: AuditPlan | None = None) -> str:
    """The audit report as Markdown: groups, kappa, disagreements, coverage, G2."""
    audit = [r for r in records if r.item.stratum not in PILOT_DEFECT_STRATA | {"pilot_control"}]
    kappa = cohens_kappa(audit)
    lines = [
        "# Scorer audit report",
        "",
        "| Group | Rows | Agreement | Judged correct | Judged incorrect | Ambiguous |",
        "|---|---|---|---|---|---|",
        _group_line("right sample", group_stats(_in_strata(audit, _RIGHT_STRATA))),
        _group_line("wrong rows", group_stats(_in_strata(audit, _WRONG_STRATA))),
        _group_line("ContextRAG wrong rows", group_stats(_in_strata(audit, _CONTEXTRAG_STRATA))),
        "",
        f"Cohen's kappa (decisive rows, pooled, not population-weighted): "
        f"{'n/a' if kappa is None else f'{kappa:.3f}'}",
        "",
        "## Disagreements by class and family",
        "",
        "| Class | Family | Rows |",
        "|---|---|---|",
    ]
    counts = disagreements_by_class_and_family(audit)
    lines += [f"| {cls} | {family} | {n} |" for (cls, family), n in sorted(counts.items())]
    if plan is not None:
        lines += ["", _coverage_line(plan)]
    pilot = g2_verdict(records)
    if pilot.n_defect or pilot.n_control:
        lines += ["", _g2_line(pilot)]
    return "\n".join(lines) + "\n"


def _coverage_line(plan: AuditPlan) -> str:
    return (
        f"Budget coverage: {plan.wrong_selected} of {plan.wrong_available} distinct wrong rows; "
        f"ContextRAG wrong rows {plan.contextrag_selected} of {plan.contextrag_available}; "
        f"extra right rows {plan.right_extra_selected} of {plan.right_extra_available}."
    )


def _g2_line(pilot: G2Verdict) -> str:
    return (
        f"Gate G2: known defects found {pilot.n_defect_found}/{pilot.n_defect}, "
        f"controls judged correct {pilot.n_control_correct}/{pilot.n_control}: "
        f"{'PASS' if pilot.passed else 'FAIL'} (threshold {100 * G2_THRESHOLD:.0f} % each)."
    )
