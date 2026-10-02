"""`PlantApi`: the six primitives over an `ItemGraph`, with result handles (design §3.3).

One `PlantApi` is one question's session. Each call stores its item set under
a new handle (`$r1`, `$r2`, ...), and a later call can pass that handle where
it would otherwise name a tag, which is how the primitives compose.
"""

from __future__ import annotations

from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import (
    Direction,
    GroupBy,
    ItemEdge,
    ItemFilter,
    ItemRecord,
    PlantApiError,
    RelationGroup,
    sheet_of_key,
)
from plantgraph.qa.plant_api.results import (
    DEFAULT_MAX_ITEMS,
    ItemSet,
    PathResult,
    Subgraph,
    SubgraphMember,
    Table,
    TableRow,
    item_label,
)
from plantgraph.qa.plant_api.traversal import Closure, closure, shortest_path

_HANDLE_PREFIX = "$r"
_TAGS_PER_ROW = 5
_NO_UNIT = "(no unit)"


class PlantApi:
    """The plant graph's six operations; every result is bounded and deterministic.

    Args:
        graph: the merged item graph.
        max_items: most items (and edges) a result keeps; the full count is still reported.
    """

    def __init__(self, graph: ItemGraph, max_items: int = DEFAULT_MAX_ITEMS) -> None:
        if max_items < 1:
            raise ValueError(f"expected max_items >= 1, found {max_items}")
        self._graph = graph
        self._max_items = max_items
        self._sets: dict[str, tuple[str, ...]] = {}

    def find(self, where: ItemFilter, limit: int = DEFAULT_MAX_ITEMS) -> ItemSet:
        """Items matching `where`, sorted by tag; the first `limit` are listed, all are counted."""
        if limit < 1:
            raise PlantApiError(f"expected limit >= 1, found {limit}")
        ids = self._graph.select(where)
        return self._item_set(ids, limit)

    def neighbours(
        self,
        of: str,
        direction: Direction,
        relations: RelationGroup,
        where: ItemFilter | None = None,
    ) -> Subgraph:
        """One hop from a tag or handle, optionally keeping only neighbours matching `where`."""
        starts = self._resolve(of)
        walk_ids = None if where is None else set(self._graph.select(where))
        reached = closure(self._graph, starts, direction, relations, None, walk_ids, max_hops=1)
        return self._subgraph(starts, reached)

    def traverse(
        self,
        start: str,
        direction: Direction,
        relations: RelationGroup,
        stop_at: ItemFilter | None = None,
        walk_only: ItemFilter | None = None,
        max_hops: int | None = None,
    ) -> Subgraph:
        """Everything reachable from `start`, excluding the start items.

        A `stop_at` item is included and not expanded. An item outside
        `walk_only` is never entered (so it cannot be a stop either).
        """
        if max_hops is not None and max_hops < 1:
            raise PlantApiError(f"expected max_hops >= 1 or None, found {max_hops}")
        starts = self._resolve(start)
        stop_ids = None if stop_at is None else set(self._graph.select(stop_at))
        walk_ids = None if walk_only is None else set(self._graph.select(walk_only))
        reached = closure(self._graph, starts, direction, relations, stop_ids, walk_ids, max_hops)
        return self._subgraph(starts, reached)

    def path(
        self,
        source: str,
        target: str,
        relations: RelationGroup = "flow",
        directed: bool = True,
    ) -> PathResult:
        """Shortest path (fewest hops; ties by tag sequence); `found` is false when none exists."""
        sources, targets = self._resolve(source), self._resolve(target)
        found = shortest_path(self._graph, sources, set(targets), relations, directed)
        if found is None:
            handle = self._store(())
            return PathResult(
                handle=handle,
                source=source,
                target=target,
                found=False,
                hops=None,
                items=(),
                edges=(),
                sheets=(),
            )
        return self._path_result(source, target, *found)

    def filter(self, items: str, where: ItemFilter) -> ItemSet:
        """The members of a handle (or tag) that match `where`."""
        members = self._resolve(items)
        return self._item_set(self._graph.select(where, among=members), DEFAULT_MAX_ITEMS)

    def aggregate(self, items: str, group_by: GroupBy) -> Table:
        """Count a handle's items per class, unit or sheet; an item on two sheets counts in both."""
        members = sorted(self._resolve(items), key=self._graph.sort_key)
        groups: dict[str, list[ItemRecord]] = {}
        for item_id in members:
            item = self._graph.item(item_id)
            for group in _groups_of(item, group_by):
                groups.setdefault(group, []).append(item)
        rows = [_table_row(group, records) for group, records in groups.items()]
        rows.sort(key=lambda row: (-row.count, row.group))
        handle = self._store(members)
        return Table(
            handle=handle,
            group_by=group_by,
            rows=tuple(rows[: self._max_items]),
            total_items=len(members),
            total_groups=len(rows),
        )

    # --- handles ---------------------------------------------------------------

    def _store(self, item_ids: tuple[str, ...] | list[str]) -> str:
        handle = f"{_HANDLE_PREFIX}{len(self._sets) + 1}"
        self._sets[handle] = tuple(item_ids)
        return handle

    def _resolve(self, ref: str) -> tuple[str, ...]:
        """A handle's items, or every item carrying the tag; never empty."""
        if ref.startswith(_HANDLE_PREFIX):
            return self._stored(ref)
        ids = self._graph.ids_for_tag(ref)
        if not ids:
            raise PlantApiError(f"expected a tag in the plant or a handle, found {ref!r}")
        return tuple(ids)

    def _stored(self, handle: str) -> tuple[str, ...]:
        if handle not in self._sets:
            raise PlantApiError(f"expected one of the handles {list(self._sets)}, found {handle!r}")
        ids = self._sets[handle]
        if not ids:
            raise PlantApiError(
                f"handle {handle} holds no items; there is nothing to continue from"
            )
        return ids

    # --- result builders -------------------------------------------------------

    def _item_set(self, ids: list[str], limit: int) -> ItemSet:
        shown = ids[: min(limit, self._max_items)]
        handle = self._store(ids)
        records = tuple(self._graph.item(item_id) for item_id in shown)
        return ItemSet(handle=handle, items=records, total=len(ids))

    def _subgraph(self, starts: tuple[str, ...], reached: Closure) -> Subgraph:
        ordered = sorted(reached.hops, key=lambda i: (reached.hops[i], *self._graph.sort_key(i)))
        shown = ordered[: self._max_items]
        members = tuple(
            SubgraphMember(
                item=self._graph.item(item_id),
                hops=reached.hops[item_id],
                is_stop=item_id in reached.stops,
            )
            for item_id in shown
        )
        visible = {*starts, *shown}
        edges = [e for e in reached.edges if e.source in visible and e.target in visible]
        start_records = tuple(self._graph.item(item_id) for item_id in starts[: self._max_items])
        # A handle holds the whole reached set, not just the listed part.
        handle = self._store(ordered)
        return Subgraph(
            handle=handle,
            start=start_records,
            members=members,
            edges=tuple(edges[: self._max_items]),
            total_items=len(ordered),
            total_edges=len(reached.edges),
        )

    def _path_result(
        self, source: str, target: str, item_ids: list[str], edges: list[ItemEdge]
    ) -> PathResult:
        handle = self._store(item_ids)
        shown = item_ids[: self._max_items]
        records = tuple(self._graph.item(item_id) for item_id in shown)
        return PathResult(
            handle=handle,
            source=source,
            target=target,
            found=True,
            hops=len(edges),
            items=records,
            edges=tuple(edges[: len(shown) - 1]),
            sheets=self._sheets_in_order(item_ids, edges),
        )

    def _sheets_in_order(self, item_ids: list[str], edges: list[ItemEdge]) -> tuple[str, ...]:
        """Sheets of each item then of the stubs after it, in path order, first visit only."""
        visited: list[str] = []
        for position, item_id in enumerate(item_ids):
            visited.extend(self._graph.item(item_id).sheets)
            if position < len(edges) and edges[position].via:
                via = edges[position].via
                visited.extend((sheet_of_key(via[0]), sheet_of_key(via[-1])))
        return tuple(dict.fromkeys(visited))


def _groups_of(item: ItemRecord, group_by: GroupBy) -> tuple[str, ...]:
    if group_by == "node_class":
        return (item.node_class,)
    if group_by == "unit":
        return (item.unit_id or _NO_UNIT,)
    return item.sheets


def _table_row(group: str, records: list[ItemRecord]) -> TableRow:
    examples = records[:_TAGS_PER_ROW]
    return TableRow(
        group=group,
        count=len(records),
        tags=tuple(item_label(item) for item in examples),
        keys=tuple(sorted({key for item in examples for key in item.occurrence_keys})),
    )
