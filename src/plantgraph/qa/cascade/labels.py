"""The need label of a question: what shape of evidence it asks for (e.g. a flow PATH).

Labels are free and deterministic: the rules classifier reads only the question text and the
tags / units found in it. The need-aware run already recorded that label in its trace, so
the join reuses it; the classifier is run here only for a question no run labelled.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.qa.anchors import Anchors
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
