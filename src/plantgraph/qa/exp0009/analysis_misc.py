"""The other descriptive tables: network-touching shares, `rules.json` summaries, precision/recall.

- **Network-touching.** A *network* is a pipe system the whole plant shares (flare header, closed
  drain): v2.2 draws it on its own sheets, and its items live in unit numbers from 9000 up. A
  question *touches a network* when one of its gold evidence tags belongs to such a unit.
- **`rules.json`.** The build-time report of the handbook rules a plant was generated under: per
  rule, how many places were checked and how many broke it.
- **Precision, recall, F1.** For a list answer (a set of tags or valves) correctness is all or
  nothing, so these say how close a wrong list was. They come from END's offline re-score
  (`reports/rescore_AG_<plant>.json`), which re-scores the saved answers of the **agent tier**
  with no model call; the Cypher tier is not re-scored by END.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from plantgraph.benchmark.v2.network_models import is_network_unit_no
from plantgraph.benchmark.v2.rules.registry import RuleReport
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.qa.exp0009.analysis_claims import SCALE_LABELS
from plantgraph.qa.exp0009.analysis_load import PlantData
from plantgraph.qa.exp0009.analysis_models import Table, TableCell
from plantgraph.qa.exp0009.analysis_scope import X_FAMILIES, r_headline_ids
from plantgraph.qa.exp0009.analysis_x import ALL_SCALES
from plantgraph.qa.exp0009.records import RescoreReport
from plantgraph.qa.models import Question


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


def rescore_path(root: Path, corpus_id: str) -> Path:
    """Where END wrote the agent-tier re-score of a corpus."""
    return root / "reports" / f"rescore_AG_{corpus_id}.json"


def read_rescore(root: Path, corpus_id: str) -> RescoreReport | None:
    """END's re-score of the corpus's agent runs, or `None` when END did not write one."""
    path = rescore_path(root, corpus_id)
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
    """Mean precision, recall and F1 of the list answers, per arm and scale (agent tier)."""
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
