"""Serializing a plant graph into an LLM prompt: ChatP&ID's "graph mode" (design `qa-system.md` §5).

ChatP&ID (arXiv:2603.22528v1 §3.3.1) calls this the "graph mode": the model is
given the labels, tags and properties of a graph as plain text, with internal
identifiers and embeddings stripped. `serialize_graph` is that stripping step,
built on `networkx.generate_graphml`: it keeps only the properties a person
looking at the drawing set could also read (`graph.schema.VISIBLE_NODE_PROPERTIES`
/ `VISIBLE_EDGE_PROPERTIES`, plus the `sheet_id` a strategy needs to say which
page an item is on), and drops every piece of pipeline bookkeeping (`uid`,
`corpus_id`) and the answer key entirely.

**Which graph gets serialized is a parameter, not a hardcoded choice.**
`serialize_graph` takes any `nx.DiGraph`, so ADR-0022 (still *proposed*) can
be revisited by changing one call site: `serialize_occurrence_graph` is
today's default (S1, the occurrence graph `NetworkxGraphView` builds), and a
future switch to S2 — the resolver's merged `Resolution.plant` — is calling
`serialize_graph(resolution.plant)` directly, with no change to this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.graph import schema
from plantgraph.qa.graph_view import GraphView

#: A node may additionally carry its sheet, which is not one of the
#: resolver-facing V-properties (`graph.schema`) but is exactly what a
#: strategy needs to say which page an item is on (`qa-system.md` §5).
_NODE_ALLOWED_KEYS = schema.VISIBLE_NODE_PROPERTIES | {"sheet_id"}
#: `relation` is the edge's type (`send_to`, `continues_as`, …); everything
#: else must come from the resolver-facing V-property whitelist.
_EDGE_ALLOWED_KEYS = schema.VISIBLE_EDGE_PROPERTIES | {"relation"}


class SerializedContext(BaseModel):
    """GraphML text for one graph, plus the character count `fit.py`'s wall check needs."""

    model_config = ConfigDict(frozen=True)

    text: str
    character_count: int


def serialize_graph(graph: nx.DiGraph[str]) -> SerializedContext:
    """Render `graph` as visible-only GraphML text (ChatP&ID's graph mode, §5).

    Deterministic: nodes and edges are written in sorted key order, so the
    same graph content always serializes to the same bytes, regardless of
    the order its nodes were built in.

    Raises:
        ValueError: a node has no `sheet_id` attribute, meaning `graph` was
            not built by `NetworkxGraphView` or an equivalent producer.
    """
    clean = _visible_only_copy(graph)
    text = "\n".join(nx.generate_graphml(clean))
    return SerializedContext(text=text, character_count=len(text))


def serialize_occurrence_graph(view: GraphView) -> SerializedContext:
    """Serialize the whole corpus as the occurrence graph (ADR-0022 S1, today's default).

    This is what ContextRAG sends verbatim, and what Hierarchical sends for
    its routed sheet subset (`qa-system.md` §7): both call `view.subgraph`,
    Hierarchical with a smaller `sheet_ids`.
    """
    return serialize_graph(view.subgraph(view.sheets()))


def _visible_only_copy(graph: nx.DiGraph[str]) -> nx.DiGraph[str]:
    """A fresh graph holding only whitelisted properties, in sorted node/edge order."""
    clean: nx.DiGraph[str] = nx.DiGraph()
    for local_key in sorted(graph.nodes):
        clean.add_node(local_key, **_visible_node_attrs(local_key, graph.nodes[local_key]))
    for source, target in sorted(graph.edges):
        clean.add_edge(source, target, **_visible_edge_attrs(graph.edges[source, target]))
    return clean


def _visible_node_attrs(
    local_key: str, attrs: Mapping[str, Any]
) -> dict[str, str | int | float | bool]:
    if not isinstance(attrs.get("sheet_id"), str):
        raise ValueError(f"occurrence {local_key!r} has no sheet_id attribute: {dict(attrs)!r}")
    return {
        key: graphml_safe(value)
        for key, value in sorted(attrs.items())
        if key in _NODE_ALLOWED_KEYS and value is not None
    }


def _visible_edge_attrs(attrs: Mapping[str, Any]) -> dict[str, str | int | float | bool]:
    return {
        key: graphml_safe(value)
        for key, value in sorted(attrs.items())
        if key in _EDGE_ALLOWED_KEYS and value is not None
    }


def graphml_safe(value: Any) -> str | int | float | bool:
    """GraphML has no list type (`networkx.generate_graphml` rejects one outright).

    `dexpi_labels`, an imported `GenericItem`'s ancestor-class chain
    (ADR-0016), is the one visible property that is a list — joined with
    `|`, a character no class or label name contains.
    """
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)
