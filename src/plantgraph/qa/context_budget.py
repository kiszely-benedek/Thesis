"""Serialize the selected sheets and, if too long, cut them down (design §3.4, ADR-0030).

The limit is `max_context_chars` on the serialized text. Two ways to cut,
which differ only in what happens to a route that is itself too long:

- `drop_rings`: drop the outer rings, then unit-only sheets. A route sheet is
  never cut.
- `through_line`: the same, then replace route sheets by their *through-line*
  (only the occurrences the route uses), the sheet farthest from the anchors
  first.

Tag-anchor sheets and route sheets are never removed. If the core alone is
still too long it is sent anyway and flagged `over_budget`: the shared fit
check (`fit.py`) then decides, so no silent cut can hide a failure.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Literal

from plantgraph.qa.context_render import ContextRenderer, OccurrenceRenderer, Rendered
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.sheet_selection import SheetSelection

BudgetMode = Literal["drop_rings", "through_line"]
BUDGET_MODES: tuple[BudgetMode, ...] = ("drop_rings", "through_line")


@dataclass(frozen=True)
class FittedContext:
    """The text to send and what was kept, for the trace."""

    text: str
    #: Every sheet with any content in `text`, sorted (full or through-line).
    sheets: tuple[str, ...]
    through_line_sheets: tuple[str, ...]
    #: Local keys of every serialized occurrence, sorted.
    keys: tuple[str, ...]
    rings_dropped: int
    #: True when anything was dropped or compressed.
    truncated: bool
    #: True when even the thinnest plan is longer than the limit.
    over_budget: bool
    #: Plant items shown, frontier included (0 for the occurrence representation).
    items: int
    frontier_items: int
    #: Every sheet any shown node is drawn on, sorted.
    context_sheets: tuple[str, ...]


@dataclass(frozen=True)
class _Plan:
    """How much of each cuttable part is still in: counts, so a plan is a few integers."""

    rings_kept: int
    unit_sheets_dropped: int
    route_sheets_compressed: int


def fit_to_budget(
    view: GraphView,
    selection: SheetSelection,
    budget_mode: BudgetMode,
    max_context_chars: int,
    renderer: ContextRenderer | None = None,
) -> FittedContext:
    """The fullest plan whose rendered text is within `max_context_chars`, else the thinnest.

    `renderer` defaults to the occurrence representation, as before; the plans and the order
    of cuts do not depend on it, only the lengths do.
    """
    fitter = _Fitter(renderer or OccurrenceRenderer(view), selection, budget_mode)
    chosen = fitter.full_plan
    for chosen in fitter.plans():  # fullest first, so the first plan that fits is the best one
        rendered = fitter.render(chosen)
        if len(rendered.text) <= max_context_chars:
            break
    return FittedContext(
        text=rendered.text,
        sheets=rendered.sheets,
        through_line_sheets=rendered.through_line_sheets,
        keys=rendered.keys,
        rings_dropped=len(selection.rings) - chosen.rings_kept,
        truncated=chosen != fitter.full_plan,
        over_budget=len(rendered.text) > max_context_chars,
        items=rendered.items,
        frontier_items=rendered.frontier_items,
        context_sheets=rendered.context_sheets,
    )


class _Fitter:
    def __init__(
        self, renderer: ContextRenderer, selection: SheetSelection, budget_mode: BudgetMode
    ) -> None:
        self._renderer = renderer
        self._selection = selection
        self._budget_mode = budget_mode
        # Ascending, so "drop the highest id first" keeps a prefix of this list.
        self._unit_only = sorted(
            selection.unit_sheets - selection.tag_sheets - selection.route_sheets
        )
        self._compress_order = self._farthest_first() if budget_mode == "through_line" else []

    def _farthest_first(self) -> list[str]:
        """Compressible route sheets, those farthest from every anchor first; ties by sheet id."""
        selection = self._selection
        return sorted(
            selection.through_lines, key=lambda s: (-selection.distance_from_anchors.get(s, 0), s)
        )

    @property
    def full_plan(self) -> _Plan:
        """Everything selected, nothing cut."""
        return _Plan(len(self._selection.rings), 0, 0)

    def plans(self) -> Iterator[_Plan]:
        """From the fullest plan to the thinnest, in the order the design drops things."""
        plan = self.full_plan
        yield plan
        for rings_kept in range(plan.rings_kept - 1, -1, -1):
            plan = replace(plan, rings_kept=rings_kept)
            yield plan
        for dropped in range(1, len(self._unit_only) + 1):
            plan = replace(plan, unit_sheets_dropped=dropped)
            yield plan
        for compressed in range(1, len(self._compress_order) + 1):
            plan = replace(plan, route_sheets_compressed=compressed)
            yield plan

    def render(self, plan: _Plan) -> Rendered:
        selection = self._selection
        compressed = self._compress_order[: plan.route_sheets_compressed]
        through = {sheet: selection.through_lines[sheet] for sheet in compressed}
        dropped_units = self._unit_only[len(self._unit_only) - plan.unit_sheets_dropped :]
        full = (
            (
                selection.tag_sheets
                | selection.unit_sheets
                | selection.route_sheets
                | frozenset().union(*selection.rings[: plan.rings_kept])
            )
            - set(dropped_units)
            - set(compressed)
        )
        return self._renderer.render(frozenset(full), through)
