"""B strategy names to constructors (the B twin of `harness/registry.py`, design §10 R6).

A B run names only `*_b` strategies. Each is built over the B corpus: `cypher_rag_lines_b` over the
Neo4j view that holds the positions, `graph_agent_lines_b` over an item graph that carries them.
"""

from __future__ import annotations

from typing import Any

from plantgraph.qa.agent.models import AgentParams
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.harness.registry import CypherDeps, LlmDeps
from plantgraph.qa.strategies.base import Strategy
from plantgraph.qa.v2tb.item_graph_b import build_item_graph_b
from plantgraph.qa.v2tb.strategies_b import (
    CYPHER_RAG_LINES_B_NAME,
    GRAPH_AGENT_LINES_B_NAME,
    CypherRagLinesB,
    GraphAgentLinesB,
)

B_STRATEGY_NAMES: tuple[str, ...] = (CYPHER_RAG_LINES_B_NAME, GRAPH_AGENT_LINES_B_NAME)


def build_strategy_b(
    name: str,
    params: dict[str, Any],
    view: GraphView,
    cypher: CypherDeps | None = None,
    llm: LlmDeps | None = None,
) -> Strategy:
    """Construct the B strategy called `name` over `view`.

    Raises:
        ValueError: `name` is not a B strategy, or the strategy lacks its database connection,
            its model sender or a parameter it has no default for.
    """
    if name == CYPHER_RAG_LINES_B_NAME:
        return _build_cypher(name, params, cypher)
    if name == GRAPH_AGENT_LINES_B_NAME:
        return _build_agent(name, params, view, llm)
    raise ValueError(f"expected a strategy in {sorted(B_STRATEGY_NAMES)}, found {name!r}")


def _build_cypher(name: str, params: dict[str, Any], cypher: CypherDeps | None) -> CypherRagLinesB:
    if cypher is None:
        raise ValueError(f"expected a database connection for {name}, found none")
    missing = [key for key in ("timeout_s", "row_cap") if key not in params]
    if missing:
        raise ValueError(f"expected {name} params to include {missing}, found {sorted(params)}")
    return CypherRagLinesB(
        cypher.source,
        cypher.pin,
        cypher.send,
        timeout_s=float(params["timeout_s"]),
        row_cap=int(params["row_cap"]),
        primer=cypher.primer,
    )


def _build_agent(
    name: str, params: dict[str, Any], view: GraphView, llm: LlmDeps | None
) -> GraphAgentLinesB:
    if llm is None:
        raise ValueError(f"expected a model sender for {name} (it calls the model), found none")
    return GraphAgentLinesB(
        build_item_graph_b(view, line_view=True),
        llm.pin,
        llm.send,
        params=AgentParams.model_validate(params),  # unknown keys are an error
        primer=llm.primer,
        remaining_s=llm.remaining_s,
    )
