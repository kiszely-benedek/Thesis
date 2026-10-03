"""Hierarchical: send only the sheets between the items the question names (`qa-system.md` §7).

ContextRAG puts the whole plant in the prompt; this serializes a *routed
sub-corpus* with the same serializer and the same final step. Steps (design
`hierarchical-and-jev.md` §3.1):

1. find the anchors (tags, units) the question names (`anchors.py`);
2. none found: one LLM call picks units from a plant map (`unit_router.py`), counted;
3. core sheets = sheets of the anchors, plus the route between tag anchors
   (`route_mode`: `sheet_graph` or `flow_path`) and `sheet_hops` rings around them;
4. over `max_context_chars`: cut by `budget_mode` (`context_budget.py`);
5. render with the strategy's renderer: the occurrence graph, or the merged plant (ADR-0039).

Both modes of both choices are built because which is better is measured
(ADR-0030). Only the question text is read, never a gold field.
"""

from __future__ import annotations

from typing import Any

from plantgraph.llm.models import ContextOverflow
from plantgraph.qa.anchors import Anchors, extract_anchors
from plantgraph.qa.context_budget import BUDGET_MODES, BudgetMode, FittedContext, fit_to_budget
from plantgraph.qa.context_render import ContextRenderer, OccurrenceRenderer, Representation
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.models import Outcome, RetrievalResult
from plantgraph.qa.sheet_selection import (
    ROUTE_MODES,
    RouteMode,
    RoutingGraphs,
    SheetSelection,
    select_sheets,
)
from plantgraph.qa.unit_router import UnitChoice, UnitRouter, UnitRouterError


def hierarchical_name(representation: Representation) -> str:
    """`hierarchical` for the occurrence graph, `hierarchical_plant` for the merged plant."""
    return "hierarchical" if representation == "occurrence" else f"hierarchical_{representation}"


class Hierarchical:
    """Routes between the named items and renders the sheets the route needs."""

    def __init__(
        self,
        view: GraphView,
        *,
        route_mode: RouteMode,
        budget_mode: BudgetMode,
        sheet_hops: int,
        max_context_chars: int,
        unit_router: UnitRouter | None = None,
        renderer: ContextRenderer | None = None,
    ) -> None:
        """`unit_router=None` is for free, retrieval-only runs: a question with no anchor fails.

        `renderer` is the occurrence graph without a legend by default (today's text); the
        strategy's name follows the renderer's representation.

        Raises:
            ValueError: a mode is not one of the built ones, or a number is out of range.
        """
        _require_choice("route_mode", route_mode, ROUTE_MODES)
        _require_choice("budget_mode", budget_mode, BUDGET_MODES)
        if sheet_hops < 0 or max_context_chars <= 0:
            raise ValueError(
                "expected sheet_hops >= 0 and max_context_chars > 0, "
                f"found {sheet_hops} and {max_context_chars}"
            )
        self._view = view
        self._renderer = renderer or OccurrenceRenderer(view)
        self.name = hierarchical_name(self._renderer.representation)
        self._graphs = RoutingGraphs(view)
        self._route_mode: RouteMode = route_mode
        self._budget_mode: BudgetMode = budget_mode
        self._sheet_hops = sheet_hops
        self._max_context_chars = max_context_chars
        self._unit_router = unit_router

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Anchors -> (router fallback) -> sheets -> budget -> serialized context."""
        anchors = extract_anchors(question_text, self._view)
        trace: dict[str, Any] = {
            "route_mode": self._route_mode,
            "budget_mode": self._budget_mode,
            "anchors": anchor_names(anchors),
            "fallback_needed": anchors.is_empty,
            "fallback_used": False,
        }
        unit_ids = [unit.unit_id for unit in anchors.units]
        if anchors.is_empty:
            choice = self._ask_router(question_text, trace)
            if choice is None:
                return RetrievalResult(context=None, failure=Outcome.RETRIEVAL_ERROR, trace=trace)
            unit_ids = list(choice.units)
        selection = select_sheets(
            self._view,
            self._graphs,
            anchors.tags,
            unit_ids,
            route_mode=self._route_mode,
            sheet_hops=self._sheet_hops,
        )
        fitted = fit_to_budget(
            self._view, selection, self._budget_mode, self._max_context_chars, self._renderer
        )
        trace.update(_selection_trace(selection))
        trace.update(_fitted_trace(fitted, self._renderer.representation))
        return RetrievalResult(context=fitted.text, failure=None, trace=trace)

    def _ask_router(self, question_text: str, trace: dict[str, Any]) -> UnitChoice | None:
        """The fallback call; `None`, reason in `trace`, when it cannot be made or fails."""
        router = self._unit_router
        if router is None or not router.has_units:
            reason = "no router configured" if router is None else "the corpus has no unit ids"
            trace["retrieval_error"] = f"no anchor in the question and {reason}"
            return None
        trace["fallback_used"] = True
        try:
            choice = router.choose(question_text)
        except ContextOverflow as error:
            trace["retrieval_error"] = f"the plant-map prompt overflowed: {error}"
            return None
        except UnitRouterError as error:
            trace["retrieval_error"] = str(error)
            return None
        trace.update(
            router_units=list(choice.units),
            router_unknown_units=list(choice.unknown_units),
            router_call=choice.call,
        )
        return choice


def _require_choice(name: str, value: str, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"expected {name} in {list(allowed)}, found {value!r}")


def anchor_names(anchors: Anchors) -> list[str]:
    """Tags as written in the question, then units as `unit <id>`."""
    return [tag.text for tag in anchors.tags] + [f"unit {unit.unit_id}" for unit in anchors.units]


def _selection_trace(selection: SheetSelection) -> dict[str, Any]:
    return {"route_found": selection.route_found, "route_fallback": selection.route_fallback}


def _fitted_trace(fitted: FittedContext, representation: Representation) -> dict[str, Any]:
    return {
        "representation": representation,
        "serialized_items": fitted.items,
        "frontier_items": fitted.frontier_items,
        "context_sheets": list(fitted.context_sheets),
        "routed_sheets": list(fitted.sheets),
        "through_line_sheets": list(fitted.through_line_sheets),
        "serialized_keys": list(fitted.keys),
        "rings_dropped": fitted.rings_dropped,
        "truncated": fitted.truncated,
        "over_budget": fitted.over_budget,
        "context_chars": len(fitted.text),
    }
