"""LOOKUP_TYPE and LOOKUP_UNIT: single-node questions, always k = 0 (design §9).

Both read exactly one node's own property — `node_class` or `unit_id` — and
no edge at all. Since `k` counts evidence *edges* that cross sheets
(`evidence.py`), a question with no evidence edge can never cross one.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question, tagged_nodes_by_tag
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.templates import lookup_type_text

_TEMPLATE_VERSION = "1"


def lookup_type_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One `LOOKUP_TYPE` candidate per tagged node, ordered by tag."""
    index = SheetIndex.from_sheets(sheets, manifest)
    return [
        build_question(
            corpus_id=corpus_id,
            family=QuestionFamily.LOOKUP_TYPE,
            template_id="LOOKUP_TYPE",
            template_version=_TEMPLATE_VERSION,
            text=lookup_type_text(tag),
            answer_type=AnswerType.CLASS_NAME,
            reference=str(plant.nodes[node_id]["node_class"]),
            evidence=Evidence(nodes=frozenset({node_id}), edges=frozenset()),
            anchors=[tag],
            plant=plant,
            index=index,
            seed=seed,
        )
        for node_id, tag in tagged_nodes_by_tag(plant)
    ]


def lookup_unit_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One `LOOKUP_UNIT` candidate per tagged node, ordered by tag."""
    index = SheetIndex.from_sheets(sheets, manifest)
    return [
        build_question(
            corpus_id=corpus_id,
            family=QuestionFamily.LOOKUP_UNIT,
            template_id="LOOKUP_UNIT",
            template_version=_TEMPLATE_VERSION,
            text=f"Which unit is {tag} located in?",
            answer_type=AnswerType.UNIT_ID,
            reference=str(plant.nodes[node_id]["unit_id"]),
            evidence=Evidence(nodes=frozenset({node_id}), edges=frozenset()),
            anchors=[tag],
            plant=plant,
            index=index,
            seed=seed,
        )
        for node_id, tag in tagged_nodes_by_tag(plant)
        if "unit_id" in plant.nodes[node_id]
    ]
