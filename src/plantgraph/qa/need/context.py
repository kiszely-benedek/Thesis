"""From a program's selection to the text sent to the model (design §4.4).

The **core** is every sheet of every anchor, whole: a misread question then still gets the
anchors' own pages. The **need part** is what the program reached on *other* sheets: only
those items' drawings, plus the off-page connector stubs of the edges that lead to them, so a
line that crosses a sheet boundary stays visible. Both are serialized by the shared serializer
(`serialize_graph`), so this is still "ContextRAG on a selected subset".

Budget: when the text is over `max_context_chars`, the need items farthest from the anchors go
first (ties by tag). The core is never cut; if it alone is too long it is sent and flagged
`over_budget`, and the shared fit check (`fit.py`) decides what happens to it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from plantgraph.qa.anchors import Anchors
from plantgraph.qa.context_render import ContextRenderer, OccurrenceRenderer, Rendered
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.need.programs import NeedSelection, SelectedItem
from plantgraph.qa.plant_api.model import ItemEdge, sheet_of_key


@dataclass(frozen=True)
class NeedContext:
    """The text to send and what it holds, for the trace."""

    text: str
    #: Every sheet with any content in `text`, sorted.
    sheets: tuple[str, ...]
    #: The need-part sheets: only the selected drawings of each are in `text`.
    through_line_sheets: tuple[str, ...]
    #: Local keys of every serialized occurrence, sorted.
    keys: tuple[str, ...]
    #: Items the program reached with a drawing outside the core (the cuttable ones).
    need_items: int
    need_items_dropped: int
    over_budget: bool
    #: Plant items shown, frontier included (0 for the occurrence representation).
    items: int
    frontier_items: int
    #: Every sheet any shown node is drawn on, sorted.
    context_sheets: tuple[str, ...]


@dataclass(frozen=True)
class _Cuttable:
    """A need item outside the core, with the keys it adds: its drawings and its edges' stubs."""

    item: SelectedItem
    keys: tuple[str, ...]


def core_sheets(view: GraphView, anchors: Anchors) -> frozenset[str]:
    """Every sheet of every tag anchor and of every unit anchor."""
    tag_sheets = {sheet for tag in anchors.tags for sheet in tag.sheet_ids}
    unit_sheets = {s for unit in anchors.units for s in view.sheets_of_unit(unit.unit_id)}
    return frozenset(tag_sheets | unit_sheets)


def build_need_context(
    view: GraphView,
    core: frozenset[str],
    selection: NeedSelection,
    max_context_chars: int,
    renderer: ContextRenderer | None = None,
) -> NeedContext:
    """Serialize the core plus as much of the need part as fits.

    Args:
        view: the corpus the sheets and keys come from.
        core: the sheets sent whole (`core_sheets`).
        selection: what the program reached.
        max_context_chars: the limit on the rendered text.
        renderer: occurrence by default; the plant renderer maps the same keys to items.
    """
    renderer = renderer or OccurrenceRenderer(view)
    cuttable = _cuttable_items(core, selection)
    kept = _most_that_fits(renderer, core, cuttable, max_context_chars)
    rendered = _render(renderer, core, cuttable[:kept])
    return NeedContext(
        text=rendered.text,
        sheets=rendered.sheets,
        through_line_sheets=rendered.through_line_sheets,
        keys=rendered.keys,
        need_items=len(cuttable),
        need_items_dropped=len(cuttable) - kept,
        over_budget=len(rendered.text) > max_context_chars,
        items=rendered.items,
        frontier_items=rendered.frontier_items,
        context_sheets=rendered.context_sheets,
    )


def _cuttable_items(core: frozenset[str], selection: NeedSelection) -> list[_Cuttable]:
    """Items with a drawing outside the core, nearest first; each carries its edges' stubs."""
    distance = {sel.item.item_id: sel.distance for sel in selection.items}
    stubs_of: dict[str, list[str]] = defaultdict(list)
    for edge in selection.edges:
        stubs_of[_farther_end(edge, distance)] += [k for k in edge.via if _outside(k, core)]
    cuttable: list[_Cuttable] = []
    for selected in selection.items:
        drawings = [k for k in selected.item.occurrence_keys if _outside(k, core)]
        if drawings:  # an item drawn only inside the core costs nothing to keep
            keys = tuple(sorted({*drawings, *stubs_of[selected.item.item_id]}))
            cuttable.append(_Cuttable(selected, keys))
    return cuttable


def _farther_end(edge: ItemEdge, distance: dict[str, int]) -> str:
    """The end of an edge that is farther from the anchors; cutting it cuts the edge's stubs."""
    source, target = distance[edge.source], distance[edge.target]
    return edge.source if source > target else edge.target


def _outside(local_key: str, core: frozenset[str]) -> bool:
    return sheet_of_key(local_key) not in core


def _most_that_fits(
    renderer: ContextRenderer, core: frozenset[str], cuttable: list[_Cuttable], max_chars: int
) -> int:
    """How many of the nearest need items fit; 0 when even the bare core is too long.

    Binary search: text length only grows as items are added, so "fits" is true for a prefix.
    """
    if _length(renderer, core, cuttable) <= max_chars:
        return len(cuttable)
    low, high = 0, len(cuttable) - 1  # `len(cuttable)` was just ruled out
    while low < high:
        middle = (low + high + 1) // 2
        if _length(renderer, core, cuttable[:middle]) <= max_chars:
            low = middle
        else:
            high = middle - 1
    return low


def _length(renderer: ContextRenderer, core: frozenset[str], kept: list[_Cuttable]) -> int:
    return len(_render(renderer, core, kept).text)


def _render(renderer: ContextRenderer, core: frozenset[str], kept: list[_Cuttable]) -> Rendered:
    """The core whole plus, on the other sheets, only the `kept` need items' drawings."""
    by_sheet: dict[str, list[str]] = defaultdict(list)
    for cut in kept:
        for key in cut.keys:
            by_sheet[sheet_of_key(key)].append(key)
    through = {sheet: tuple(keys) for sheet, keys in by_sheet.items()}
    return renderer.render(core, through)
