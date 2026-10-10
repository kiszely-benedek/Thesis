"""What each primitive returns, and how it renders to bounded text (design §3.3).

Every result carries its `handle` (`"$r<n>"`, the name a later call uses to
pass the result's items on), reports `touched_keys` (the drawings it shows,
for the trace and evidence recall) and renders itself to at most `max_chars`.
Rendering never prints an item id: an item is its tag, class, unit and sheets.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.plant_api.model import (
    GroupBy,
    ItemEdge,
    ItemRecord,
    RelationGroup,
    sheet_of_key,
)

DEFAULT_MAX_CHARS = 4_000
DEFAULT_MAX_ITEMS = 50
_NOT_SHOWN_WORDS = "more not shown"
_NOT_SHOWN = "({n} " + _NOT_SHOWN_WORDS + "; narrow with filter or aggregate)"
STOP_MARK = "[stop]"
END_MARK = "[end]"
HOP_LIMIT_MARK = "[hop limit]"


class ItemSet(BaseModel):
    """Items from `find` or `filter`: the first few, plus the full count."""

    model_config = ConfigDict(frozen=True)

    handle: str
    items: tuple[ItemRecord, ...]
    #: Matches in total; larger than `len(items)` when the list was cut.
    total: int
    #: The tag a lookup asked for when no item carries it; the render then explains why.
    missing_tag: str | None = None

    @property
    def touched_keys(self) -> tuple[str, ...]:
        """Local keys of every drawing of every listed item, sorted."""
        return _keys_of(self.items)

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Header with the total, then one line per item."""
        shown = self.items[:max_items]
        lines = [item_line(item) for item in shown]
        header = f"{self.handle}: {self.total} items"
        if self.missing_tag is not None:
            lines.append(no_such_tag_text(self.missing_tag))
        return frame_text(header, lines, self.total - len(shown), max_chars)


class SubgraphMember(BaseModel):
    """One item a walk reached."""

    model_config = ConfigDict(frozen=True)

    item: ItemRecord
    #: Hops from the nearest start item.
    hops: int
    #: True when the stop filter matched; the walk did not go beyond it.
    is_stop: bool = False
    #: True when no edge leaves the item in the walk direction (the walk cannot go further).
    is_end: bool = False
    #: True when `max_hops` kept the walk from expanding the item although it could go further.
    is_hop_limit: bool = False


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
    #: Walk-boundary items (end, stop, hop limit) that the nearest-first cut left out of `members`.
    unlisted_boundary: tuple[SubgraphMember, ...] = ()
    #: How many such items there are before the cap on `unlisted_boundary`.
    total_unlisted_boundary: int = 0

    @property
    def touched_keys(self) -> tuple[str, ...]:
        """Local keys of the start, member and boundary items and every stub crossed, sorted."""
        drawn = _keys_of([*self.start, *(m.item for m in [*self.members, *self.unlisted_boundary])])
        stubs = (key for edge in self.edges for key in edge.via)
        return tuple(sorted({*drawn, *stubs}))

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Header, one line per item (with hops), then one line per edge."""
        members = self.members[:max_items]
        edges = self.edges[:max_items]
        names = {item.item_id: item for item in [*self.start, *(m.item for m in self.members)]}
        lines = [_member_line(member) for member in members]
        lines += [edge_line(edge, names) for edge in edges]
        boundary = self.unlisted_boundary[:max_items]
        lines += self._boundary_lines(boundary)
        header = f"{self.handle}: {self.total_items} items, {self.total_edges} edges"
        # boundary items shown are listed, so they are not "not shown"
        hidden = (self.total_items - len(members) - len(boundary)) + (self.total_edges - len(edges))
        return frame_text(header, lines, hidden, max_chars)

    def _boundary_lines(self, boundary: Sequence[SubgraphMember]) -> list[str]:
        """Heading plus one line per unlisted boundary item; empty when there are none."""
        if not boundary:
            return []
        heading = f"Not listed above — where the walk ended ({self.total_unlisted_boundary} items):"
        lines = [heading, *(_member_line(member) for member in boundary)]
        if self.total_unlisted_boundary > len(boundary):
            lines.append(
                f"({self.total_unlisted_boundary - len(boundary)} more ending items not shown)"
            )
        return lines


class PathResult(BaseModel):
    """The shortest path between two items, or the fact that there is none."""

    model_config = ConfigDict(frozen=True)

    handle: str
    #: The tags (or handles) the caller named, for the header.
    source: str
    target: str
    found: bool
    #: False when the search ignored edge direction (`directed=false`).
    directed: bool = True
    #: The relations the search followed; the no-path sentence names them.
    relations: RelationGroup = "flow"
    #: How many edges of the whole path are walked against their direction (undirected only).
    against_direction: int = 0
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
        """Local keys of the listed drawings and the stubs between them, sorted.

        An undirected path is shown as a summary only, so it shows (and touches) nothing.
        """
        if not self.directed:
            return ()
        stubs = (key for edge in self.edges for key in edge.via)
        return tuple(sorted({*_keys_of(self.items), *stubs}))

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Directed: header, items in order, edges. Undirected: a one-line summary, no route."""
        if not self.directed:
            return frame_text(self._undirected_summary(), [], 0, max_chars)
        if self.hops is None:
            return frame_text(self._no_path_header(), [], 0, max_chars)
        shown = self.items[:max_items]
        names = {item.item_id: item for item in shown}
        edges = [edge for edge in self.edges if edge.source in names and edge.target in names]
        lines = [item_line(item) for item in shown]
        lines += [edge_line(edge, names) for edge in edges]
        hidden = (self.hops + 1) - len(shown)
        return frame_text(self._found_header(self.hops), lines, hidden, max_chars)

    def _undirected_summary(self) -> str:
        """Linked or not, hops, edges against their direction, sheets; never the route itself."""
        head = f"{self.handle}: path {self.source} to {self.target} IGNORING EDGE DIRECTION"
        if self.hops is None:
            return f"{head}: not linked, even ignoring edge direction."
        return (
            f"{head}: linked, {self.hops} hops, {self.against_direction} edges walked against "
            f"their direction, sheets {','.join(self.sheets)}. This is not a flow path and the "
            "route is not listed; it does not answer a question about flow."
        )

    def _no_path_header(self) -> str:
        head = f"{self.handle}: no path from {self.source} to {self.target}"
        if self.relations == "flow":
            return (
                f"{head} along the edge direction (send_to: source to target). "
                f"Flow cannot reach {self.target} from {self.source}."
            )
        return (
            f"{head} along the edge direction (source to target). "
            f"{self.target} cannot be reached from {self.source} that way."
        )

    def _found_header(self, hops: int) -> str:
        head = f"{self.handle}: path {self.source} to {self.target}"
        return f"{head}, {hops} hops, sheets {','.join(self.sheets)}"


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
        return frame_text(header, lines, self.total_groups - len(shown), max_chars)


