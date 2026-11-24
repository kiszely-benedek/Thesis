"""Criterion 9: can a reader of the B view reproduce the gold's names for untagged valves?

Gold side: it compares the canonical program (`canonical_b.py`, which reads only the view) with the
gold's descriptors and positions, on the dev scope X questions of one plant (design `v2t-b`
§10.6 criterion 9, as amended by §10.8). Two things are checked, each on every case:

1. **Descriptors.** For each untagged valve in a kept isolation reference (OPEN_VALVES and
   UPSTREAM_ISOLATION_X), the program's canonical descriptor over the view equals the gold's, and
   the gold's descriptor resolves over the view to exactly that valve.
2. **Positions.** For each descriptor-form POSITION question, the descriptor in its text resolves
   over the view to exactly the question's valve, and the valve's `operating_position` in the view
   equals the question's reference.

The bar is 100 %. A miss means the gold names something the B system cannot read, so each one is
recorded with the generator **role** of its valve (a role says why the valve is on the drawing,
for example "pump discharge block").
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.scope_x_models import FamilyOutcome, NamedBy
from plantgraph.qa.v2tb.canonical_b import visible_plant
from plantgraph.qa.v2tb.descriptor import (
    Descriptor,
    PlantIndex,
    Side,
    canonical_descriptor,
    decode_item,
    resolve_descriptor,
)
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from plantgraph.resolution.localize import OccurrenceMap

_ISOLATION_FAMILIES = (QuestionFamily.OPEN_VALVES_TO_ISOLATE, QuestionFamily.UPSTREAM_ISOLATION_X)
_DESCRIBED = re.compile(
    r"^What is the normal operating position of the (?P<cls>.+?) on line (?P<line>.+), "
    r"on the (?P<side>upstream|downstream) side of (?P<next_to>.+)\?$"
)


class Miss(BaseModel):
    """One valve the B reader could not reproduce."""

    model_config = ConfigDict(frozen=True)

    check: str
    role: str
    valve_id: str
    detail: str


class ExpressivenessReport(BaseModel):
    """The counts of the two checks and every miss."""

    model_config = ConfigDict(frozen=True)

    n_untagged_gold_valves: int
    n_descriptors_reproduced: int
    n_position_questions: int
    n_resolved_exactly: int
    n_position_read: int
    misses: list[Miss]

    @property
    def misses_by_role(self) -> dict[str, int]:
        """Role -> number of misses, largest first."""
        counts = Counter(miss.role for miss in self.misses)
        return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def check_expressiveness(
    *,
    plant: nx.DiGraph[str],
    view: GraphView,
    occurrence_map: OccurrenceMap,
    outcomes: Mapping[QuestionFamily, FamilyOutcome],
    roles: Mapping[str, str],
) -> ExpressivenessReport:
    """Run both checks of criterion 9 on one plant's dev scope X outcomes.

    Args:
        plant: the gold plant (the descriptors' source of truth).
        view: the `NetworkxGraphViewB` the B system reads.
        occurrence_map: gold node id <-> local key, to find a valve in the view.
        outcomes: the dev scope X family outcomes of the plant.
        roles: valve node id -> generator role, for naming the misses.
    """
    reader = _Reader(plant, view, occurrence_map, roles)
    for family in _ISOLATION_FAMILIES:
        for question in outcomes[family].kept:
            reader.check_reference(question)
    position = outcomes[QuestionFamily.POSITION_OF_VALVE]
    for question in position.kept:
        if position.flags[question.question_id].named_by is NamedBy.DESCRIPTOR:
            reader.check_position_question(question)
    return reader.report()


class _Reader:
    """The two indexes (gold and visible), the tallies and the misses."""

    def __init__(
        self,
        plant: nx.DiGraph[str],
        view: GraphView,
        occurrence_map: OccurrenceMap,
        roles: Mapping[str, str],
    ) -> None:
        self._gold = PlantIndex(plant)
        self._visible_plant = visible_plant(view)
        self._visible = PlantIndex(self._visible_plant)
        self._local_key = _local_keys(occurrence_map)
        self._roles = roles
        self._seen: set[str] = set()
        self._reproduced = 0
        self._position_questions = 0
        self._resolved = 0
        self._read = 0
        self._misses: list[Miss] = []

    def check_reference(self, question: Question) -> None:
        """Every untagged valve of a VALVE_SET reference, once per valve."""
        if question.answer_type is not AnswerType.VALVE_SET or not isinstance(
            question.reference, list
        ):
            raise ValueError(f"expected a VALVE_SET reference list, found {question.question_id!r}")
        for item in question.reference:
            decoded = decode_item(item)
            if isinstance(decoded, Descriptor):
                self._check_descriptor(decoded)

    def _check_descriptor(self, gold: Descriptor) -> None:
        valve = self._gold_valve(gold)
        if valve in self._seen:
            return
        self._seen.add(valve)
        local = self._local_key[valve]
        found = canonical_descriptor(self._visible, local)
        if found == gold:
            self._reproduced += 1
        else:
            self._miss("descriptor", valve, f"gold {gold!r}, program {found!r}")

    def check_position_question(self, question: Question) -> None:
        """One descriptor-form POSITION question: resolve it in the view, read the position."""
        self._position_questions += 1
        parsed = _parse_described(question.text)
        valve = self._gold_valve(parsed)
        local = self._local_key[valve]
        if resolve_descriptor(self._visible, parsed) != {local}:
            self._miss("resolve", valve, f"{question.text!r} does not resolve to the valve")
            return
        self._resolved += 1
        position = self._visible_plant.nodes[local].get(OPERATING_POSITION)
        if position == question.reference:
            self._read += 1
        else:
            self._miss("position", valve, f"view shows {position!r}, gold {question.reference!r}")

    def _gold_valve(self, descriptor: Descriptor) -> str:
        found = resolve_descriptor(self._gold, descriptor)
        if len(found) != 1:
            raise ValueError(
                f"expected {descriptor!r} to name one gold valve, found {sorted(found)}"
            )
        return next(iter(found))

    def _miss(self, check: str, valve: str, detail: str) -> None:
        role = self._roles.get(valve, "<no role>")
        self._misses.append(Miss(check=check, role=role, valve_id=valve, detail=detail))

    def report(self) -> ExpressivenessReport:
        """The tallies so far."""
        return ExpressivenessReport(
            n_untagged_gold_valves=len(self._seen),
            n_descriptors_reproduced=self._reproduced,
            n_position_questions=self._position_questions,
            n_resolved_exactly=self._resolved,
            n_position_read=self._read,
            misses=self._misses,
        )


def _parse_described(text: str) -> Descriptor:
    """The descriptor in a descriptor-form POSITION question's text.

    Raises:
        ValueError: the text is not of that form.
    """
    match = _DESCRIBED.match(text)
    if match is None:
        raise ValueError(f"expected a descriptor-form POSITION question, found {text!r}")
    return Descriptor(
        class_name=match["cls"],
        line_number=match["line"],
        next_to=match["next_to"],
        side=Side(match["side"]),
    )


def _local_keys(occurrence_map: OccurrenceMap) -> dict[str, str]:
    """Gold node id -> local key, for the nodes that have exactly one occurrence (valves do)."""
    keys: dict[str, list[str]] = {}
    for local_key in occurrence_map.local_to_original:
        keys.setdefault(occurrence_map.original_node_id(local_key), []).append(local_key)
    return {node_id: found[0] for node_id, found in keys.items() if len(found) == 1}
