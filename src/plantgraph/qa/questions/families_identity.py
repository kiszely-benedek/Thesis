"""SHEETS_OF_TAG: on which sheets is an item drawn? (ADR-0028, design RU §3.5).

An **identity group** is one physical item the splitter drew on several
sheets: one home occurrence plus reference occurrences (`IdentityGroup`).
The question asks for every sheet that draws it, and the sheet ids are the
ones a reader sees, which `localize` keeps unchanged (`resolution/localize.py`).

`k` here is the number of reference occurrences: the extra drawings of the
same item a strategy must find and recognise as one item. Each group is
paired with a control, a single-sheet item with `k = 0` and a one-element
answer, so the k curve also shows how a strategy does when there is nothing
to merge.
"""

from __future__ import annotations

import random

import networkx as nx

from plantgraph.benchmark.models import IdentityGroup, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import build_question, tagged_nodes_by_tag
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.templates import sheets_of_tag_text

_TEMPLATE_VERSION = "1"


def sheets_of_tag_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """One candidate per identity group, plus as many single-sheet controls (k = 0)."""
    index = SheetIndex.from_sheets(sheets, manifest)
    group_nodes = [_group_node_id(group) for group in manifest.identity_groups]
    controls = _control_node_ids(plant, index, group_nodes, seed)
    questions = [
        _group_question(group, plant, index, corpus_id, seed) for group in _by_tag(manifest)
    ]
    questions += [_control_question(node_id, plant, index, corpus_id, seed) for node_id in controls]
    return questions


def _by_tag(manifest: SplitManifest) -> list[IdentityGroup]:
    """Groups ordered by printed tag, so candidate order never depends on the splitter's."""
    return sorted(manifest.identity_groups, key=lambda group: group.tag)


def _split_key(key: str) -> tuple[str, str]:
    """`"sheet:node"` -> `(sheet_id, node_id)`, the form the splitter writes group keys in."""
    sheet_id, separator, node_id = key.partition(":")
    if not separator or not sheet_id or not node_id:
        raise ValueError(f"expected an occurrence key 'sheet_id:node_id', found {key!r}")
    return sheet_id, node_id


def _group_node_id(group: IdentityGroup) -> str:
    return _split_key(group.home)[1]


def _group_question(
    group: IdentityGroup,
    plant: nx.DiGraph[str],
    index: SheetIndex,
    corpus_id: str,
    seed: int,
) -> Question:
    node_id = _group_node_id(group)
    sheet_ids = sorted({_split_key(key)[0] for key in [group.home, *group.references]})
    question = _question(node_id, group.tag, sheet_ids, plant, index, corpus_id, seed)
    # k counts the reference occurrences; the item has no evidence edge, so
    # build_question left k at 0. Every crossing here is an identity one.
    n_references = len(group.references)
    return question.model_copy(update={"k": n_references, "k_identity": n_references})


def _control_node_ids(
    plant: nx.DiGraph[str], index: SheetIndex, group_nodes: list[str], seed: int
) -> list[str]:
    """As many single-sheet equipment items as there are groups, drawn with a seeded rng."""
    taken = set(group_nodes)
    pool = [
        node_id
        for node_id, _ in tagged_nodes_by_tag(plant)
        if plant.nodes[node_id]["node_class"] in EQUIPMENT_CLASSES
        and len(index.sheets_of.get(node_id, frozenset())) == 1
        and node_id not in taken
    ]
    rng = random.Random(f"{seed}:SHEETS_OF_TAG")
    return sorted(rng.sample(pool, min(len(group_nodes), len(pool))))


def _control_question(
    node_id: str, plant: nx.DiGraph[str], index: SheetIndex, corpus_id: str, seed: int
) -> Question:
    sheet_ids = sorted(index.sheets_of[node_id])
    return _question(
        node_id, str(plant.nodes[node_id]["tag"]), sheet_ids, plant, index, corpus_id, seed
    )


def _question(
    node_id: str,
    tag: str,
    sheet_ids: list[str],
    plant: nx.DiGraph[str],
    index: SheetIndex,
    corpus_id: str,
    seed: int,
) -> Question:
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.SHEETS_OF_TAG,
        template_id="SHEETS_OF_TAG",
        template_version=_TEMPLATE_VERSION,
        text=sheets_of_tag_text(tag),
        answer_type=AnswerType.SHEET_SET,
        reference=sheet_ids,
        evidence=Evidence(nodes=frozenset({node_id}), edges=frozenset()),
        anchors=[tag],
        plant=plant,
        index=index,
        seed=seed,
    )
