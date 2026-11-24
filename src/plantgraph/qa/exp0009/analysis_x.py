"""Scope X in numbers: refused shares, sub-scopes, POSITION_OF_VALVE beside its two baselines.

Scope X is the five question families that need valve **positions** (which valves are normally
open) or valves that print no tag. A candidate question is **refused** when its gold answer would
name an untagged valve that no unique description can pick out, or when the gold is empty. A
POSITION question names its valve by its **tag** or, for an untagged valve, by a **descriptor**
(valve class, line number, side, neighbour). The code is the valve's normal position: NO and NC
(normally open, closed), LO and LC (locked), CSO and CSC (car-sealed).

Two baselines say how much the question text gives away: the **majority** code, and the **text
prior** (the commonest code for the question's text key). B's accuracy is read against them.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.exp0009.analysis_claims import SCALE_LABELS
from plantgraph.qa.exp0009.analysis_load import A2_PRIMARY, PlantData
from plantgraph.qa.exp0009.analysis_models import Table, TableCell
from plantgraph.qa.exp0009.analysis_scope import X_FAMILIES, stripped_id
from plantgraph.qa.exp0009.scope_x_report import FamilyReport
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.scope_x_models import QuestionFlags
from plantgraph.qa.v2tb.policy_b import B_POLICY_NAME

SCOPE_REPORT_FILE, BASELINES_FILE = "scope_report.json", "position_baselines.jsonl"
ALL_SCALES = "both scales"
_OPEN_VALVES = (
    QuestionFamily.OPEN_VALVES_TO_ISOLATE,
    QuestionFamily.OPEN_VALVES_TO_ISOLATE_DOWNSTREAM,
)


class BaselineRow(BaseModel):
    """One POSITION question: its form, the gold code and what each baseline would answer."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    named_by: str
    gold: str
    majority: str
    text_prior: str


# ---- reading the files -----------------------------------------------------------------------


def read_scope_report(root: Path, plant: PlantData) -> list[FamilyReport]:
    """The per-family counts of scope X on one plant (`questions/<A id>/scope_report.json`)."""
    path = root / "questions" / plant.spec.plant_id / SCOPE_REPORT_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    return [FamilyReport.model_validate(entry) for entry in document["scope_x"]]


def read_baselines(root: Path, plant: PlantData) -> list[BaselineRow]:
    """The POSITION baseline rows of one plant (`questions/<B id>/position_baselines.jsonl`)."""
    path = root / "questions" / plant.spec.b_id / BASELINES_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    return [BaselineRow.model_validate_json(line) for line in lines if line.strip()]


def read_flags(root: Path, plant: PlantData) -> dict[str, QuestionFlags] | None:
    """The per-question flags of scope X (`qpool/<A id>/scope_x/flags.json`), `None` if absent."""
    path = root / "qpool" / plant.spec.plant_id / "scope_x" / "flags.json"
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    return {qid: QuestionFlags.model_validate(flags) for qid, flags in document.items()}


# ---- refused shares ---------------------------------------------------------------------------


def refused_table(
    reports: Mapping[str, Sequence[FamilyReport]], plants: Sequence[PlantData]
) -> Table:
    """Candidates and refusals per scale and X family, summed over the scale's plants."""
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for plant in plants:
        for report in reports[plant.spec.plant_id]:
            cell = totals[(SCALE_LABELS[plant.spec.scale], report.family.value)]
            cell[:] = [
                cell[0] + report.candidates,
                cell[1] + report.refused_no_descriptor,
                cell[2] + report.refused_empty_gold,
                cell[3] + report.kept,
            ]
    rows: list[list[TableCell]] = [
        [scale, family, c[0], c[1], c[2], _share(c[1] + c[2], c[0]), c[3]]
        for (scale, family), c in sorted(totals.items())
    ]
    return Table(
        name="x_refused", title="Scope X: candidates and refused shares",
        note="refused = no unique descriptor for an untagged valve, or an empty gold answer",
        header=["scale", "family", "candidates", "no descriptor", "empty gold", "refused", "kept"],
        rows=rows,
    )  # fmt: skip


