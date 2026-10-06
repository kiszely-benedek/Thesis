"""Strategy names to constructors, so a run's config can name strategies as plain strings.

Most strategies need only the corpus view. CypherRAG also needs a database
connection and a way to call the LLM, so it is built from `CypherDeps`;
Hierarchical, and the need-aware variant built on it, need a way to call the LLM
only for the router fallback, so they take `LlmDeps`; the two agents (`graph_agent`, `hier_agent`)
call it at every step and always read the merged plant. The runner supplies both. Each of the two
exists in two representations, told apart by name and never by a parameter (ADR-0039): the
unsuffixed one prints the occurrence graph, the `_plant` one the merged plant; CypherRAG has the
same pair, `cypher_rag` and `cypher_rag_plant`, reading differently loaded stores. Add a strategy
here when it is built; the harness needs no other change.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from plantgraph.llm.models import ModelPin
from plantgraph.qa.agent.models import AgentParams
from plantgraph.qa.agent.strategies import GRAPH_AGENT_NAME, HIER_AGENT_NAME, GraphAgent, HierAgent
from plantgraph.qa.context_render import (
    REPRESENTATIONS,
    ContextRenderer,
    OccurrenceRenderer,
    PlantRenderer,
    Representation,
)
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.need.rules import RuleNeedClassifier
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.strategies.base import Strategy
from plantgraph.qa.strategies.context_rag import ContextRag
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME, CypherRag
from plantgraph.qa.strategies.hierarchical import Hierarchical, hierarchical_name
from plantgraph.qa.strategies.hierarchical_need import NeedAwareHierarchical, need_strategy_name
from plantgraph.qa.unit_router import UnitRouter

StrategyFactory = Callable[[GraphView, dict[str, Any]], Strategy]

#: Parameters of Hierarchical and of every need-aware variant (the latter's fallback).
_HIERARCHICAL_PARAMS = ("route_mode", "budget_mode", "sheet_hops", "max_context_chars")
#: Strategy name -> representation, for the two Hierarchical families.
_HIERARCHICAL_NAMES: dict[str, Representation] = {
    hierarchical_name(rep): rep for rep in REPRESENTATIONS
}
_NEED_RULES_NAMES: dict[str, Representation] = {
    need_strategy_name(RuleNeedClassifier.name, rep): rep for rep in REPRESENTATIONS
}

_AGENT_NAMES = (GRAPH_AGENT_NAME, HIER_AGENT_NAME)

STRATEGY_FACTORIES: dict[str, StrategyFactory] = {
    ContextRag.name: lambda view, _params: ContextRag(view),
}


@dataclass(frozen=True)
class CypherDeps:
    """What CypherRAG needs besides its parameters: the database, the model and a sender."""

    source: CypherSource
    pin: ModelPin
    send: SendChatRequest
    #: Whether the query-writing prompt carries the P&ID reading primer (`RunConfig.primer`).
    primer: bool = False


@dataclass(frozen=True)
class LlmDeps:
    """How a strategy that only sometimes asks the LLM does so: the answer model and a sender."""

    pin: ModelPin
    send: SendChatRequest
    #: Whether an agent's system prompt carries the P&ID reading primer (`RunConfig.primer`).
    primer: bool = False


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
    if name in PROFILE_OF_NAME:
        return _build_cypher_rag(name, params, cypher)
    if name in _HIERARCHICAL_NAMES:
        return _build_hierarchical(name, _HIERARCHICAL_NAMES[name], params, view, llm)
    if name in _NEED_RULES_NAMES:
        return _build_need_rules(name, _NEED_RULES_NAMES[name], params, view, llm)
    if name in _AGENT_NAMES:
        return _build_agent(name, params, view, llm)
    factory = STRATEGY_FACTORIES.get(name)
    if factory is None:
        known = sorted(
            [
                *STRATEGY_FACTORIES,
                *PROFILE_OF_NAME,
                *_HIERARCHICAL_NAMES,
                *_NEED_RULES_NAMES,
                *_AGENT_NAMES,
            ]
        )
        raise ValueError(f"expected a strategy in {known}, found {name!r}")
    return factory(view, params)


def _build_cypher_rag(name: str, params: dict[str, Any], cypher: CypherDeps | None) -> CypherRag:
    if cypher is None:
        raise ValueError(f"expected a database connection for {name}, found none")
    missing = [key for key in ("timeout_s", "row_cap") if key not in params]
    if missing:
        # no default: both are set in the pilot, on dev corpora (`qa-system.md` §7)
        raise ValueError(f"expected {name} params to include {missing}, found {sorted(params)}")
    return CypherRag(
        cypher.source,
        cypher.pin,
        cypher.send,
        timeout_s=float(params["timeout_s"]),
        row_cap=int(params["row_cap"]),
        primer=cypher.primer,
        profile=PROFILE_OF_NAME[name],
    )


def _build_hierarchical(
    name: str,
    representation: Representation,
    params: dict[str, Any],
    view: GraphView,
    llm: LlmDeps | None,
) -> Hierarchical:
    _require_hierarchical_params(name, params)
    renderer = _renderer(name, representation, params, view, _plant_of(representation, view))
    # with no `llm` (a free, retrieval-only run) a question with no anchor fails instead of calling
    router = UnitRouter(view, llm.pin, llm.send) if llm is not None else None
    return Hierarchical(
        view,
        route_mode=params["route_mode"],
        budget_mode=params["budget_mode"],
        sheet_hops=int(params["sheet_hops"]),
        max_context_chars=int(params["max_context_chars"]),
        unit_router=router,
        renderer=renderer,
    )


def _build_need_rules(
    name: str,
    representation: Representation,
    params: dict[str, Any],
    view: GraphView,
    llm: LlmDeps | None,
) -> NeedAwareHierarchical:
    """The rules classifier needs no model; `llm` serves only the fallback's router."""
    _require_hierarchical_params(name, params)
    plant = _plant_of(representation, view)
    renderer = _renderer(name, representation, params, view, plant)
    router = UnitRouter(view, llm.pin, llm.send) if llm is not None else None
    return NeedAwareHierarchical(
        view,
        RuleNeedClassifier(),
        route_mode=params["route_mode"],
        budget_mode=params["budget_mode"],
        sheet_hops=int(params["sheet_hops"]),
        max_context_chars=int(params["max_context_chars"]),
        unit_router=router,
        renderer=renderer,
        item_graph=plant,
    )


