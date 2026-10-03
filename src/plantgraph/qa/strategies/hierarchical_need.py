"""NeedAwareHierarchical: pick the context by the evidence shape the question calls for (design §4).

Hierarchical picks sheets by *where the question's anchors are*. This variant first asks a
classifier what *shape* of evidence the question needs ("everything upstream of X up to the
first valve", "the flow route between X and Y", ...), runs that shape's fixed program of
plant-API primitives from the anchors (`qa/need/`), and serializes the anchors' sheets whole
plus the items the program reached.

Whenever the classification cannot be trusted or acted on, the question goes to the generic
`Hierarchical` unchanged, so the worst case is the baseline (design §4.3):

- `generic`: the classifier says `GENERIC`;
- `low_confidence`: it gives a score below `tau`;
- `no_anchor`: the question names no item or unit (the baseline's router fallback then applies);
- `precondition`: the label's program needs more than the question names (a `PATH` with one tag).

Only the question text is read, never a gold field.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any

from plantgraph.qa.anchors import Anchors, extract_anchors
from plantgraph.qa.context_budget import BudgetMode
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.models import RetrievalResult
from plantgraph.qa.need.classifiers import NeedClassifier, NeedDecision, build_need_input
from plantgraph.qa.need.context import NeedContext, build_need_context, core_sheets
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.need.programs import NeedPreconditionError, NeedSelection, run_program
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.sheet_selection import RouteMode
from plantgraph.qa.strategies.hierarchical import Hierarchical, anchor_names
from plantgraph.qa.unit_router import UnitRouter

#: A program's result is never cut by the API's own listing limit; the budget does the cutting.
_UNCAPPED = 2**62


def need_strategy_name(classifier_name: str) -> str:
    """The strategy name of a classifier: `rules` gives `hierarchical_need_rules`."""
    return f"hierarchical_need_{classifier_name}"


class NeedAwareHierarchical:
    """Classifies the question's need, runs its program, and falls back to Hierarchical."""

    def __init__(
        self,
        view: GraphView,
        classifier: NeedClassifier,
        *,
        route_mode: RouteMode,
        budget_mode: BudgetMode,
        sheet_hops: int,
        max_context_chars: int,
        tau: float = 0.0,
        unit_router: UnitRouter | None = None,
    ) -> None:
        """The mode, hops and router parameters belong to the fallback `Hierarchical`.

        `tau` is the lowest classifier score that is acted on; a classifier that gives no
        score (the rules) ignores it. `max_context_chars` limits both paths.

        Raises:
            ValueError: `tau` is outside [0, 1], or the fallback rejects a parameter.
        """
        if not 0.0 <= tau <= 1.0:
            raise ValueError(f"expected tau in [0, 1], found {tau}")
        self.name = need_strategy_name(classifier.name)
        self._view = view
        self._classifier = classifier
        self._tau = tau
        self._max_context_chars = max_context_chars
        self._route_mode: RouteMode = route_mode
        self._budget_mode: BudgetMode = budget_mode
        self._fallback = Hierarchical(
            view,
            route_mode=route_mode,
            budget_mode=budget_mode,
            sheet_hops=sheet_hops,
            max_context_chars=max_context_chars,
            unit_router=unit_router,
        )

    @cached_property
    def _item_graph(self) -> ItemGraph:
        """The plant as merged items, built on the first question that needs a program."""
        return build_item_graph(self._view)

    def retrieve(self, question_text: str) -> RetrievalResult:
        """Classify, then either run the label's program or hand the question to Hierarchical."""
        anchors = extract_anchors(question_text, self._view)
        decision = self._classifier.classify(build_need_input(question_text, anchors))
        reason = self._reason_to_fall_back(decision, anchors)
        if reason is not None:
            return self._fall_back(question_text, decision, reason)
        api = PlantApi(self._item_graph, max_items=_UNCAPPED)
        try:
            selection = run_program(decision.label, anchors, api)
        except NeedPreconditionError as error:
            return self._fall_back(question_text, decision, "precondition", detail=str(error))
        return self._need_result(decision, anchors, selection)

    def _reason_to_fall_back(self, decision: NeedDecision, anchors: Anchors) -> str | None:
        if decision.label is NeedLabel.GENERIC:
            return "generic"
        if decision.score is not None and decision.score < self._tau:
            return "low_confidence"
        if anchors.is_empty:
            return "no_anchor"
        return None

    def _fall_back(
        self,
        question_text: str,
        decision: NeedDecision,
        reason: str,
        detail: str | None = None,
    ) -> RetrievalResult:
        """The generic Hierarchical's result, with the need decision added to its trace."""
        result = self._fallback.retrieve(question_text)
        trace = {
            **result.trace,
            **_decision_trace(decision),
            "need_used": False,
            "need_fallback_reason": reason,
            "need_fallback_detail": detail,
            "need_program": [],
            "need_items": 0,
            "need_items_dropped": 0,
        }
        return RetrievalResult(context=result.context, failure=result.failure, trace=trace)

    def _need_result(
        self, decision: NeedDecision, anchors: Anchors, selection: NeedSelection
    ) -> RetrievalResult:
        context = build_need_context(
            self._view,
            core_sheets(self._view, anchors),
            selection,
            self._max_context_chars,
        )
        trace = {
            **self._hierarchical_style_trace(anchors, context),
            **_decision_trace(decision),
            "need_used": True,
            "need_fallback_reason": None,
            "need_fallback_detail": None,
            "need_program": list(selection.program),
            "need_items": context.need_items,
            "need_items_dropped": context.need_items_dropped,
        }
        return RetrievalResult(context=context.text, failure=None, trace=trace)

    def _hierarchical_style_trace(self, anchors: Anchors, context: NeedContext) -> dict[str, Any]:
        """The keys `Hierarchical` writes, so every report reads both strategies alike."""
        return {
            "route_mode": self._route_mode,
            "budget_mode": self._budget_mode,
            "anchors": anchor_names(anchors),
            "fallback_needed": False,
            "fallback_used": False,
            "route_found": None,
            "route_fallback": None,
            "routed_sheets": list(context.sheets),
            "through_line_sheets": list(context.through_line_sheets),
            "serialized_keys": list(context.keys),
            "rings_dropped": 0,
            "truncated": context.need_items_dropped > 0,
            "over_budget": context.over_budget,
            "context_chars": len(context.text),
        }


def _decision_trace(decision: NeedDecision) -> dict[str, Any]:
    return {
        "need_label": decision.label.value,
        "need_score": decision.score,
        "need_scores": decision.scores,
        "need_classifier": decision.classifier,
        "classifier_call": decision.call,
    }
