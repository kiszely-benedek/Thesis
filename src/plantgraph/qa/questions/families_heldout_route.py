"""`ROUTE_AVOIDING`: can flow still get from A to B if one item on the way is removed?

Held-out family (EXP-0006, ADR-0035). Walks only `send_to` edges (material flow: `A -send_to-> B`
means A feeds B) and uses the same shortest path as `FLOW_PATH`. The item removed may be any
equipment item or valve strictly inside the path. The "yes" evidence is the breadth-first path
(first parent in sorted node-id order), since the design names no tie-break for the detour.
"""

from __future__ import annotations

import random

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import (
    build_question,
    is_path_item,
    nodes_of_classes,
    send_to_successors,
)
from plantgraph.qa.questions.evidence import Evidence, SheetIndex
from plantgraph.qa.questions.families_flow import (
    Reached,
    one_target_per_bin,
    path_to,
    reach_from,
)
from plantgraph.qa.questions.families_heldout_paths import path_evidence, tag_of
from plantgraph.qa.questions.templates_heldout import route_avoiding_text

_TEMPLATE_VERSION = "1"


def _tree_without(
    successors: dict[str, list[str]], source_id: str, removed_id: str
) -> dict[str, str]:
    """Breadth-first tree from `source_id` with `removed_id` taken out: node -> first parent."""
    parent_of: dict[str, str] = {}
    frontier = [source_id]
    while frontier:
        found: dict[str, str] = {}
        for current in frontier:
            for successor in successors[current]:
                if successor not in (source_id, removed_id) and successor not in parent_of:
                    found.setdefault(successor, current)
        parent_of.update(found)
        frontier = sorted(found)
    return parent_of


def _route_in_tree(parent_of: dict[str, str], source_id: str, target_id: str) -> list[str]:
    """The path from the tree's root `source_id` down to `target_id`."""
    path = [target_id]
    while path[-1] != source_id:
        path.append(parent_of[path[-1]])
    return path[::-1]


def route_avoiding_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> list[Question]:
    """Per source A and shortest-path k-bin: one target B, one removed item V on the way.

    The answer ("yes" or "no") is asked for alternately, starting from a seeded side, so that
    neither dominates; when a target offers only one of the two, that one is used.

    Whether B stays reachable without V is decided with dominators. A node V "dominates" B
    when every route from A to B passes through V, so removing V cuts B off exactly then. One
    dominator computation per source answers this for every V and B, instead of one
    breadth-first walk per V.
    """
    index = SheetIndex.from_sheets(sheets, manifest)
    successors = {node_id: send_to_successors(plant, node_id) for node_id in plant.nodes}
    flow = nx.DiGraph((a, b) for a, nexts in successors.items() for b in nexts)
    equipment = set(nodes_of_classes(plant, EQUIPMENT_CLASSES))
    questions = []
    for source_id in sorted(equipment):
        rng = random.Random(f"{seed}:ROUTE_AVOIDING:{source_id}")
        wants_yes = rng.random() < 0.5
        reach = reach_from(plant, successors, source_id, index)  # dropped after this source
        targets = _targets_with_item_inside(plant, reach, source_id, equipment)
        if not targets:
            continue
        dominator_of = nx.immediate_dominators(flow, source_id)
        for target_id in one_target_per_bin(targets, rng):
            path = path_to(reach, source_id, target_id)
            cutting = _dominators_of(dominator_of, source_id, target_id)
            removed_id = _removed_item(plant, path, cutting, wants_yes, rng)
            tree = _tree_without(successors, source_id, removed_id)
            wants_yes = not wants_yes
            questions.append(_route_question(plant, index, corpus_id, seed, path, removed_id, tree))
    return questions


def _targets_with_item_inside(
    plant: nx.DiGraph[str], reach: dict[str, Reached], source_id: str, equipment: set[str]
) -> dict[str, Reached]:
    """Equipment reached from the source with an item strictly inside its path (a tee is no item).

    One pass instead of rebuilding every path. `reach` lists a parent before its children, so a
    node has an item inside if its parent does, or if its parent is an item other than the source.
    """
    has_item_inside: dict[str, bool] = {source_id: False}
    for node_id, reached in reach.items():
        if node_id == source_id:
            continue
        parent_id = reached.parent
        if parent_id is None:
            raise ValueError(f"expected {node_id!r} to have a parent, it is a second root")
        has_item_inside[node_id] = has_item_inside[parent_id] or (
            parent_id != source_id and is_path_item(plant, parent_id)
        )
    return {
        t: r for t, r in reach.items() if t in equipment and t != source_id and has_item_inside[t]
    }


def _dominators_of(dominator_of: dict[str, str], source_id: str, target_id: str) -> set[str]:
    """The nodes every route from the source to the target passes through (ends excluded).

    Follows the immediate-dominator links from the target up to the source. Some networkx
    versions map the source to itself and some leave it out, so the walk stops at the source.
    """
    cutting: set[str] = set()
    node_id = dominator_of[target_id]
    while node_id != source_id:
        cutting.add(node_id)
        node_id = dominator_of[node_id]
    return cutting


def _items_inside(plant: nx.DiGraph[str], path: list[str]) -> list[str]:
    """The equipment items and valves strictly between a path's two ends, in path order."""
    return [node_id for node_id in path[1:-1] if is_path_item(plant, node_id)]


def _removed_item(
    plant: nx.DiGraph[str],
    path: list[str],
    cutting: set[str],
    wants_yes: bool,
    rng: random.Random,
) -> str:
    """Pick the item V strictly inside `path` whose removal gives the wanted answer.

    Removing V answers "yes" (the target stays reachable) unless V is in `cutting`. If no V
    gives the wanted answer, one with the other answer is used.
    """
    inside = _items_inside(plant, path)
    if not inside:
        raise ValueError(f"expected a path with an item inside, found {path}")
    wanted = [v for v in inside if (v not in cutting) == wants_yes]
    return rng.choice(wanted or sorted(inside))


def _route_question(
    plant: nx.DiGraph[str],
    index: SheetIndex,
    corpus_id: str,
    seed: int,
    path: list[str],
    removed_id: str,
    parent_of: dict[str, str],
) -> Question:
    source_id, target_id = path[0], path[-1]
    if target_id in parent_of:
        evidence = path_evidence(_route_in_tree(parent_of, source_id, target_id))
    else:  # proving "no" means seeing everything A still reaches
        tree_edges = frozenset((parent, child) for child, parent in parent_of.items())
        evidence = Evidence(nodes=frozenset({source_id, *parent_of}), edges=tree_edges)
    tags = [tag_of(plant, source_id), tag_of(plant, target_id), tag_of(plant, removed_id)]
    return build_question(
        corpus_id=corpus_id,
        family=QuestionFamily.ROUTE_AVOIDING,
        template_id="ROUTE_AVOIDING",
        template_version=_TEMPLATE_VERSION,
        text=route_avoiding_text(*tags),
        answer_type=AnswerType.BOOLEAN,
        reference="yes" if target_id in parent_of else "no",
        evidence=evidence,
        anchors=tags,
        plant=plant,
        index=index,
        seed=seed,
    )
