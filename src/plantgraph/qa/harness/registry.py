"""Strategy names to constructors, so a run's config can name strategies as plain strings.

Add a strategy here when it is built (T12 onwards); the harness needs no other change.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.strategies.base import Strategy
from plantgraph.qa.strategies.context_rag import ContextRag

StrategyFactory = Callable[[GraphView, dict[str, Any]], Strategy]

STRATEGY_FACTORIES: dict[str, StrategyFactory] = {
    ContextRag.name: lambda view, _params: ContextRag(view),
}


def build_strategy(name: str, params: dict[str, Any], view: GraphView) -> Strategy:
    """Construct the strategy called `name` over `view`.

    Raises:
        ValueError: `name` is not registered.
    """
    factory = STRATEGY_FACTORIES.get(name)
    if factory is None:
        raise ValueError(f"expected a strategy in {sorted(STRATEGY_FACTORIES)}, found {name!r}")
    return factory(view, params)
