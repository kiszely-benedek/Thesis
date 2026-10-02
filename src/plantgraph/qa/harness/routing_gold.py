"""Two gold-side routing metrics beside strict routing recall (design §3.7, ADR-0030).

Strict recall (`gold.routing_hit`) asks whether *every* sheet an evidence node is drawn on was
routed. That under-counts: an item drawn on several sheets lists them all, including reference
sheets a path never needs, and a flow question accepts any valid path, not just the gold one.
So two more numbers are added; strict recall keeps its name and value (pre-registered).

- **relaxed routing hit**: for a `FLOW_PATH` question, does *some* `send_to` path from the
  source tag to the target tag use only items drawn on a routed sheet? Other families: same as
  strict.
- **evidence-node recall**: the share of evidence items that appear at least once in the
  serialized context (after any budget cut).

Both read gold fields and the strategy's trace here, in the harness; a strategy never sees them.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.harness.gold import ROUTING_HIT_TRACE_KEY, routing_hit
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.common import send_to_successors
from plantgraph.qa.questions.evidence import SheetIndex
from plantgraph.resolution.localize import OccurrenceMap

#: Keys the harness adds to a row's trace, next to `gold.ROUTING_HIT_TRACE_KEY`.
RELAXED_ROUTING_HIT_TRACE_KEY = "relaxed_routing_hit"
EVIDENCE_NODE_RECALL_TRACE_KEY = "evidence_node_recall"

#: Trace keys a strategy writes under `trace["retrieval"]`.
_SERIALIZED_KEYS_TRACE_KEY = "serialized_keys"


@dataclass(frozen=True)
class RoutingGold:
    """What the two metrics need to know about one corpus's ground truth."""

    plant: nx.DiGraph[str]
    #: Plant node id -> every sheet that draws it (a duplicated item has several).
    sheets_of: dict[str, frozenset[str]]
    occurrence_map: OccurrenceMap
    #: Printed tag -> the plant node ids carrying it.
    node_ids_of_tag: dict[str, list[str]]


def build_routing_gold(
    plant: nx.DiGraph[str],
    gold_sheets: list[SheetGraph],
    manifest: SplitManifest,
    occurrence_map: OccurrenceMap,
) -> RoutingGold:
    """Index the plant by tag and the raw (pre-`localize`) sheets by node."""
    node_ids_of_tag: dict[str, list[str]] = {}
    for node_id, data in plant.nodes(data=True):
        if "tag" in data:
            node_ids_of_tag.setdefault(str(data["tag"]), []).append(str(node_id))
    index = SheetIndex.from_sheets(gold_sheets, manifest)
    return RoutingGold(plant, index.sheets_of, occurrence_map, node_ids_of_tag)


def add_routing_metrics(trace: dict[str, Any], question: Question, gold: RoutingGold) -> None:
    """Write whichever of the three routing metrics apply to this row into `trace`."""
    strict = routing_hit(question, trace)
    if strict is None:
        return
    trace[ROUTING_HIT_TRACE_KEY] = strict
    trace[RELAXED_ROUTING_HIT_TRACE_KEY] = relaxed_routing_hit(question, trace, gold)
    recall = evidence_node_recall(question, trace, gold)
    if recall is not None:
        trace[EVIDENCE_NODE_RECALL_TRACE_KEY] = recall


def relaxed_routing_hit(question: Question, trace: dict[str, Any], gold: RoutingGold) -> bool:
    """Strict hit, except a `FLOW_PATH` question is also a hit if any valid path is routed.

    Call only when `routing_hit` is not `None` (the strategy routed and there is evidence).

    Raises:
        ValueError: a `FLOW_PATH` question without exactly two anchor tags, or a tag
            the plant does not know.
    """
    routed = set(trace["retrieval"]["routed_sheets"])
    if question.family is not QuestionFamily.FLOW_PATH:
        return set(question.evidence_sheets) <= routed
    if len(question.anchors) != 2:
        raise ValueError(
            f"expected a FLOW_PATH question to have 2 anchors, found {question.anchors}"
        )
    source_tag, target_tag = question.anchors
    return _path_within_routed(
        gold, _nodes_of(gold, source_tag), _nodes_of(gold, target_tag), routed
    )


def evidence_node_recall(
    question: Question, trace: dict[str, Any], gold: RoutingGold
) -> float | None:
    """Share of evidence items with at least one occurrence in the serialized context.

    Items are compared by printed tag after mapping each serialized occurrence back to its
    plant node through the occurrence map; a tag names one plant node, so this is a node count.
    Returns `None` when the strategy lists no serialized keys or the question has no evidence.
    """
    keys = trace.get("retrieval", {}).get(_SERIALIZED_KEYS_TRACE_KEY)
    evidence = set(question.evidence_tags)
    if keys is None or not evidence:
        return None
    seen = {tag for key in keys if (tag := _tag_of_key(gold, key)) is not None}
    return len(evidence & seen) / len(evidence)


def _tag_of_key(gold: RoutingGold, local_key: str) -> str | None:
    """The plant tag behind one serialized occurrence; `None` for stubs and untagged items."""
    node_id = gold.occurrence_map.original_node_id(local_key)
    if node_id not in gold.plant:
        return None
    tag = gold.plant.nodes[node_id].get("tag")
    return None if tag is None else str(tag)


def _nodes_of(gold: RoutingGold, tag: str) -> list[str]:
    node_ids = gold.node_ids_of_tag.get(tag)
    if not node_ids:
        raise ValueError(f"expected tag {tag!r} to name a plant item, found none")
    return node_ids


def _path_within_routed(
    gold: RoutingGold, sources: list[str], targets: list[str], routed: set[str]
) -> bool:
    """BFS over `send_to`, stepping only onto items drawn on at least one routed sheet."""
    wanted = set(targets)
    seen = {node_id for node_id in sources if _is_drawn_on(gold, node_id, routed)}
    queue = deque(seen)
    while queue:
        node_id = queue.popleft()
        if node_id in wanted:
            return True
        for successor in send_to_successors(gold.plant, node_id):
            if successor not in seen and _is_drawn_on(gold, successor, routed):
                seen.add(successor)
                queue.append(successor)
    return False


def _is_drawn_on(gold: RoutingGold, node_id: str, routed: set[str]) -> bool:
    return not gold.sheets_of.get(node_id, frozenset()).isdisjoint(routed)
