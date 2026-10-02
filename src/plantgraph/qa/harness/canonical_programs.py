"""One fixed program of plant-API primitives per dev family: the API-02 expressiveness check.

Design `question-aware-retrieval.md` §3.4. A *canonical program* answers a family's question with
no model, by calling the six primitives in a fixed order. Comparing its output with the family's
reference function (computed from the ground-truth plant) measures how much of the family the
API can express. It is also a free "perfect planner" upper bound for the agent arms.

Gold side: a program reads the question's `anchors` (the tags and unit it names), which only the
harness may see; `qa/plant_api/` imports nothing from here. Programs run on a `PlantApi` built
with a very large `max_items`, so a result is never cut: this measures what the primitives can
compute, while rendering limits are a separate matter.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.qa.models import AnswerValue, Question, QuestionFamily
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import ItemFilter, ItemRecord
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import Subgraph

#: A program takes a fresh API session and a question; it returns an answer (`None`: not present).
CanonicalProgram = Callable[[PlantApi, Question], AnswerValue]

_NO_LIMIT = 10_000_000
#: Class-chain labels from `graph.schema`: every valve is a `PipingComponent`.
_VALVE = "PipingComponent"
_EQUIPMENT = "Equipment"
_OPERATED_VALVE = "OperatedValve"


def run_canonical_program(graph: ItemGraph, question: Question) -> AnswerValue:
    """Run the family's program on a fresh `PlantApi` session over `graph`.

    Raises:
        PlantApiError: a primitive rejected a call (the caller counts this as a failed program).
        KeyError: the family has no program.
    """
    return PROGRAMS[question.family](PlantApi(graph, max_items=_NO_LIMIT), question)


# --- small helpers over results ---------------------------------------------------------------


def _tags_where(sub: Subgraph, label: str | None = None) -> list[str]:
    """Sorted tags of a walk's members, optionally only those carrying `label`."""
    return sorted(
        m.item.tag
        for m in sub.members
        if m.item.tag is not None and (label is None or label in m.item.labels)
    )


def _single(tags: list[str]) -> str | None:
    """The one tag, or `None` when the program found zero or several (a mismatch, not a crash)."""
    return tags[0] if len(tags) == 1 else None


def _find(api: PlantApi, tag: str) -> list[ItemRecord]:
    return list(api.find(ItemFilter(tag=tag), limit=_NO_LIMIT).items)


def _units_of(sub: Subgraph) -> list[str]:
    return sorted({m.item.unit_id for m in sub.members if m.item.unit_id is not None})


# --- dev-old families ------------------------------------------------------------------------


def _lookup_type(api: PlantApi, question: Question) -> AnswerValue:
    found = _find(api, question.anchors[0])
    return found[0].node_class if found else None


def _lookup_unit(api: PlantApi, question: Question) -> AnswerValue:
    found = _find(api, question.anchors[0])
    return found[0].unit_id if found else None


def _neighbours_downstream(api: PlantApi, question: Question) -> AnswerValue:
    return _tags_where(api.neighbours(question.anchors[0], "downstream", "flow"))


def _loop_actuated_valve(api: PlantApi, question: Question) -> AnswerValue:
    # controller -send_signal_to-> actuator -control-> valve: two signal hops
    sub = api.traverse(question.anchors[0], "downstream", "signal", max_hops=2)
    return _single(_tags_where(sub, _VALVE))


def _loop_measured_equipment(api: PlantApi, question: Question) -> AnswerValue:
    # equipment -measured_by-> sensor -send_signal_to-> controller, read backwards
    sub = api.traverse(question.anchors[0], "upstream", "signal", max_hops=2)
    return _single(_tags_where(sub, _EQUIPMENT))


def _flow_path(api: PlantApi, question: Question) -> AnswerValue:
    path = api.path(question.anchors[0], question.anchors[1])
    return [item.tag for item in path.items if item.tag is not None] if path.found else None


def _upstream_isolation(api: PlantApi, question: Question) -> AnswerValue:
    # the walk includes an operated valve and does not go beyond it: those stops are the answer
    sub = api.traverse(
        question.anchors[0], "upstream", "flow", stop_at=ItemFilter(label=_OPERATED_VALVE)
    )
    return sorted(m.item.tag for m in sub.members if m.is_stop and m.item.tag is not None)


def _cross_unit(api: PlantApi, question: Question) -> AnswerValue:
    unit = question.anchors[0]
    in_unit = api.find(ItemFilter(unit=unit), limit=1)
    sub = api.neighbours(in_unit.handle, "downstream", "flow", where=ItemFilter(not_unit=unit))
    return _units_of(sub)


