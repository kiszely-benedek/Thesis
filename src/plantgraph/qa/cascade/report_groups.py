"""Breakdowns of correct answers by need label, family and k-bin (evaluation-only columns)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from plantgraph.qa.cascade.evaluate import Evaluation
from plantgraph.qa.cascade.report_models import Cell
from plantgraph.qa.models import Question
from plantgraph.qa.need.labels import NeedLabel

DIM_LABEL = "need label"
DIM_FAMILY = "family"
DIM_K = "k bin"
#: Display order of the k bins; the other dimensions sort alphabetically.
K_BIN_ORDER = ("k=0", "k=1-2", "k>=3", "unanswerable")
UNLABELLED = "(no label)"


def k_bin(k: int | None) -> str:
    """The cross-sheet difficulty bin; `k` is `None` for an unanswerable question."""
    if k is None:
        return "unanswerable"
    if k == 0:
        return "k=0"
    return "k=1-2" if k <= 2 else "k>=3"


def question_groups(
    questions: Sequence[Question], need_labels: Mapping[str, NeedLabel]
) -> dict[str, dict[str, str]]:
    """Dimension -> question id -> group name."""
    return {
        DIM_LABEL: {
            q.question_id: need_labels[q.question_id].value
            if q.question_id in need_labels
            else UNLABELLED
            for q in questions
        },
        DIM_FAMILY: {q.question_id: q.family.value for q in questions},
        DIM_K: {q.question_id: k_bin(q.k) for q in questions},
    }


def breakdown(
    evaluations: Mapping[str, Evaluation], group_of: Mapping[str, str], dimension: str
) -> dict[str, dict[str, Cell]]:
    """Group -> policy -> cell, for the policies in `evaluations`."""
    counts: dict[str, dict[str, list[int]]] = {}
    for policy, evaluation in evaluations.items():
        for scored in evaluation.scored:
            group = group_of[scored.decision.question_id]
            cell = counts.setdefault(group, {}).setdefault(policy, [0, 0])
            cell[0] += scored.correct
            cell[1] += 1
    ordered = sorted(counts, key=lambda g: _sort_key(dimension, g))
    return {
        group: {p: Cell(correct=c, total=n) for p, (c, n) in counts[group].items()}
        for group in ordered
    }


def _sort_key(dimension: str, group: str) -> tuple[int, str]:
    if dimension == DIM_K:
        return (K_BIN_ORDER.index(group), group)
    return (0, group)
