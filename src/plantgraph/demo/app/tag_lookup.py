"""Tag lookup: where on the drawings is this item? (the demo's search box, no model call).

A tag is the printed identifier of an item on a drawing (for example `P-151-1`); the same item can
be drawn on several sheets. Lookup reads only the in-memory item graph, so it works for every
loaded plant whatever the graph database holds.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import dataclass

from plantgraph.demo.app.api_models import TagHit, TagLookup
from plantgraph.demo.app.models import SheetLink
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.scoring import normalize_scalar

#: How many tags a prefix may suggest.
MAX_SUGGESTIONS = 10


@dataclass(frozen=True)
class TagIndex:
    """Every tag of a plant, sorted by its folded spelling, so a prefix is one binary search."""

    #: (folded tag, tag as drawn), sorted and without repeats.
    pairs: tuple[tuple[str, str], ...]

    @classmethod
    def build(cls, item_graph: ItemGraph) -> TagIndex:
        """Index every tagged item's tag, folded as the plant API folds it (`normalize_scalar`)."""
        tags = {item_graph.item(i).tag for i in item_graph.all_ids()}
        return cls(tuple(sorted((normalize_scalar(t), t) for t in tags if t)))

    def suggest(self, query: str, limit: int = MAX_SUGGESTIONS) -> tuple[str, ...]:
        """Up to `limit` tags that start with `query` (case and spacing folded), in sorted order."""
        prefix = normalize_scalar(query)
        found: list[str] = []
        # pairs sort by folded tag, so every match follows the first one without a gap
        for folded, tag in self.pairs[bisect_left(self.pairs, (prefix, "")) :]:
            if not folded.startswith(prefix) or len(found) == limit:
                break
            found.append(tag)
        return tuple(found)


def lookup(
    query: str, item_graph: ItemGraph, index: TagIndex, pages: Mapping[str, int]
) -> TagLookup:
    """The items that carry the tag `query`, plus the tags that start with it.

    Raises:
        ValueError: an item's sheet is missing from `pages` (the PDF does not match the plant).
    """
    hits = tuple(_hit(item_id, item_graph, pages) for item_id in item_graph.ids_for_tag(query))
    return TagLookup(query=query, hits=hits, suggestions=index.suggest(query))


def _hit(item_id: str, item_graph: ItemGraph, pages: Mapping[str, int]) -> TagHit:
    item = item_graph.item(item_id)
    return TagHit(
        item_id=item_id,
        tag=item.tag,
        node_class=item.node_class,
        unit_id=item.unit_id,
        sheets=_sheet_links(item.sheets, pages),
    )


def _sheet_links(sheets: tuple[str, ...], pages: Mapping[str, int]) -> tuple[SheetLink, ...]:
    missing = [sheet for sheet in sheets if sheet not in pages]
    if missing:
        raise ValueError(f"expected every sheet to be in the drawing index, missing {missing[:3]}")
    links = [SheetLink(sheet_id=sheet, page=pages[sheet]) for sheet in sheets]
    return tuple(sorted(links, key=lambda link: (link.page, link.sheet_id)))