#: Anything a primitive can return.
PlantResult = ItemSet | Subgraph | PathResult | Table


# --- line formats -------------------------------------------------------------


def item_label(item: ItemRecord) -> str:
    """The tag, or the item's id for an untagged item (an actuator, a stub).

    The id is what the plant rendering (`context_render.PlantRenderer`) calls the item, and
    `PlantApi` accepts it wherever it accepts a tag, so an agent can still refer to the item.
    """
    return item.tag if item.tag is not None else item.item_id


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


def no_such_tag_text(tag: str) -> str:
    """What to tell a caller whose tag matched nothing, so it does not retry other spellings."""
    return (
        f"No item has tag {tag!r} in this plant. Tags are already matched ignoring case and "
        "spaces; patterns and wildcards are not supported, so another spelling will not match. "
        "Do not try other tags in its place: that the plant has no such item is itself an answer."
    )


def repeated_miss_text(tag: str) -> str:
    """The firmer notice for a second empty tag lookup in the same question."""
    return (
        f"Already searched: no item has tag {tag!r}; another spelling will not match. "
        "Finish with what you have."
    )


def _member_line(member: SubgraphMember) -> str:
    flags = (
        (STOP_MARK, member.is_stop),
        (END_MARK, member.is_end),
        (HOP_LIMIT_MARK, member.is_hop_limit),
    )
    marks = [mark for mark, applies in flags if applies]
    return " ".join([f"{item_line(member.item)} [hop {member.hops}]", *marks])


def _row_line(row: TableRow) -> str:
    more = ", ..." if row.count > len(row.tags) else ""
    return f"{row.group}: {row.count} ({', '.join(row.tags)}{more})"


def _keys_of(items: Iterable[ItemRecord]) -> tuple[str, ...]:
    return tuple(sorted({key for item in items for key in item.occurrence_keys}))


def render_was_cut(text: str, max_chars: int) -> bool:
    """True when a rendering dropped lines: its header says so, or it hit the character limit."""
    return len(text) >= max_chars or _NOT_SHOWN_WORDS in text.partition("\n")[0]


def frame_text(header: str, lines: Sequence[str], hidden: int, max_chars: int) -> str:
    """Header plus as many lines as fit in `max_chars`; `hidden` lines were already cut upstream."""
    kept = list(lines)
    while True:
        omitted = hidden + len(lines) - len(kept)
        top = f"{header} {_NOT_SHOWN.format(n=omitted)}" if omitted else header
        text = "\n".join([top, *kept])
        if len(text) <= max_chars or not kept:
            return text[:max_chars]
        kept.pop()
