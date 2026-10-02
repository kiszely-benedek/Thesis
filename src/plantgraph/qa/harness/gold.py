"""What the harness reads from the answer key, and strategies never do (`qa-system.md` §5, §17).

Two things need the ground truth at scoring time:

- a `TAG_PATH` answer is valid if every step is a real flow edge of the plant,
  so `scoring.score_path` needs the plant's `send_to` edges by tag, plus the
  tags of off-page connectors (drawing artefacts it must strip out);
- **routing recall**, the share of questions whose gold evidence sheets all
  lie inside the sheets a hierarchical strategy routed to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from plantgraph.graph.schema import CONNECTOR_CLASSES, Relation
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.models import Question

#: Key a strategy puts in `RetrievalResult.trace` to say which sheets it routed to.
#: The harness reads it generically; a strategy without routing just omits it.
ROUTED_SHEETS_TRACE_KEY = "routed_sheets"

#: Key the harness adds to a row's trace: did the routed sheets cover the gold evidence?
ROUTING_HIT_TRACE_KEY = "routing_hit"


@dataclass(frozen=True)
class GoldScoring:
    """The two ground-truth inputs `scoring.score_answer` needs for path questions."""

    #: Printed numbers of every off-page connector in the corpus.
    connector_tags: frozenset[str]
    #: `(from_tag, to_tag)` for every `send_to` edge between two tagged plant items.
    valid_edges: frozenset[tuple[str, str]]


def build_gold_scoring(plant: nx.DiGraph[str], view: GraphView) -> GoldScoring:
    """Collect connector numbers from the view and flow edges from the plant."""
    return GoldScoring(
        connector_tags=_connector_numbers(view), valid_edges=_send_to_tag_edges(plant)
    )


def _connector_numbers(view: GraphView) -> frozenset[str]:
    numbers = (
        item.properties.get("connector_number")
        for item in view.items()
        if item.node_class in CONNECTOR_CLASSES
    )
    return frozenset(number for number in numbers if isinstance(number, str))


def _send_to_tag_edges(plant: nx.DiGraph[str]) -> frozenset[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for source, target, data in plant.edges(data=True):
        if data.get("relation") != Relation.SEND_TO.value:
            continue
        source_tag, target_tag = plant.nodes[source].get("tag"), plant.nodes[target].get("tag")
        if source_tag is not None and target_tag is not None:
            edges.add((str(source_tag), str(target_tag)))
    return frozenset(edges)


def routing_hit(question: Question, trace: dict[str, Any]) -> bool | None:
    """Whether the strategy's routed sheets cover the question's gold evidence sheets.

    Returns `None` when the strategy exposes no routed sheets, or the question
    has no evidence sheets (unanswerable), so it does not count towards recall.

    Raises:
        ValueError: the trace holds routed sheets that are not a list.
    """
    routed = trace.get("retrieval", {}).get(ROUTED_SHEETS_TRACE_KEY)
    if routed is None or not question.evidence_sheets:
        return None
    if not isinstance(routed, list):
        raise ValueError(f"expected routed sheets as a list, found {routed!r}")
    return set(question.evidence_sheets) <= set(routed)
