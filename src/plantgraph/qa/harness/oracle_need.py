"""The oracle need classifier: the gold label, looked up by question text (design §4.2).

It separates a classifier miss from a program miss: with the right label, whatever is still
lost is the program's or the budget's fault. It reads the answer key (`need_gold`), so it
lives on the harness side and is for free analysis only; `qa/strategies/` and `qa/need/`
never import it.
"""

from __future__ import annotations

from collections.abc import Iterable

from plantgraph.qa.harness.need_gold import gold_need_of
from plantgraph.qa.models import Question
from plantgraph.qa.need.classifiers import NeedDecision, NeedInput
from plantgraph.qa.need.labels import NeedLabel


class OracleNeedClassifier:
    """Answers with the gold label of the question whose text it is given; confidence 1.0."""

    name = "oracle"

    def __init__(self, label_of_text: dict[str, NeedLabel]) -> None:
        self._label_of_text = label_of_text

    @classmethod
    def from_questions(cls, questions: Iterable[Question]) -> OracleNeedClassifier:
        """Index the questions' gold labels by text.

        Raises:
            ValueError: one text has two different gold labels (the lookup would be ambiguous),
                or a question's family has no gold label.
        """
        label_of_text: dict[str, NeedLabel] = {}
        for question in questions:
            label = _single_label(question)
            known = label_of_text.setdefault(question.text, label)
            if known is not label:
                raise ValueError(
                    f"expected one gold need label per question text, found {known.value} "
                    f"and {label.value} for {question.text!r}"
                )
        return cls(label_of_text)

    def classify(self, need_input: NeedInput) -> NeedDecision:
        """The gold label of `need_input.text`.

        Raises:
            ValueError: the text is not one of the indexed questions.
        """
        label = self._label_of_text.get(need_input.text)
        if label is None:
            raise ValueError(
                f"expected a question text the oracle knows, found {need_input.text!r}"
            )
        return NeedDecision(label=label, score=1.0, classifier=self.name)


def _single_label(question: Question) -> NeedLabel:
    """A question's one gold label (the sets are singletons per question, `need_gold`)."""
    labels = gold_need_of(question)
    if len(labels) != 1:
        raise ValueError(
            f"expected exactly one gold need label for {question.question_id}, "
            f"found {sorted(label.value for label in labels)}"
        )
    return next(iter(labels))