def _share(part: float, whole: float) -> float | None:
    return part / whole if whole else None


# ---- one row per sampled X question ----------------------------------------------------------


@dataclass(frozen=True)
class XQuestion:
    """A sampled scope X question with both arms' acc@C (1.0 or 0.0; `None` = arm did not ask)."""

    scale: str
    family: QuestionFamily
    b_ok: float | None
    a2_ok: float | None
    untagged_gold: bool | None
    discriminating: bool | None


def _flags_by_stripped_id(plant: PlantData, policy: str, *, b: bool) -> dict[str, float]:
    arm = plant.b if b else plant.a2
    if arm is None:
        return {}
    scored = arm.evaluations[policy].scored
    return {stripped_id(s.decision.question_id): float(s.correct_at_cutoff) for s in scored}


def x_questions(
    plants: Sequence[PlantData], flags: Mapping[str, Mapping[str, QuestionFlags] | None]
) -> list[XQuestion]:
    """Every X question of B's file, with each arm's result and its flags when `qpool` has them."""
    rows = []
    for plant in plants:
        b_ok = _flags_by_stripped_id(plant, B_POLICY_NAME, b=True)
        a2_ok = _flags_by_stripped_id(plant, A2_PRIMARY, b=False)
        own = flags[plant.spec.plant_id]
        for q in (q for q in plant.b_questions if q.family in X_FAMILIES):
            key = stripped_id(q.question_id)
            found = None if own is None else own.get(f"{plant.spec.plant_id}:{key}")
            rows.append(
                XQuestion(
                    scale=SCALE_LABELS[plant.spec.scale], family=q.family,
                    b_ok=b_ok.get(key), a2_ok=a2_ok.get(key),
                    untagged_gold=None if found is None else found.holds_untagged,
                    discriminating=None if found is None else found.differs_from_topological,
                )
            )  # fmt: skip
    return rows


def _mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def subscope_table(rows: Sequence[XQuestion]) -> Table:
    """Accuracy of each arm on the sub-scopes of X: untagged gold or not, discriminating or not.

    A question holds **untagged gold** when its gold answer names an untagged valve. A question is
    **discriminating** (the two OPEN_VALVES families only) when its gold differs from the purely
    topological answer, so only a system that reads valve positions can get it right.
    """
    groups: list[tuple[str, list[XQuestion]]] = [
        ("untagged gold", [r for r in rows if r.untagged_gold is True]),
        ("tagged gold only", [r for r in rows if r.untagged_gold is False]),
        ("discriminating", [r for r in rows if r.discriminating is True]),
        ("not discriminating", [r for r in rows if r.discriminating is False]),
    ]
    table_rows: list[list[TableCell]] = []
    for scale in (*SCALE_LABELS.values(), ALL_SCALES):
        for name, members in groups:
            mine = [r for r in members if scale in (ALL_SCALES, r.scale)]
            table_rows.append(
                [
                    scale,
                    name,
                    len(mine),
                    _mean([r.b_ok for r in mine]),
                    _mean([r.a2_ok for r in mine]),
                ]
            )
    return Table(
        name="x_subscopes", title="Scope X sub-scopes (acc@C)",
        note=(
            "B asked every X question, A2 only the isolation families. The flags come from "
            "qpool/<plant>/scope_x/flags.json; a question without flags is in no sub-scope."
        ),
        header=["scale", "sub-scope", "questions", "B acc@C", "A2 acc@C"], rows=table_rows,
    )  # fmt: skip


