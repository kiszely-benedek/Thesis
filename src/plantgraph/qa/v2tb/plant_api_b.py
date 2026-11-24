"""The plant API of the B agent: the frozen tools, with two facts added to what they print.

The frozen tools print an item as `TAG (Class, kind, unit, sheets)` and an edge as `A -send_to-> B`:
no item property and no line number ever reaches the model. A B agent needs both to answer:

- a valve's `operating_position` (which valves are closed in normal operation), and
- the `line_number` of an edge (an untagged valve is named by its line number, design `v2t-b` §5).

So the result types below print one more bracket: `[operating_position NC]` after a valve's line,
`[line 6"-P-1203-A1A]` after an edge. Nothing else changes: `PlantApiB` computes exactly what the
frozen `PlantApi` computes and only wraps its results in these subclasses. Each `render` is a copy
of the frozen method with the two line formatters swapped; its docstring names the original.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord, RelationGroup
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import (
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_ITEMS,
    END_MARK,
    HOP_LIMIT_MARK,
    STOP_MARK,
    ItemSet,
    PathResult,
    Subgraph,
    SubgraphMember,
    edge_line,
    frame_text,
    item_line,
    no_such_tag_text,
)
from plantgraph.qa.plant_api.traversal import Closure
from plantgraph.qa.v2tb.visible import OPERATING_POSITION

LINE_NUMBER = "line_number"


def item_line_b(item: ItemRecord) -> str:
    """`item_line`, plus `[operating_position NC]` when the item has a position."""
    position = item.properties.get(OPERATING_POSITION)
    if not isinstance(position, str):
        return item_line(item)
    return f"{item_line(item)} [{OPERATING_POSITION} {position}]"


def edge_line_b(edge: ItemEdge, names: Mapping[str, ItemRecord]) -> str:
    """`edge_line`, plus `[line 6"-P-1203-A1A]` when the drawn edge has a line number."""
    line_number = edge.properties.get(LINE_NUMBER)
    if not isinstance(line_number, str):
        return edge_line(edge, names)
    return f"{edge_line(edge, names)} [line {line_number}]"


def _member_line_b(member: SubgraphMember) -> str:
    """Copy of the frozen `results._member_line`, over `item_line_b`."""
    flags = (
        (STOP_MARK, member.is_stop),
        (END_MARK, member.is_end),
        (HOP_LIMIT_MARK, member.is_hop_limit),
    )
    marks = [mark for mark, applies in flags if applies]
    return " ".join([f"{item_line_b(member.item)} [hop {member.hops}]", *marks])


class ItemSetB(ItemSet):
    """`ItemSet` whose item lines show the position."""

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Copy of `ItemSet.render` over `item_line_b`."""
        shown = self.items[:max_items]
        lines = [item_line_b(item) for item in shown]
        header = f"{self.handle}: {self.total} items"
        if self.missing_tag is not None:
            lines.append(no_such_tag_text(self.missing_tag))
        return frame_text(header, lines, self.total - len(shown), max_chars)


class SubgraphB(Subgraph):
    """`Subgraph` whose item and edge lines show the position and the line number."""

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """Copy of `Subgraph.render` over `_member_line_b` and `edge_line_b`."""
        members = self.members[:max_items]
        edges = self.edges[:max_items]
        names = {item.item_id: item for item in [*self.start, *(m.item for m in self.members)]}
        lines = [_member_line_b(member) for member in members]
        lines += [edge_line_b(edge, names) for edge in edges]
        boundary = self.unlisted_boundary[:max_items]
        lines += self._boundary_lines(boundary)
        header = f"{self.handle}: {self.total_items} items, {self.total_edges} edges"
        hidden = (self.total_items - len(members) - len(boundary)) + (self.total_edges - len(edges))
        return frame_text(header, lines, hidden, max_chars)

    def _boundary_lines(self, boundary: Sequence[SubgraphMember]) -> list[str]:
        """Copy of `Subgraph._boundary_lines` over `_member_line_b`."""
        if not boundary:
            return []
        heading = f"Not listed above — where the walk ended ({self.total_unlisted_boundary} items):"
        lines = [heading, *(_member_line_b(member) for member in boundary)]
        if self.total_unlisted_boundary > len(boundary):
            lines.append(
                f"({self.total_unlisted_boundary - len(boundary)} more ending items not shown)"
            )
        return lines


class PathResultB(PathResult):
    """`PathResult` whose item and edge lines show the position and the line number."""

    def render(self, max_chars: int = DEFAULT_MAX_CHARS, max_items: int = DEFAULT_MAX_ITEMS) -> str:
        """`PathResult.render`, with `item_line_b` and `edge_line_b` for a directed path."""
        if not self.directed or self.hops is None:
            return super().render(max_chars, max_items)  # a summary: no item or edge line in it
        shown = self.items[:max_items]
        names = {item.item_id: item for item in shown}
        edges = [edge for edge in self.edges if edge.source in names and edge.target in names]
        lines = [item_line_b(item) for item in shown]
        lines += [edge_line_b(edge, names) for edge in edges]
        hidden = (self.hops + 1) - len(shown)
        return frame_text(self._found_header(self.hops), lines, hidden, max_chars)


class PlantApiB(PlantApi):
    """The frozen `PlantApi`, returning the B result types (same items, same order, same counts)."""

    def _item_set(self, ids: list[str], limit: int, missing_tag: str | None = None) -> ItemSetB:
        return ItemSetB(**dict(super()._item_set(ids, limit, missing_tag)))

    def _subgraph(
        self, starts: tuple[str, ...], reached: Closure, mark_boundaries: bool
    ) -> SubgraphB:
        return SubgraphB(**dict(super()._subgraph(starts, reached, mark_boundaries)))

    def _path_result(
        self,
        source: str,
        target: str,
        directed: bool,
        relations: RelationGroup,
        item_ids: list[str],
        edges: list[ItemEdge],
    ) -> PathResultB:
        found = super()._path_result(source, target, directed, relations, item_ids, edges)
        return PathResultB(**dict(found))
