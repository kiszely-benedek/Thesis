"""Strategy names to constructors, so a run's config can name strategies as plain strings.

Most strategies need only the corpus view. CypherRAG also needs a database
connection and a way to call the LLM, so it is built from `CypherDeps`;
Hierarchical needs a way to call the LLM only for its router fallback, so it
takes `LlmDeps`. The runner supplies both. Add a strategy here when it is built; the harness needs
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
from plantgraph.qa.strategies.hierarchical import Hierarchical
from plantgraph.qa.unit_router import UnitRouter

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


@dataclass(frozen=True)
class LlmDeps:
    """How a strategy that only sometimes asks the LLM does so: the answer model and a sender."""

    pin: ModelPin
    send: SendChatRequest


def build_strategy(
    name: str,
    params: dict[str, Any],
    view: GraphView,
    cypher: CypherDeps | None = None,
    llm: LlmDeps | None = None,
) -> Strategy:
    """Construct the strategy called `name` over `view`.

    Raises:
        ValueError: `name` is not registered, or CypherRAG or Hierarchical is asked
            for without a parameter it has no default for (all set on dev corpora).
    """
    if name == CypherRag.name:
        return _build_cypher_rag(params, cypher)
    if name == Hierarchical.name:
        return _build_hierarchical(params, view, llm)
    factory = STRATEGY_FACTORIES.get(name)
    if factory is None:
        known = sorted([*STRATEGY_FACTORIES, CypherRag.name, Hierarchical.name])
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


def _build_hierarchical(
    params: dict[str, Any], view: GraphView, llm: LlmDeps | None
) -> Hierarchical:
    required = ("route_mode", "budget_mode", "sheet_hops", "max_context_chars")
    missing = [key for key in required if key not in params]
    if missing:
        # no default: route and budget are picked by ADR-0030's rule, the rest in the pilot
        raise ValueError(
            f"expected hierarchical params to include {missing}, found {sorted(params)}"
        )
    # with no `llm` (a free, retrieval-only run) a question with no anchor fails instead of calling
    router = UnitRouter(view, llm.pin, llm.send) if llm is not None else None
    return Hierarchical(
        view,
        route_mode=params["route_mode"],
        budget_mode=params["budget_mode"],
        sheet_hops=int(params["sheet_hops"]),
        max_context_chars=int(params["max_context_chars"]),
        unit_router=router,
    )
