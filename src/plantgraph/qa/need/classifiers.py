"""The classifier interface: question text in, one need label out (design §4.2).

A classifier sees only what a reader of the question sees: the text, the text with its tags
and units hidden, and how many of each the question names. Rules, a label-probability model
and a Jev `choice` call are interchangeable behind `NeedClassifier`; so is the oracle, but
that one lives on the harness side because it reads the answer key.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.anchors import Anchors, mask_anchors
from plantgraph.qa.need.labels import NeedLabel


class NeedInput(BaseModel):
    """What a classifier may read; built from the question text and the anchors found in it."""

    model_config = ConfigDict(frozen=True)

    text: str
    #: `text` with every tag written `<TAG>` and every unit id `<UNIT>`.
    masked_text: str
    n_tag_anchors: int
    n_unit_anchors: int


class NeedDecision(BaseModel):
    """One classification: the label, and how sure the classifier is when it can say."""

    model_config = ConfigDict(frozen=True)

    label: NeedLabel
    #: Probability of `label`; `None` for a classifier that gives no confidence (rules).
    score: float | None = None
    #: Probability of every label, when the classifier gives them.
    scores: dict[str, float] | None = None
    classifier: str
    #: Usage of the classifier's own model call, for the trace; `None` when it made none.
    call: dict[str, Any] | None = None


class NeedClassifier(Protocol):
    """Anything that maps a `NeedInput` to a `NeedDecision`."""

    #: Short name, recorded in the trace and in the strategy's name (`hierarchical_need_<name>`).
    name: str

    def classify(self, need_input: NeedInput) -> NeedDecision:
        """Pick the label for one question."""
        ...


def build_need_input(question_text: str, anchors: Anchors) -> NeedInput:
    """The classifier's view of a question."""
    return NeedInput(
        text=question_text,
        masked_text=mask_anchors(question_text, anchors),
        n_tag_anchors=len(anchors.tags),
        n_unit_anchors=len(anchors.units),
    )