def _count_in_unit(api: PlantApi, question: Question) -> AnswerValue:
    unit, node_class = question.anchors
    return api.find(ItemFilter(unit=unit, node_class=node_class), limit=1).total


def _unanswerable_tag(api: PlantApi, question: Question) -> AnswerValue:
    """Not present when some named tag is absent; otherwise a marker that cannot match."""
    missing = [tag for tag in question.anchors if not _find(api, tag)]
    return None if missing else "every named tag is present"


def _no_path(api: PlantApi, question: Question) -> AnswerValue:
    path = api.path(question.anchors[0], question.anchors[1])
    return None if not path.found else [item.tag or "" for item in path.items]


def _sheets_of_tag(api: PlantApi, question: Question) -> AnswerValue:
    return sorted({sheet for item in _find(api, question.anchors[0]) for sheet in item.sheets})


# --- dev-new families ------------------------------------------------------------------------


def _connected(api: PlantApi, question: Question) -> AnswerValue:
    return "yes" if api.path(question.anchors[0], question.anchors[1]).found else "no"


def _downstream_in_unit(api: PlantApi, question: Question) -> AnswerValue:
    tag, unit = question.anchors
    sub = api.traverse(tag, "downstream", "flow", walk_only=ItemFilter(unit=unit))
    return sorted(
        m.item.tag
        for m in sub.members
        if m.item.tag is not None and {_EQUIPMENT, _VALVE} & set(m.item.labels)
    )


def _instruments_of_item(api: PlantApi, question: Question) -> AnswerValue:
    # equipment -measured_by-> sensor: the only signal edge leaving an equipment item
    return _tags_where(api.neighbours(question.anchors[0], "downstream", "signal"))


def _upstream_sources(api: PlantApi, question: Question) -> AnswerValue:
    """All ancestors of the item, keeping those with no flow predecessor of their own."""
    ancestors = api.traverse(question.anchors[0], "upstream", "flow")
    tags = [m.item.tag for m in ancestors.members if m.item.tag is not None]
    return sorted(tag for tag in tags if _has_no_flow_predecessor(api, tag))


def _has_no_flow_predecessor(api: PlantApi, tag: str) -> bool:
    return api.neighbours(tag, "upstream", "flow").total_items == 0


def _same_unit(api: PlantApi, question: Question) -> AnswerValue:
    first, second = (_find(api, tag) for tag in question.anchors)
    if not first or not second:
        return None
    return "yes" if first[0].unit_id == second[0].unit_id else "no"


def _loops_near_item(api: PlantApi, question: Question) -> AnswerValue:
    """Adjacent valves, then their actuators, then those actuators' controllers (loop tags)."""
    valves = api.neighbours(question.anchors[0], "both", "flow", where=ItemFilter(label=_VALVE))
    if valves.total_items == 0:
        return []
    actuators = api.neighbours(valves.handle, "upstream", "signal")
    if actuators.total_items == 0:
        return []
    return _tags_where(api.neighbours(actuators.handle, "upstream", "signal"))


PROGRAMS: dict[QuestionFamily, CanonicalProgram] = {
    QuestionFamily.LOOKUP_TYPE: _lookup_type,
    QuestionFamily.LOOKUP_UNIT: _lookup_unit,
    QuestionFamily.NEIGHBOURS_DOWNSTREAM: _neighbours_downstream,
    QuestionFamily.LOOP_ACTUATED_VALVE: _loop_actuated_valve,
    QuestionFamily.LOOP_MEASURED_EQUIPMENT: _loop_measured_equipment,
    QuestionFamily.FLOW_PATH: _flow_path,
    QuestionFamily.UPSTREAM_ISOLATION: _upstream_isolation,
    QuestionFamily.CROSS_UNIT: _cross_unit,
    QuestionFamily.COUNT_IN_UNIT: _count_in_unit,
    QuestionFamily.UNANSWERABLE_TAG: _unanswerable_tag,
    QuestionFamily.NO_PATH: _no_path,
    QuestionFamily.SHEETS_OF_TAG: _sheets_of_tag,
    QuestionFamily.CONNECTED: _connected,
    QuestionFamily.DOWNSTREAM_IN_UNIT: _downstream_in_unit,
    QuestionFamily.INSTRUMENTS_OF_ITEM: _instruments_of_item,
    QuestionFamily.UPSTREAM_SOURCES: _upstream_sources,
    QuestionFamily.SAME_UNIT: _same_unit,
    QuestionFamily.LOOPS_NEAR_ITEM: _loops_near_item,
}
