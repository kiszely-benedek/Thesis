"""The gold need label of every dev family: what evidence shape its question calls for.

Gold side: strategies and `qa/need/` must never import this (design `question-aware-retrieval.md`
§4.2, §13 import ban), or the "oracle" classifier would be an answer key leaking into retrieval.

The label follows the evidence the question's reference function reads, not its wording:
`LOOP_ACTUATED_VALVE` reads a signal chain, `COUNT_IN_UNIT` reads a whole unit, and so on.
`UNANSWERABLE_TAG` reuses three templates, so its label depends on which template it wraps.
"""

from __future__ import annotations

from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.need.labels import NeedLabel

#: The single acceptable label of every family that is not `UNANSWERABLE_TAG`.
_FAMILY_NEED: dict[QuestionFamily, NeedLabel] = {
    QuestionFamily.LOOKUP_TYPE: NeedLabel.ITEM,
    QuestionFamily.LOOKUP_UNIT: NeedLabel.ITEM,
    QuestionFamily.NEIGHBOURS_DOWNSTREAM: NeedLabel.NEIGHBOURS_DOWNSTREAM,
    QuestionFamily.LOOP_ACTUATED_VALVE: NeedLabel.SIGNAL_CHAIN,
    QuestionFamily.LOOP_MEASURED_EQUIPMENT: NeedLabel.SIGNAL_CHAIN,
    QuestionFamily.FLOW_PATH: NeedLabel.PATH,
    QuestionFamily.UPSTREAM_ISOLATION: NeedLabel.UPSTREAM_TO_FIRST_VALVE,
    QuestionFamily.CROSS_UNIT: NeedLabel.UNIT_SCOPE,
    QuestionFamily.COUNT_IN_UNIT: NeedLabel.UNIT_SCOPE,
    QuestionFamily.NO_PATH: NeedLabel.PATH,
    QuestionFamily.SHEETS_OF_TAG: NeedLabel.ITEM,
    # dev-new (§8.2)
    QuestionFamily.CONNECTED: NeedLabel.PATH,
    QuestionFamily.DOWNSTREAM_IN_UNIT: NeedLabel.DOWNSTREAM_ALL,
    QuestionFamily.INSTRUMENTS_OF_ITEM: NeedLabel.SIGNAL_CHAIN,
    QuestionFamily.UPSTREAM_SOURCES: NeedLabel.UPSTREAM_ALL,
    QuestionFamily.SAME_UNIT: NeedLabel.ITEM,
    QuestionFamily.LOOPS_NEAR_ITEM: NeedLabel.GENERIC,  # a composite no single shape covers
}

#: `UNANSWERABLE_TAG` wraps these templates (`families_abstain.py`), keyed by `template_id`.
_UNANSWERABLE_TEMPLATE_NEED: dict[str, NeedLabel] = {
    "LOOKUP_TYPE": NeedLabel.ITEM,
    "NEIGHBOURS_DOWNSTREAM": NeedLabel.NEIGHBOURS_DOWNSTREAM,
    "FLOW_PATH": NeedLabel.PATH,
}


def gold_need_of_family(family: QuestionFamily) -> frozenset[NeedLabel]:
    """The acceptable labels for any question of `family`.

    Raises:
        ValueError: `family` has no gold label (a family added without one).
    """
    if family is QuestionFamily.UNANSWERABLE_TAG:
        return frozenset(_UNANSWERABLE_TEMPLATE_NEED.values())
    if family not in _FAMILY_NEED:
        raise ValueError(f"expected a gold need label for {family.value}, found none")
    return frozenset({_FAMILY_NEED[family]})


def gold_need_of(question: Question) -> frozenset[NeedLabel]:
    """The acceptable labels for one question; exact for `UNANSWERABLE_TAG`, by its template.

    Raises:
        ValueError: the question's family or (for `UNANSWERABLE_TAG`) template has no label.
    """
    if question.family is not QuestionFamily.UNANSWERABLE_TAG:
        return gold_need_of_family(question.family)
    if question.template_id not in _UNANSWERABLE_TEMPLATE_NEED:
        raise ValueError(
            f"expected an UNANSWERABLE_TAG template in {sorted(_UNANSWERABLE_TEMPLATE_NEED)}, "
            f"found {question.template_id!r}"
        )
    return frozenset({_UNANSWERABLE_TEMPLATE_NEED[question.template_id]})
