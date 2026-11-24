"""POSITION_OF_VALVE: one candidate per valve with a normal position (design `v2t-b` §10 R11).

A valve that prints a tag is asked about by that tag. A valve that prints none is asked about by its
**descriptor** ("the gate valve on line 6"-P-1203-A1A, on the downstream side of P-101"): the
class, the line number and the nearest tagged item beside it. An untagged valve with no unique
descriptor is refused and counted, never reworded. The reference is the position code either way.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.graph.schema import Relation
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question
from plantgraph.qa.questions.evidence import Evidence
from plantgraph.qa.questions.scope_x_models import (
    TEMPLATE_VERSION,
    FamilyOutcome,
    NamedBy,
    QuestionFlags,
    Refusal,
    RefusalReason,
    XPlant,
)
from plantgraph.qa.questions.templates_x import (
    position_of_described_valve_text,
    position_of_valve_text,
)
from plantgraph.qa.v2tb.descriptor import Descriptor, PlantIndex, Side, canonical_descriptor

_FAMILY = QuestionFamily.POSITION_OF_VALVE


def position_outcome(plant: XPlant) -> FamilyOutcome:
    """Every positioned valve as a question named by tag or descriptor, or as a refusal."""
    kept: list[Question] = []
    refusals: list[Refusal] = []
    flags: dict[str, QuestionFlags] = {}
    for node_id in sorted(plant.positions):  # sorted: networkx gives no stable node order
        built = _question_or_refusal(plant, node_id)
        if isinstance(built, Refusal):
            refusals.append(built)
            continue
        question, named_by = built
        kept.append(question)
        flags[question.question_id] = QuestionFlags(
            holds_untagged=named_by is NamedBy.DESCRIPTOR, named_by=named_by
        )
    return FamilyOutcome(
        family=_FAMILY,
        candidates=len(plant.positions),
        kept=kept,
        refusals=refusals,
        flags=flags,
    )


def _question_or_refusal(plant: XPlant, node_id: str) -> tuple[Question, NamedBy] | Refusal:
    tag = plant.plant_index.tag_of(node_id)
    if tag is not None:
        return _tag_question(plant, node_id, tag), NamedBy.TAG
    descriptor = canonical_descriptor(plant.plant_index, node_id)
    if descriptor is None:
        return Refusal(
            family=_FAMILY,
            anchor=node_id,
            reason=RefusalReason.NO_UNIQUE_DESCRIPTOR,
            valve_ids=(node_id,),
        )
    return _descriptor_question(plant, node_id, descriptor), NamedBy.DESCRIPTOR


def _tag_question(plant: XPlant, node_id: str, tag: str) -> Question:
    return _build(
        plant,
        text=position_of_valve_text(tag),
        reference_node=node_id,
        evidence=Evidence(nodes=frozenset({node_id}), edges=frozenset()),
        anchor=tag,
    )


def _descriptor_question(plant: XPlant, node_id: str, descriptor: Descriptor) -> Question:
    text = position_of_described_valve_text(
        descriptor.class_name, descriptor.line_number, descriptor.side.value, descriptor.next_to
    )
    question = _build(
        plant,
        text=text,
        reference_node=node_id,
        evidence=_walk_evidence(plant, node_id, descriptor),
        anchor=descriptor.next_to,
    )
    # many valves sit beside one tag, so the anchor cannot tell questions apart; the descriptor can
    unique = "|".join(
        (descriptor.next_to, descriptor.side.value, descriptor.class_name, descriptor.line_number)
    )
    return question.model_copy(
        update={"question_id": f"{plant.corpus_id}:{_FAMILY.value}:{unique}"}
    )


def _build(
    plant: XPlant, *, text: str, reference_node: str, evidence: Evidence, anchor: str
) -> Question:
    return build_question(
        corpus_id=plant.corpus_id,
        family=_FAMILY,
        template_id=_FAMILY.value,
        template_version=TEMPLATE_VERSION,
        text=text,
        answer_type=AnswerType.POSITION,
        reference=plant.positions[reference_node],
        evidence=evidence,
        anchors=[anchor],
        plant=plant.graph,
        index=plant.sheet_index,
        seed=plant.seed,
    )


def next_to_node(index: PlantIndex, valve_id: str, descriptor: Descriptor) -> str:
    """The plant node that the descriptor's `next_to` tag stands for on the walk from the valve.

    A tag can be printed on two nodes (a control valve and its actuator); only one of them is on the
    `send_to` walk from the valve, so the choice is not a guess.

    Raises:
        ValueError: no such neighbour exists (a descriptor from `canonical_descriptor` has one).
    """
    upstream = descriptor.side is Side.UPSTREAM
    reached = index.nearest_tagged(valve_id, forward=upstream)
    beside = sorted(index.nodes_with_tag(descriptor.next_to) & reached)
    if not beside:
        raise ValueError(
            f"expected {descriptor.next_to} to be the nearest tagged item "
            f"{descriptor.side.value} of {valve_id}, found none"
        )
    return beside[0]


def _walk_evidence(plant: XPlant, valve_id: str, descriptor: Descriptor) -> Evidence:
    """The valve, `next_to` and the untagged nodes between them: one shortest `send_to` walk."""
    neighbour = next_to_node(plant.plant_index, valve_id, descriptor)
    # flow runs upstream item -> valve -> downstream item, so the walk starts at the upstream end
    upstream = descriptor.side is Side.UPSTREAM
    source, target = (valve_id, neighbour) if upstream else (neighbour, valve_id)
    path = nx.shortest_path(_untagged_flow(plant, source, target), source, target)
    return Evidence(nodes=frozenset(path), edges=frozenset(zip(path, path[1:], strict=False)))


def _untagged_flow(plant: XPlant, source: str, target: str) -> nx.DiGraph[str]:
    """The `send_to` edges among untagged nodes plus the two ends: the walk may not pass a tag."""
    graph = plant.graph
    ends = {source, target}
    return nx.subgraph_view(  # type: ignore[no-any-return]
        graph,
        filter_node=lambda n: n in ends or plant.plant_index.tag_of(n) is None,
        filter_edge=lambda u, v: graph.edges[u, v].get("relation") == Relation.SEND_TO.value,
    )
