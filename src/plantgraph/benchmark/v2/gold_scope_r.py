"""The gold side of scope R (replication) on a v2.2 plant (design 11).

**Scope R** is the EXP-0008 question recipe, re-run on v2.2 plants; its answers stay topological
(any piping path, whatever the valve positions). A v2.2 document may print no tag on its manual
valves, and an answer that must name a valve then has nothing to name. The question generator
therefore **refuses** such candidates rather than rewording them (user: natural questions only),
and reports the refused share per plant so the loss is visible.

This module holds the pure rules; the question generator (`qa/questions`, frozen by freeze E9)
calls them. It reads a plant graph only: a node's `tag` attribute is missing when it prints none.

Two rules and a constant:

- an isolation answer (a set of valve tags) that holds an untagged valve is refused;
- a FLOW_PATH pair whose equal-length shortest paths list different tagged items is refused
  (it extends rule F2, which breaks a tie between equal paths by tag order: with untagged valves
  dropping out of the listing, two routes can disagree on which tags the answer holds);
- the two isolation families are **pre-registered unavailable** in scope R (design 11).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from plantgraph.graph.schema import EQUIPMENT_CLASSES, VALVE_CLASSES, Relation
from plantgraph.qa.models import QuestionFamily

#: families with no scope R questions on v2.2, fixed before any seed is drawn: on an untagged
#: 100-sheet plant (one document) they have no candidate, and the untagged weight is not tuned to
#: rescue them (design 11). Both arms answer them in scope X instead.
SCOPE_R_UNAVAILABLE_FAMILIES: tuple[QuestionFamily, ...] = (
    QuestionFamily.UPSTREAM_ISOLATION,
    QuestionFamily.DOWNSTREAM_ISOLATION,
)

_PATH_ITEM_CLASSES = EQUIPMENT_CLASSES | VALVE_CLASSES


class RefusedShare(BaseModel):
    """How many candidates a refusal rule removed, for the per-plant report."""

    model_config = ConfigDict(frozen=True)

    rule: str
    candidates: int = Field(ge=0)
    refused: int = Field(ge=0)

    @property
    def share(self) -> float:
        """Refused over candidates; 0.0 when there were no candidates."""
        return self.refused / self.candidates if self.candidates else 0.0


def holds_untagged_item(plant: nx.DiGraph[str], answer_nodes: Iterable[str]) -> bool:
    """True when an answer names a node that prints no tag (the isolation refusal rule)."""
    return any(not plant.nodes[node].get("tag") for node in answer_nodes)


def untagged_refusal_share(
    plant: nx.DiGraph[str], answers: Sequence[Iterable[str]]
) -> RefusedShare:
    """The share of isolation candidates (one node set each) the untagged rule refuses."""
    refused = sum(holds_untagged_item(plant, nodes) for nodes in answers)
    return RefusedShare(rule="untagged_answer", candidates=len(answers), refused=refused)


def tagged_sequences_differ(plant: nx.DiGraph[str], source: str, target: str) -> bool:
    """FLOW_PATH tie rule: do equal-length shortest paths list different tagged items?

    Walks the layers of shortest paths from `source` to `target` once, keeping the distinct
    tagged sequences that reach each node, and stops counting at two.

    Raises:
        ValueError: `target` cannot be reached from `source` over `send_to`.
    """
    flow = _flow_graph(plant)
    from_source = nx.single_source_shortest_path_length(flow, source)
    if target not in from_source:
        raise ValueError(f"expected {target!r} reachable from {source!r} over send_to, found not")
    to_target = nx.single_source_shortest_path_length(flow.reverse(copy=False), target)
    length = from_source[target]
    # a node is on some shortest path when its two distances add up to the whole length
    on_shortest = {n for n, d in from_source.items() if d + to_target.get(n, length + 1) == length}
    sequences: dict[str, set[tuple[str, ...]]] = {source: {_listing(plant, source)}}
    for node in sorted(on_shortest, key=from_source.__getitem__):
        for successor in flow.successors(node):
            if successor in on_shortest and from_source[successor] == from_source[node] + 1:
                reached = sequences.setdefault(successor, set())
                reached.update((*seq, *_listing(plant, successor)) for seq in sequences[node])
                # two distinct sequences already decide the answer, and stay distinct downstream
                sequences[successor] = set(sorted(reached)[:2])
    return len(sequences[target]) > 1


def _flow_graph(plant: nx.DiGraph[str]) -> nx.DiGraph[str]:
    """Only the piping edges."""
    return nx.DiGraph(
        (s, t) for s, t, d in plant.edges(data=True) if d["relation"] == Relation.SEND_TO.value
    )


def _listing(plant: nx.DiGraph[str], node: str) -> tuple[str, ...]:
    """What a path answer lists for a node: its tag when it is a tagged item, else nothing."""
    data = plant.nodes[node]
    if data["node_class"] in _PATH_ITEM_CLASSES and data.get("tag"):
        return (str(data["tag"]),)
    return ()
