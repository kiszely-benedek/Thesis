"""Strategy names to constructors, so a run's config can name strategies as plain strings.

Most strategies need only the corpus view. CypherRAG also needs a database
connection and a way to call the LLM, so it is built from `CypherDeps`, which
the runner supplies. Add a strategy here when it is built; the harness needs
no other change.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.strategies.base import Strategy
from plantgraph.qa.strategies.context_rag import ContextRag
from plantgraph.qa.strategies.cypher_rag import CypherRag

StrategyFactory = Callable[[GraphView, dict[str, Any]], Strategy]

STRATEGY_FACTORIES: dict[str, StrategyFactory] = {
    ContextRag.name: lambda view, _params: ContextRag(view),
}


@dataclass(frozen=True)
class CypherDeps:
    """What CypherRAG needs besides its parameters: the database, the model and a sender."""

    source: CypherSource
    pin: ModelPin
    send: SendChatRequest


def build_strategy(
    name: str, params: dict[str, Any], view: GraphView, cypher: CypherDeps | None = None
) -> Strategy:
    """Construct the strategy called `name` over `view`.

    Raises:
        ValueError: `name` is not registered, or CypherRAG is asked for without
            `cypher` or without its `timeout_s` and `row_cap` parameters.
    """
    if name == CypherRag.name:
        return _build_cypher_rag(params, cypher)
    factory = STRATEGY_FACTORIES.get(name)
    if factory is None:
        known = sorted([*STRATEGY_FACTORIES, CypherRag.name])
        raise ValueError(f"expected a strategy in {known}, found {name!r}")
    return factory(view, params)


def _build_cypher_rag(params: dict[str, Any], cypher: CypherDeps | None) -> CypherRag:
    if cypher is None:
        raise ValueError("expected a database connection for cypher_rag, found none")
    missing = [key for key in ("timeout_s", "row_cap") if key not in params]
    if missing:
        # no default: both are set in the pilot, on dev corpora (`qa-system.md` §7)
        raise ValueError(f"expected cypher_rag params to include {missing}, found {sorted(params)}")
    return CypherRag(
        cypher.source,
        cypher.pin,
        cypher.send,
        timeout_s=float(params["timeout_s"]),
        row_cap=int(params["row_cap"]),
    )
