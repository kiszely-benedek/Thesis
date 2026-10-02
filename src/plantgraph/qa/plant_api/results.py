"""What each primitive returns, and how it renders to bounded text (design §3.3).

Every result carries its `handle` (`"$r<n>"`, the name a later call uses to
pass the result's items on), reports `touched_keys` (the drawings it shows,
for the trace and evidence recall) and renders itself to at most `max_chars`.
Rendering never prints an item id: an item is its tag, class, unit and sheets.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.plant_api.model import GroupBy, ItemEdge, ItemRecord, sheet_of_key

DEFAULT_MAX_CHARS = 4_000
DEFAULT_MAX_ITEMS = 50
_NOT_SHOWN = "({n} more not shown; narrow with filter or aggregate)"


class ItemSet(BaseModel):
    """Items from `find` or `filter`: the first few, plus the full count."""

    model_config = ConfigDict(frozen=True)

    handle: str
    items: tuple[ItemRecord, ...]
    #: Matches in total; larger than `len(items)` when the list was cut.
    total: int

    @property
    def touched_keys(self) -> tuple[str, ...]:
        """Local keys of every drawing of every listed item, sorted."""
        return _keys_of(self.items)

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Header with the total, then one line per item."""
        shown = self.items[:max_items]
        lines = [item_line(item) for item in shown]
        header = f"{self.handle}: {self.total} items"
        return _frame(header, lines, self.total - len(shown), max_chars)


class SubgraphMember(BaseModel):
    """One item a walk reached."""

    model_config = ConfigDict(frozen=True)

    item: ItemRecord
    #: Hops from the nearest start item.
    hops: int
    #: True when the stop filter matched; the walk did not go beyond it.
    is_stop: bool = False


class Subgraph(BaseModel):
    """Items reached by `neighbours` or `traverse`, and the edges walked to reach them."""

    model_config = ConfigDict(frozen=True)

    handle: str
    #: The items the walk began at; listed only so edge lines can name them.
    start: tuple[ItemRecord, ...]
    members: tuple[SubgraphMember, ...]
    edges: tuple[ItemEdge, ...]
    total_items: int
    total_edges: int

    @property
    def touched_keys(self) -> tuple[str, ...]:
        """Local keys of the start items, members and every stub an edge crosses, sorted."""
        drawn = _keys_of([*self.start, *(m.item for m in self.members)])
        stubs = (key for edge in self.edges for key in edge.via)
        return tuple(sorted({*drawn, *stubs}))

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Header, one line per item (with hops), then one line per edge."""
        members = self.members[:max_items]
        edges = self.edges[:max_items]
        names = {item.item_id: item for item in [*self.start, *(m.item for m in self.members)]}
        lines = [_member_line(member) for member in members]
        lines += [edge_line(edge, names) for edge in edges]
        header = f"{self.handle}: {self.total_items} items, {self.total_edges} edges"
        hidden = (self.total_items - len(members)) + (self.total_edges - len(edges))
        return _frame(header, lines, hidden, max_chars)


class PathResult(BaseModel):
    """The shortest path between two items, or the fact that there is none."""

    model_config = ConfigDict(frozen=True)

    handle: str
    #: The tags (or handles) the caller named, for the header.
    source: str
    target: str
    found: bool
    #: Edges on the whole path; `None` when there is no path.
    hops: int | None
    #: The first items along the path in order (cut at the item limit); empty if not found.
    items: tuple[ItemRecord, ...]
    #: Edges between the listed items.
    edges: tuple[ItemEdge, ...]
    #: Every sheet the whole path touches, in order of first visit.
    sheets: tuple[str, ...]

    @property
    def touched_keys(self) -> tuple[str, ...]:
        """Local keys of the listed drawings and the stubs between them, sorted."""
        stubs = (key for edge in self.edges for key in edge.via)
        return tuple(sorted({*_keys_of(self.items), *stubs}))

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Header with hop count and sheets, then the items in order, then the edges."""
        if self.hops is None:
            header = f"{self.handle}: no path from {self.source} to {self.target}"
            return _frame(header, [], 0, max_chars)
        shown = self.items[:max_items]
        names = {item.item_id: item for item in shown}
        edges = [edge for edge in self.edges if edge.source in names and edge.target in names]
        lines = [item_line(item) for item in shown]
        lines += [edge_line(edge, names) for edge in edges]
        header = (
            f"{self.handle}: path {self.source} to {self.target}, {self.hops} hops, "
            f"sheets {','.join(self.sheets)}"
        )
        hidden = (self.hops + 1) - len(shown)
        return _frame(header, lines, hidden, max_chars)


