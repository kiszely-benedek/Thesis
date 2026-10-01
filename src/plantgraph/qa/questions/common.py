"""Shared plumbing every question family builds on: graph walks and `Question` assembly.

None of this reads an equipment attribute (ADR-0021, ADR-0018 A1) — only
`tag`, `node_class`, `unit_id` and the plant's `send_to` / `send_signal_to` /
`measured_by` / `control` edges (`graph/schema.py`).
"""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import Relation
from plantgraph.qa.models import AnswerType, AnswerValue, Question, QuestionFamily
from plantgraph.qa.questions.evidence import Evidence, evidence_k, evidence_sheets, evidence_tags


def tagged_nodes_by_tag(plant: nx.DiGraph[str]) -> list[tuple[str, str]]:
    """Every `(node_id, tag)` pair in the plant, sorted by tag.

    Sorting is what makes candidate enumeration deterministic: networkx does
    not promise a stable node iteration order across versions, so any
    family that walked `plant.nodes()` directly could reorder its candidates
    from one run to the next even on the same graph (design §9,
    "Deterministic ... order included").
    """
    return sorted(
        ((node_id, str(data["tag"])) for node_id, data in plant.nodes(data=True) if "tag" in data),
        key=lambda pair: pair[1],
    )


def send_to_successors(plant: nx.DiGraph[str], node_id: str) -> list[str]:
    """Every node `node_id` sends material to directly, sorted by node_id."""
    return _relation_successors(plant, node_id, Relation.SEND_TO)


def single_successor(
    plant: nx.DiGraph[str], node_id: str, relation: Relation, *, context: str
) -> str:
    """The one node reached from `node_id` over `relation` — a generated loop has exactly one.

    Raises:
        ValueError: `node_id` has zero or more than one `relation` successor,
            meaning the plant does not match the generator's own invariant
            this family relies on (`tests/graph_plant_builder.py`).
    """
    matches = _relation_successors(plant, node_id, relation)
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {relation.value!r} successor of {node_id!r} ({context}), "
            f"found {len(matches)}: {matches}"
        )
    return matches[0]


def single_predecessor(
    plant: nx.DiGraph[str], node_id: str, relation: Relation, *, context: str
) -> str:
    """The one node that reaches `node_id` over `relation` — the mirror of `single_successor`."""
    matches = _relation_predecessors(plant, node_id, relation)
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {relation.value!r} predecessor of {node_id!r} ({context}), "
            f"found {len(matches)}: {matches}"
        )
    return matches[0]


def _relation_successors(plant: nx.DiGraph[str], node_id: str, relation: Relation) -> list[str]:
    return sorted(
        successor_id
        for successor_id in plant.successors(node_id)
        if plant.edges[node_id, successor_id]["relation"] == relation.value
    )


def _relation_predecessors(plant: nx.DiGraph[str], node_id: str, relation: Relation) -> list[str]:
    return sorted(
        predecessor_id
        for predecessor_id in plant.predecessors(node_id)
        if plant.edges[predecessor_id, node_id]["relation"] == relation.value
    )


def build_question(
    *,
    corpus_id: str,
    family: QuestionFamily,
    template_id: str,
    template_version: str,
    text: str,
    answer_type: AnswerType,
    reference: AnswerValue,
    evidence: Evidence,
    anchors: list[str],
    plant: nx.DiGraph[str],
    sheets: Sequence[SheetGraph],
    cut: frozenset[tuple[str, str]],
    seed: int,
) -> Question:
    """Assemble one answerable `Question`, filling `k`, `evidence_sheets` and `evidence_tags`.

    `question_id` is built from the family and the anchors alone, so
    re-running candidate generation on the same corpus gives byte-identical
    ids (design §9, "Deterministic").
    """
    return Question(
        question_id=f"{corpus_id}:{family.value}:{'|'.join(anchors)}",
        corpus_id=corpus_id,
        family=family,
        template_id=template_id,
        template_version=template_version,
        text=text,
        answer_type=answer_type,
        answerable=True,
        reference=reference,
        evidence_tags=evidence_tags(evidence, plant),
        evidence_sheets=evidence_sheets(evidence, sheets),
        k=evidence_k(evidence, cut),
        anchors=anchors,
        generator_seed=seed,
    )


def build_unanswerable_question(
    *,
    corpus_id: str,
    family: QuestionFamily,
    template_id: str,
    template_version: str,
    text: str,
    answer_type: AnswerType,
    anchors: list[str],
    seed: int,
) -> Question:
    """Assemble one `Question` whose correct reply is "not present" (`k=None`, no evidence).

    Several templates share one family (`UNANSWERABLE_TAG` wraps three), so
    `template_id` goes into `question_id` too; anchors alone would collide.
    `answer_type` is the shape the underlying template would have had if the
    question were answerable, since `AnswerType` has no "not present" member.
    """
    return Question(
        question_id=f"{corpus_id}:{family.value}:{template_id}:{'|'.join(anchors)}",
        corpus_id=corpus_id,
        family=family,
        template_id=template_id,
        template_version=template_version,
        text=text,
        answer_type=answer_type,
        answerable=False,
        reference=None,
        k=None,
        anchors=anchors,
        generator_seed=seed,
    )


def unit_of(plant: nx.DiGraph[str], node_id: str) -> str | None:
    """The `unit_id` of a node, or `None` when the node carries none."""
    unit_id = plant.nodes[node_id].get("unit_id")
    return None if unit_id is None else str(unit_id)


def nodes_of_classes(plant: nx.DiGraph[str], node_classes: frozenset[str]) -> list[str]:
    """Node ids whose `node_class` is in `node_classes`, ordered by printed tag."""
    return [
        node_id
        for node_id, _ in tagged_nodes_by_tag(plant)
        if plant.nodes[node_id]["node_class"] in node_classes
    ]
