"""The other descriptive tables: network-touching shares, `rules.json` summaries, precision/recall.

- **Network-touching.** A *network* is a pipe system the whole plant shares (flare header, closed
  drain): v2.2 draws it on its own sheets, and its items live in unit numbers from 9000 up. A
  question *touches a network* when one of its gold evidence tags belongs to such a unit.
- **`rules.json`.** The build-time report of the handbook rules a plant was generated under: per
  rule, how many places were checked and how many broke it.
- **Precision, recall, F1.** For a list answer (a set of tags or valves) correctness is all or
  nothing, so these say how close a wrong list was. They come from END's offline re-score, which
  re-scores the saved answers of **each tier** with no model call
  (`reports/rescore_AG_<plant>.json` and `reports/rescore_CYP_<plant>.json`). A cascade asks the
  Cypher tier first and falls back to the agent tier, so two tables are written: one per tier
  (every answer that tier gave, wherever the cascade stopped) and one over the cascade's **final
  answers** (each question scored from the tier that answered it).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from plantgraph.benchmark.v2.network_models import is_network_unit_no
from plantgraph.benchmark.v2.rules.registry import RuleReport
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.qa.cascade.evaluate import Evaluation
from plantgraph.qa.exp0009.analysis_claims import SCALE_LABELS
from plantgraph.qa.exp0009.analysis_load import A2_PRIMARY, TIER_RUNS, PlantData
from plantgraph.qa.exp0009.analysis_models import Table, TableCell
from plantgraph.qa.exp0009.analysis_scope import X_FAMILIES, r_headline_ids
from plantgraph.qa.exp0009.analysis_x import ALL_SCALES
from plantgraph.qa.exp0009.records import RescoreReport, RowScore
from plantgraph.qa.models import Question
from plantgraph.qa.v2tb.policy_b import policy_b


def touches_network(question: Question) -> bool:
    """Whether some gold evidence tag of the question belongs to a network unit."""
    for tag in question.evidence_tags:
        parsed = parse_tag(tag)
        if parsed is not None and is_network_unit_no(parsed.unit):
            return True
    return False


def _scope_of(question: Question, r_ids: frozenset[str]) -> str | None:
    if question.family in X_FAMILIES:
        return "X"
    return "R" if question.question_id in r_ids else None


def network_table(plants: Sequence[PlantData]) -> Table:
    """Per scale, scope and family: how many questions touch a network, from B's question file."""
    counts: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for plant in plants:
        r_ids = r_headline_ids(plant.b_questions, plant.b_splits)
        scale = SCALE_LABELS[plant.spec.scale]
        for question in plant.b_questions:
            scope = _scope_of(question, r_ids)
            if scope is None:
                continue
            for key in ((scale, scope, question.family.value), (scale, scope, "all")):
                counts[key][0] += 1
                counts[key][1] += touches_network(question)
    rows: list[list[TableCell]] = [
        [scale, scope, family, n, touching, touching / n]
        for (scale, scope, family), (n, touching) in sorted(counts.items())
    ]
    return Table(
        name="network_touching", title="Questions whose evidence touches a network unit",
        note="from B's file (every R and X question); a network unit's number is 9000 or more",
        header=["scale", "scope", "family", "questions", "touching", "share"], rows=rows,
    )  # fmt: skip


# ---- rules.json -------------------------------------------------------------------------------


def read_rules(root: Path, plant: PlantData) -> RuleReport | None:
    """`corpora/<A id>/rules.json`, or `None` when the plant has none."""
    path = root / "corpora" / plant.spec.plant_id / "rules.json"
    if not path.is_file():
        return None
    return RuleReport.model_validate_json(path.read_text(encoding="utf-8"))


def rules_table(reports: Mapping[str, RuleReport | None], plants: Sequence[PlantData]) -> Table:
    """Per scale and rule: places checked, violations and exceptions, summed over the plants."""
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for plant in plants:
        report = reports[plant.spec.plant_id]
        if report is None:
            continue
        for row in report.rows:
            cell = totals[(SCALE_LABELS[plant.spec.scale], row.rule_id)]
            cell[:] = [
                cell[0] + 1, cell[1] + row.checked, cell[2] + row.violations,
                cell[3] + sum(row.exceptions.values()),
            ]  # fmt: skip
    rows: list[list[TableCell]] = [[scale, rule, *c] for (scale, rule), c in sorted(totals.items())]
    return Table(
        name="rules", title="rules.json summaries (build-time rule checks, per scale)",
        header=["scale", "rule", "plants", "checked", "violations", "exceptions"], rows=rows,
    )  # fmt: skip


# ---- precision, recall and F1 -----------------------------------------------------------------


def rescore_path(root: Path, corpus_id: str, tier: str = "AG") -> Path:
    """Where END wrote the re-score of a corpus's `tier` run (`AG` agent, `CYP` Cypher)."""
    return root / "reports" / f"rescore_{tier}_{corpus_id}.json"


def read_rescore(root: Path, corpus_id: str, tier: str = "AG") -> RescoreReport | None:
    """END's re-score of the corpus's run of one tier, or `None` when END did not write one."""
    path = rescore_path(root, corpus_id, tier)
    if not path.is_file():
        return None
    return RescoreReport.model_validate_json(path.read_text(encoding="utf-8"))


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _a_id(plant: PlantData) -> str:
    return plant.spec.plant_id