def _build_agent(
    name: str, params: dict[str, Any], view: GraphView, llm: LlmDeps | None
) -> GraphAgent:
    """An agent over the merged plant; `params` may override the loop limits (`AgentParams`)."""
    if llm is None:
        raise ValueError(f"expected a model sender for {name} (it calls the model), found none")
    loop_params = AgentParams.model_validate(params)  # unknown keys are an error
    plant = build_item_graph(view)
    if name == HIER_AGENT_NAME:
        return HierAgent(view, plant, llm.pin, llm.send, params=loop_params, primer=llm.primer)
    return GraphAgent(plant, llm.pin, llm.send, params=loop_params, primer=llm.primer)


def _plant_of(representation: Representation, view: GraphView) -> ItemGraph | None:
    """The merged plant for a plant arm (built once, shared by renderer and programs)."""
    return build_item_graph(view) if representation == "plant" else None


def _renderer(
    name: str,
    representation: Representation,
    params: dict[str, Any],
    view: GraphView,
    plant: ItemGraph | None,
) -> ContextRenderer:
    """The plant renderer (legend always on), or the occurrence one with its optional legend."""
    if plant is not None:
        if "legend" in params:
            raise ValueError(
                f"expected no legend param for {name} (always on), found {params['legend']!r}"
            )
        return PlantRenderer(plant)
    legend = params.get("legend", False)
    if not isinstance(legend, bool):
        raise ValueError(f"expected legend to be true or false for {name}, found {legend!r}")
    return OccurrenceRenderer(view, legend=legend)


def _require_hierarchical_params(strategy_name: str, params: dict[str, Any]) -> None:
    missing = [key for key in _HIERARCHICAL_PARAMS if key not in params]
    if missing:
        # no default: route and budget are picked by ADR-0030's rule, the rest in the pilot
        raise ValueError(
            f"expected {strategy_name} params to include {missing}, found {sorted(params)}"
        )