class TableRow(BaseModel):
    """One group of an aggregate: its name, size and a few example tags."""

    model_config = ConfigDict(frozen=True)

    group: str
    count: int
    #: The first few tags in the group, in tag order; fewer than `count` when cut.
    tags: tuple[str, ...]
    #: Local keys of the drawings behind `tags`, for the trace.
    keys: tuple[str, ...]


class Table(BaseModel):
    """Items grouped and counted, largest group first."""

    model_config = ConfigDict(frozen=True)

    handle: str
    group_by: GroupBy
    rows: tuple[TableRow, ...]
    total_items: int
    total_groups: int

    @property
    def touched_keys(self) -> tuple[str, ...]:
        """Local keys behind the example tags shown, sorted."""
        return tuple(sorted({key for row in self.rows for key in row.keys}))

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Header, then one `group: count (example tags)` line per group."""
        shown = self.rows[:max_items]
        lines = [_row_line(row) for row in shown]
        header = (
            f"{self.handle}: {self.total_items} items in {self.total_groups} groups "
            f"by {self.group_by}"
        )
        return _frame(header, lines, self.total_groups - len(shown), max_chars)


#: Anything a primitive can return.
PlantResult = ItemSet | Subgraph | PathResult | Table


# --- line formats -------------------------------------------------------------


def item_label(item: ItemRecord) -> str:
    """The tag, or a class placeholder for an untagged item such as a stub."""
    return item.tag if item.tag is not None else f"[untagged {item.node_class}]"


def item_line(item: ItemRecord) -> str:
    """`TAG (Class, unit U, sheets S1,S2)`; the unit is omitted when the item has none."""
    unit = f", unit {item.unit_id}" if item.unit_id is not None else ""
    return f"{item_label(item)} ({item.node_class}{unit}, sheets {','.join(item.sheets)})"


def edge_line(edge: ItemEdge, names: Mapping[str, ItemRecord]) -> str:
    """`A -send_to-> B [crosses S3→S4]`; the crossing shows only for an off-page edge."""
    line = f"{item_label(names[edge.source])} -{edge.relation}-> {item_label(names[edge.target])}"
    if not edge.via:
        return line
    return f"{line} [crosses {sheet_of_key(edge.via[0])}→{sheet_of_key(edge.via[-1])}]"


def _member_line(member: SubgraphMember) -> str:
    stop = " [stop]" if member.is_stop else ""
    return f"{item_line(member.item)} [hop {member.hops}]{stop}"


def _row_line(row: TableRow) -> str:
    more = ", ..." if row.count > len(row.tags) else ""
    return f"{row.group}: {row.count} ({', '.join(row.tags)}{more})"


def _keys_of(items: Iterable[ItemRecord]) -> tuple[str, ...]:
    return tuple(sorted({key for item in items for key in item.occurrence_keys}))


def _frame(header: str, lines: Sequence[str], hidden: int, max_chars: int) -> str:
    """Header plus as many lines as fit in `max_chars`; `hidden` lines were already cut upstream."""
    kept = list(lines)
    while True:
        omitted = hidden + len(lines) - len(kept)
        top = f"{header} {_NOT_SHOWN.format(n=omitted)}" if omitted else header
        text = "\n".join([top, *kept])
        if len(text) <= max_chars or not kept:
            return text[:max_chars]
        kept.pop()