def _b_id(plant: PlantData) -> str:
    return plant.spec.b_id


def prf_table(
    rescored: Mapping[str, RescoreReport | None], plants: Sequence[PlantData], *, b_sealed: bool
) -> Table:
    """Mean precision, recall and F1 of the list answers the agent tier gave, per arm and scale."""
    rows: list[list[TableCell]] = []
    arms: list[tuple[str, Callable[[PlantData], str]]] = [("V2T-A2", _a_id)]
    if b_sealed:
        arms.append(("V2T-B", _b_id))
    for arm, corpus_of in arms:
        for scale in (*SCALE_LABELS.values(), ALL_SCALES):
            mine = [p for p in plants if scale in (ALL_SCALES, SCALE_LABELS[p.spec.scale])]
            reports = [rescored[corpus_of(p)] for p in mine]
            scored = [
                row for r in reports if r is not None for row in r.rows if row.precision is not None
            ]
            rows.append(
                [
                    arm, scale, sum(r is not None for r in reports), len(scored),
                    _mean([r.precision for r in scored if r.precision is not None]),
                    _mean([r.recall for r in scored if r.recall is not None]),
                    _mean([r.f1 for r in scored if r.f1 is not None]),
                ]
            )  # fmt: skip
    return Table(
        name="precision_recall", title="Precision, recall and F1 of list answers (agent tier)",
        note="from END's offline re-score of the saved answers; list answers only",
        header=["arm", "scale", "plants re-scored", "list answers", "precision", "recall", "F1"],
        rows=rows,
    )  # fmt: skip


# ---- the cascade's final answers ---------------------------------------------------------------

#: the re-scored rows picked, and how many final answers each tier (`CYP`, `AG`) gave
FinalRows = tuple[list[RowScore], dict[str, int]]


def final_answer_rows(
    evaluation: Evaluation, by_tier: Mapping[str, RescoreReport | None]
) -> FinalRows:
    """Each question's re-scored row from the tier that answered it, and how many came from each.

    `by_tier` maps `CYP` and `AG` to that tier's re-score. A question nobody answered, or whose
    tier has no re-scored row, is left out.
    """
    rows_of = {
        tier: {r.question_id: r for r in report.rows} if report else {}
        for tier, report in by_tier.items()
    }
    picked: list[RowScore] = []
    counts = {tier: 0 for tier in by_tier}
    for scored in evaluation.scored:
        decision = scored.decision
        tier = TIER_RUNS.get(decision.answered_by or "")
        row = rows_of.get(tier or "", {}).get(decision.question_id)
        if tier is not None and row is not None:
            picked.append(row)
            counts[tier] += 1
    return picked, counts


def _arm_evaluation(plant: PlantData, arm: str) -> Evaluation | None:
    """The evaluation of the policy the arm's claims read (A2: `cascade_v4_iso`, B: its twin)."""
    if arm == "V2T-A2":
        return plant.a2.evaluations[A2_PRIMARY]
    return plant.b.evaluations[policy_b().name] if plant.b else None


def prf_final_table(
    rescored: Mapping[tuple[str, str], RescoreReport | None],
    plants: Sequence[PlantData],
    *,
    b_sealed: bool,
) -> Table:
    """Mean precision, recall and F1 over the cascade's final list answers, per arm and scale.

    A plant counts only when both tiers were re-scored, because a final answer may come from either.
    """
    rows: list[list[TableCell]] = []
    arms: list[tuple[str, Callable[[PlantData], str]]] = [("V2T-A2", _a_id)]
    if b_sealed:
        arms.append(("V2T-B", _b_id))
    for arm, corpus_of in arms:
        for scale in (*SCALE_LABELS.values(), ALL_SCALES):
            mine = [p for p in plants if scale in (ALL_SCALES, SCALE_LABELS[p.spec.scale])]
            picked: list[RowScore] = []
            from_tier = {"CYP": 0, "AG": 0}
            complete = 0
            for plant in mine:
                by_tier = {t: rescored[(corpus_of(plant), t)] for t in from_tier}
                evaluation = _arm_evaluation(plant, arm)
                if evaluation is None or any(r is None for r in by_tier.values()):
                    continue
                complete += 1
                plant_rows, counts = final_answer_rows(evaluation, by_tier)
                picked += [r for r in plant_rows if r.precision is not None]
                from_tier = {t: n + counts[t] for t, n in from_tier.items()}
            rows.append(
                [
                    arm, scale, complete, len(picked), from_tier["CYP"], from_tier["AG"],
                    _mean([r.precision for r in picked if r.precision is not None]),
                    _mean([r.recall for r in picked if r.recall is not None]),
                    _mean([r.f1 for r in picked if r.f1 is not None]),
                ]
            )  # fmt: skip
    return Table(
        name="precision_recall_final",
        title="Precision, recall and F1 of list answers: the cascade's final answers",
        note=(
            "each question is scored from the tier that answered it; 'from Cypher' and 'from "
            "agent' count all final answers of that tier (list answers or not)"
        ),
        header=[
            "arm", "scale", "plants re-scored (both tiers)", "list answers", "from Cypher",
            "from agent", "precision", "recall", "F1",
        ],
        rows=rows,
    )  # fmt: skip
