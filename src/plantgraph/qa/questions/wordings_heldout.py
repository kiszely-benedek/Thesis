"""Held-out wordings: a dev question asked again in different words (EXP-0006, ADR-0035).

A reworded question keeps everything about its source (reference, evidence, `k`, `u`,
anchors, family). Only three fields change: the text, the `template_id` (the dev id plus
`_P1`) and the `question_id`, which now carries the template id so that the reworded
question and the dev question about the same anchors never collide.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions import templates_heldout as t
from plantgraph.qa.questions.families_aggregate import class_plural

_WORDING_SUFFIX = "_P1"

#: Anchors of the source question -> the held-out text. Anchor order is each family's own.
_TEXT_FROM_ANCHORS: dict[QuestionFamily, Callable[[list[str]], str]] = {
    QuestionFamily.LOOKUP_TYPE: lambda a: t.lookup_type_p1_text(a[0]),
    QuestionFamily.LOOKUP_UNIT: lambda a: t.lookup_unit_p1_text(a[0]),
    QuestionFamily.NEIGHBOURS_DOWNSTREAM: lambda a: t.neighbours_downstream_p1_text(a[0]),
    QuestionFamily.LOOP_ACTUATED_VALVE: lambda a: t.loop_actuated_valve_p1_text(a[0]),
    QuestionFamily.LOOP_MEASURED_EQUIPMENT: lambda a: t.loop_measured_equipment_p1_text(a[0]),
    QuestionFamily.FLOW_PATH: lambda a: t.flow_path_p1_text(a[0], a[1]),
    QuestionFamily.UPSTREAM_ISOLATION: lambda a: t.upstream_isolation_p1_text(a[0]),
    QuestionFamily.CROSS_UNIT: lambda a: t.cross_unit_p1_text(a[0]),
    # COUNT_IN_UNIT anchors are [unit_id, node_class]
    QuestionFamily.COUNT_IN_UNIT: lambda a: t.count_in_unit_p1_text(class_plural(a[1]), a[0]),
    QuestionFamily.SHEETS_OF_TAG: lambda a: t.sheets_of_tag_p1_text(a[0]),
}

#: The families that have a held-out wording, in a fixed order.
WORDING_FAMILIES: tuple[QuestionFamily, ...] = tuple(_TEXT_FROM_ANCHORS)


def reword(question: Question) -> Question:
    """The held-out wording of `question`; everything but text, template and id is kept.

    Raises:
        ValueError: the family has no held-out wording.
    """
    make_text = _TEXT_FROM_ANCHORS.get(question.family)
    if make_text is None:
        raise ValueError(
            f"expected a family with a held-out wording {[f.value for f in WORDING_FAMILIES]}, "
            f"found {question.family.value}"
        )
    template_id = question.template_id + _WORDING_SUFFIX
    anchors = "|".join(question.anchors)
    return question.model_copy(
        update={
            "text": make_text(question.anchors),
            "template_id": template_id,
            "question_id": f"{question.corpus_id}:{question.family.value}:{template_id}:{anchors}",
        }
    )