def family_table(rows: Sequence[XQuestion]) -> Table:
    """Accuracy of each arm per X family and scale, with the discriminating share."""
    table_rows: list[list[TableCell]] = []
    for family in sorted(X_FAMILIES, key=lambda f: f.value):
        for scale in (*SCALE_LABELS.values(), ALL_SCALES):
            mine = [r for r in rows if r.family is family and scale in (ALL_SCALES, r.scale)]
            flagged = [r for r in mine if r.discriminating is not None]
            table_rows.append(
                [
                    family.value, scale, len(mine), _mean([r.b_ok for r in mine]),
                    _mean([r.a2_ok for r in mine]),
                    _share(sum(r.discriminating is True for r in flagged), len(flagged)),
                ]
            )  # fmt: skip
    return Table(
        name="x_families", title="Scope X per family (acc@C)",
        header=["family", "scale", "questions", "B acc@C", "A2 acc@C", "discriminating share"],
        rows=table_rows,
    )  # fmt: skip


# ---- POSITION_OF_VALVE beside the baselines --------------------------------------------------


@dataclass(frozen=True)
class PositionRow:
    """One POSITION question: its baseline row, and B's acc@C on it (`None` if B did not run)."""

    baseline: BaselineRow
    b_ok: float | None


def _position_groups(rows: Sequence[PositionRow]) -> dict[str, list[PositionRow]]:
    """Group name -> its rows: the two forms first, then each gold code."""
    groups: dict[str, list[PositionRow]] = {}
    for row in rows:
        groups.setdefault(f"form: {row.baseline.named_by}", []).append(row)
    for row in rows:
        groups.setdefault(f"code: {row.baseline.gold}", []).append(row)
    return dict(sorted(groups.items(), key=lambda item: (item[0].startswith("code"), item[0])))


def _position_rows(plant: PlantData, baselines: Sequence[BaselineRow]) -> list[PositionRow]:
    b_ok = _flags_by_stripped_id(plant, B_POLICY_NAME, b=True)
    return [PositionRow(row, b_ok.get(stripped_id(row.question_id))) for row in baselines]


def position_table(
    plants: Sequence[PlantData], baselines: Mapping[str, Sequence[BaselineRow]]
) -> Table:
    """POSITION accuracy of B by form and by gold code, beside the majority and the text prior."""
    table_rows: list[list[TableCell]] = []
    for scale in (*SCALE_LABELS.values(), ALL_SCALES):
        rows = [
            row
            for plant in plants
            if scale in (ALL_SCALES, SCALE_LABELS[plant.spec.scale])
            for row in _position_rows(plant, baselines[plant.spec.plant_id])
        ]
        for name, group in _position_groups(rows).items():
            n = len(group)
            majority_hits = sum(r.baseline.majority == r.baseline.gold for r in group)
            prior_hits = sum(r.baseline.text_prior == r.baseline.gold for r in group)
            table_rows.append(
                [scale, name, n, _mean([r.b_ok for r in group]), majority_hits / n, prior_hits / n]
            )
    return Table(
        name="position", title="POSITION_OF_VALVE: B beside the majority and the text prior",
        note="all three columns are shares of the same questions; B is acc@C",
        header=["scale", "group", "questions", "B acc@C", "majority", "text prior"],
        rows=table_rows,
    )  # fmt: skip


def named_by_table(
    plants: Sequence[PlantData], baselines: Mapping[str, Sequence[BaselineRow]]
) -> Table:
    """The realized mix of POSITION questions by form (tag or descriptor), per scale."""
    table_rows: list[list[TableCell]] = []
    for scale in (*SCALE_LABELS.values(), ALL_SCALES):
        mine = [
            r
            for p in plants
            if scale in (ALL_SCALES, SCALE_LABELS[p.spec.scale])
            for r in baselines[p.spec.plant_id]
        ]
        by_tag = sum(r.named_by == "tag" for r in mine)
        table_rows.append([scale, len(mine), by_tag, len(mine) - by_tag, _share(by_tag, len(mine))])
    return Table(
        name="named_by", title="Realized named_by mix of the POSITION questions",
        header=["scale", "questions", "by tag", "by descriptor", "tag share"], rows=table_rows,
    )  # fmt: skip
