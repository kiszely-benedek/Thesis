"""Strategy names to constructors, so a run's config can name strategies as plain strings.

Most strategies need only the corpus view. CypherRAG also needs a database
connection and a way to call the LLM, so it is built from `CypherDeps`;
Hierarchical, and the need-aware variant built on it, need a way to call the LLM
only for the router fallback, so they take `LlmDeps`. The runner supplies both. Add a strategy
here when it is built; the harness needs no other change.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.need.rules import RuleNeedClassifier
from plantgraph.qa.strategies.base import Strategy
from plantgraph.qa.strategies.context_rag import ContextRag
from plantgraph.qa.strategies.cypher_rag import CypherRag
from plantgraph.qa.strategies.hierarchical import Hierarchical
from plantgraph.qa.strategies.hierarchical_need import NeedAwareHierarchical, need_strategy_name
from plantgraph.qa.unit_router import UnitRouter

StrategyFactory = Callable[[GraphView, dict[str, Any]], Strategy]

#: Parameters of Hierarchical and of every need-aware variant (the latter's fallback).
_HIERARCHICAL_PARAMS = ("route_mode", "budget_mode", "sheet_hops", "max_context_chars")
_NEED_RULES_NAME = need_strategy_name(RuleNeedClassifier.name)

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
        ValueError: `name` is not registered, or CypherRAG, Hierarchical or a need-aware
            variant is asked for without a parameter it has no default for (all set on
            dev corpora).
    """
    if name == CypherRag.name:
        return _build_cypher_rag(params, cypher)
    if name == Hierarchical.name:
        return _build_hierarchical(params, view, llm)
    if name == _NEED_RULES_NAME:
        return _build_need_rules(params, view, llm)
    factory = STRATEGY_FACTORIES.get(name)
    if factory is None:
        known = sorted([*STRATEGY_FACTORIES, CypherRag.name, Hierarchical.name, _NEED_RULES_NAME])
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
    _require_hierarchical_params(Hierarchical.name, params)
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


def _build_need_rules(
    params: dict[str, Any], view: GraphView, llm: LlmDeps | None
) -> NeedAwareHierarchical:
    """The rules classifier needs no model; `llm` serves only the fallback's router."""
    _require_hierarchical_params(_NEED_RULES_NAME, params)
    router = UnitRouter(view, llm.pin, llm.send) if llm is not None else None
    return NeedAwareHierarchical(
        view,
        RuleNeedClassifier(),
        route_mode=params["route_mode"],
        budget_mode=params["budget_mode"],
        sheet_hops=int(params["sheet_hops"]),
        max_context_chars=int(params["max_context_chars"]),
        unit_router=router,
    )


def _require_hierarchical_params(strategy_name: str, params: dict[str, Any]) -> None:
    missing = [key for key in _HIERARCHICAL_PARAMS if key not in params]
    if missing:
        # no default: route and budget are picked by ADR-0030's rule, the rest in the pilot
        raise ValueError(
            f"expected {strategy_name} params to include {missing}, found {sorted(params)}"
        )
