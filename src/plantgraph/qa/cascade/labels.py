"""The need label of a question: what shape of evidence it asks for (e.g. a flow PATH).

Labels are free and deterministic: the rules classifier reads only the question text and the
tags / units found in it. The need-aware run already recorded that label in its trace, so
the join reuses it; the classifier is run here only for a question no run labelled.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from plantgraph.qa.anchors import Anchors
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import QuestionResult
from plantgraph.qa.need.classifiers import build_need_input
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.need.rules import RuleNeedClassifier

#: Finds the tags and units a question names; needs the corpus graph, so the caller supplies it.
AnchorFinder = Callable[[str], Anchors]


def classify_need(question_text: str, find_anchors: AnchorFinder) -> NeedLabel:
    """The rules label of one question."""
    need_input = build_need_input(question_text, find_anchors(question_text))
    return RuleNeedClassifier().classify(need_input).label


def label_from_trace(row: QuestionResult) -> NeedLabel | None:
    """The label a need-aware run wrote into its trace; `None` for any other strategy."""
    retrieval = row.trace.get("retrieval")
    if not isinstance(retrieval, dict):
        return None
    value = retrieval.get("need_label")
    return NeedLabel(value) if isinstance(value, str) else None


def labels_from_run_dirs(run_dirs: Iterable[Path]) -> dict[str, NeedLabel]:
    """Every trace label found in these runs' rows, whatever tier they belong to.

    A policy whose own tiers record no label (the agent tier) can still route by the label a
    need-aware run of the same questions wrote; the first run to label a question wins.
    """
    labels: dict[str, NeedLabel] = {}
    for run_dir in run_dirs:
        for row in RunDir(run_dir).read_rows():
            label = label_from_trace(row)
            if label is not None:
                labels.setdefault(row.question_id, label)
    return labels
