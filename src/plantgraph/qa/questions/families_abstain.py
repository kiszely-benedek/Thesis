"""UNANSWERABLE_TAG and NO_PATH: questions whose correct reply is "not present" (design §9).

Both have `reference=None`, no evidence and `k=None`: there is nothing to
find, so nothing for an off-page connector to stand in front of. They are
reported in their own column and never enter the k curve (ADR-0011 item 3).

A **tag** is the identifier printed beside an item on the drawing; this
generator mints them as `{prefix}-{unit}-{seq}`, for example `GV-2-3`.
"""

from __future__ import annotations

import random
import re

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, VALVE_CLASSES, Relation
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import (
    build_unanswerable_question,
    nodes_of_classes,
    tagged_nodes_by_tag,
)
from plantgraph.qa.questions.templates import (
    flow_path_text,
    lookup_type_text,
    neighbours_downstream_text,
)

_TEMPLATE_VERSION = "1"

#: Bounds on candidate enumeration, so a plant-scale corpus does not yield one
#: question per tag or per node pair. They cap what the sampler may choose
#: from; they are not the per-bin question counts (those come from the pilot).
DEFAULT_MAX_UNANSWERABLE_TAGS = 20
DEFAULT_PAIRS_PER_SOURCE = 3

_TAG_GRAMMAR = re.compile(r"^(?P<prefix>.+)-(?P<unit>\d+)-(?P<seq>\d+)$")


def _highest_seq_by_group(plant: nx.DiGraph[str]) -> dict[tuple[str, str], int]:
    """Highest sequence number per `(prefix, unit)`, over equipment and valve tags only."""
    highest: dict[tuple[str, str], int] = {}
    for node_id, tag in tagged_nodes_by_tag(plant):
        if plant.nodes[node_id]["node_class"] not in EQUIPMENT_CLASSES | VALVE_CLASSES:
            continue
        match = _TAG_GRAMMAR.match(tag)
        if match is None:
            continue
        group = (match["prefix"], match["unit"])
        highest[group] = max(highest.get(group, 0), int(match["seq"]))
    return highest


def absent_tags(plant: nx.DiGraph[str], max_tags: int, rng: random.Random) -> list[str]:
    """Well-formed tags absent from the plant: one per `(prefix, unit)` group, at most `max_tags`.

    Each is the group's highest sequence number plus one, so it looks like a
    real neighbour of existing tags. If that tag is somehow taken (a loop tag
    shares the grammar), the sequence moves on until it is free.
    """
    taken = {str(data["tag"]) for _, data in plant.nodes(data=True) if "tag" in data}
    highest = _highest_seq_by_group(plant)
    groups = sorted(highest)
    if len(groups) > max_tags:
        groups = sorted(rng.sample(groups, max_tags))
    tags = []
    for prefix, unit in groups:
        seq = highest[(prefix, unit)] + 1
        while f"{prefix}-{unit}-{seq}" in taken:
            seq += 1
        tags.append(f"{prefix}-{unit}-{seq}")
    return tags


def unanswerable_tag_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
    max_tags: int = DEFAULT_MAX_UNANSWERABLE_TAGS,
) -> list[Question]:
    """Three candidates (type, neighbours, flow path) per absent tag.

    `manifest` and `sheets` are unused: there is no evidence to locate. They
    stay in the signature so every family generator is called the same way.
    """
    del manifest, sheets
    rng = random.Random(seed)
    real_tags = [str(plant.nodes[n]["tag"]) for n in nodes_of_classes(plant, EQUIPMENT_CLASSES)]
    if not real_tags:
        raise ValueError("expected at least one equipment item in the plant, found none")
    questions = []
    for absent_tag in absent_tags(plant, max_tags, rng):
        questions.extend(_three_templates(absent_tag, rng.choice(real_tags), corpus_id, seed))
    return questions


def _three_templates(absent_tag: str, real_tag: str, corpus_id: str, seed: int) -> list[Question]:
    """The lookup, neighbours and flow-path wording, each naming `absent_tag`."""
    specs = [
        ("LOOKUP_TYPE", lookup_type_text(absent_tag), AnswerType.CLASS_NAME, [absent_tag]),
        (
            "NEIGHBOURS_DOWNSTREAM",
            neighbours_downstream_text(absent_tag),
            AnswerType.TAG_SET,
            [absent_tag],
        ),
        (
            "FLOW_PATH",
            flow_path_text(real_tag, absent_tag),
            AnswerType.TAG_PATH,
            [real_tag, absent_tag],
        ),
    ]
    return [
        build_unanswerable_question(
            corpus_id=corpus_id,
            family=QuestionFamily.UNANSWERABLE_TAG,
            template_id=template_id,
            template_version=_TEMPLATE_VERSION,
            text=text,
            answer_type=answer_type,
            anchors=anchors,
            seed=seed,
        )
        for template_id, text, answer_type, anchors in specs
    ]


def _send_to_graph(plant: nx.DiGraph[str]) -> nx.DiGraph[str]:
    """The plant with only its `send_to` edges: signal and measurement links are not flow."""
    flow: nx.DiGraph[str] = nx.DiGraph()
    flow.add_nodes_from(plant.nodes)
    flow.add_edges_from(
        (u, v)
        for u, v, data in plant.edges(data=True)
        if data["relation"] == Relation.SEND_TO.value
    )
    return flow


def no_path_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
    pairs_per_source: int = DEFAULT_PAIRS_PER_SOURCE,
) -> list[Question]:
    """FLOW_PATH questions between two present equipment items with no `send_to` path.

    For each source, up to `pairs_per_source` unreachable targets are drawn
    with the seeded RNG, so the candidate list stays bounded on a big plant.
    """
    del manifest, sheets
    rng = random.Random(seed)
    flow = _send_to_graph(plant)
    equipment = nodes_of_classes(plant, EQUIPMENT_CLASSES)
    questions = []
    for source_id in equipment:
        reachable = nx.descendants(flow, source_id) | {source_id}
        unreachable = [n for n in equipment if n not in reachable]
        for target_id in _draw(unreachable, pairs_per_source, rng):
            questions.append(_no_path_question(plant, source_id, target_id, corpus_id, seed))
    return questions


def _draw(items: list[str], count: int, rng: random.Random) -> list[str]:
    """Up to `count` items, drawn with the seeded RNG and returned sorted."""
    return sorted(rng.sample(items, min(count, len(items))))


def _no_path_question(
    plant: nx.DiGraph[str], source_id: str, target_id: str, corpus_id: str, seed: int
) -> Question:
    source_tag = str(plant.nodes[source_id]["tag"])
    target_tag = str(plant.nodes[target_id]["tag"])
    return build_unanswerable_question(
        corpus_id=corpus_id,
        family=QuestionFamily.NO_PATH,
        template_id="FLOW_PATH",
        template_version=_TEMPLATE_VERSION,
        text=flow_path_text(source_tag, target_tag),
        answer_type=AnswerType.TAG_PATH,
        anchors=[source_tag, target_tag],
        seed=seed,
    )
