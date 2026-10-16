"""Presentation mode on the server: the configured sequences, resolved against the loaded plants.

A sequence is a short talk bound to one plant. Its example steps name questions by id; here each id
is turned into the example's own text, so the page asks exactly what the examples file says.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from plantgraph.demo.app.api_models import (
    PresentationItem,
    PresentationSequenceView,
    PresentationView,
)
from plantgraph.demo.app.config import DemoConfig, PresentationSequence, PresentationStep
from plantgraph.demo.app.state import AppState, CorpusNotReady

Missing = Literal["unknown_question", "corpus_not_ready"]
#: A plant's example texts by question id, or `None` while the plant is not loaded.
ExampleTexts = Callable[[str], dict[str, str] | None]


def example_texts_of(state: AppState) -> ExampleTexts:
    """The lookup over a live `AppState`: only a loaded plant has example texts."""

    def texts(corpus_id: str) -> dict[str, str] | None:
        try:
            questions = state.ready_corpus(corpus_id).questions
        except CorpusNotReady:
            return None
        return {question_id: q.text for question_id, q in questions.items()}

    return texts


def presentation_view(config: DemoConfig, example_texts: ExampleTexts) -> PresentationView:
    """Every configured sequence with each step resolved; an unresolvable step is marked."""
    return PresentationView(
        sequences=tuple(_sequence_view(s, example_texts) for s in config.presentation)
    )


def _sequence_view(
    sequence: PresentationSequence, example_texts: ExampleTexts
) -> PresentationSequenceView:
    texts = example_texts(sequence.corpus_id)  # read once: the same plant serves every step
    items = tuple(_item(i, step, texts) for i, step in enumerate(sequence.steps))
    return PresentationSequenceView(corpus_id=sequence.corpus_id, title=sequence.title, items=items)


def _item(index: int, step: PresentationStep, texts: dict[str, str] | None) -> PresentationItem:
    if step.kind == "results":  # the Results tab needs no plant
        return PresentationItem(
            index=index, kind="results", question_id=None, text=None, missing=None
        )
    if texts is None:
        return _example(index, step, text=None, missing="corpus_not_ready")
    text = texts.get(step.question_id or "")
    if text is None:
        return _example(index, step, text=None, missing="unknown_question")
    return _example(index, step, text=text, missing=None)


def _example(
    index: int, step: PresentationStep, *, text: str | None, missing: Missing | None
) -> PresentationItem:
    return PresentationItem(
        index=index, kind="example", question_id=step.question_id, text=text, missing=missing
    )
