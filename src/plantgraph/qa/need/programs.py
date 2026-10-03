"""One fixed program of plant-API primitives per need label (design §4.1 table).

A *program* is a short, fixed sequence of primitive calls (`plant_api/`) whose slots are the
anchors the question names: `traverse(a1, upstream, flow, stop_at=OperatedValve)` is the
program of `UPSTREAM_TO_FIRST_VALVE`. Running it yields the **items the answer needs**, each
with its hop distance from the anchors, and the edges walked (an edge that crosses a sheet
carries the off-page connector stubs it passes). `context.py` turns that into text.

These programs are the strategy's own. The harness holds separate, hand-written *canonical
programs* that compute gold answers; this module must never import them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from plantgraph.qa.anchors import Anchors
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.plant_api.model import (
    Direction,
    ItemEdge,
    ItemFilter,
    ItemRecord,
    PlantApiError,
)
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import PathResult, Subgraph

#: The canonical isolation boundary on a P&ID: a valve someone operates (not a check valve).
_OPERATED_VALVE = ItemFilter(label="OperatedValve")
#: Signal chains (sensor, controller, actuator) are short; three hops reach the whole loop.
_SIGNAL_HOPS = 3


class NeedPreconditionError(ValueError):
    """The question lacks what its need label's program needs (anchors, a stop label, ...).

    The strategy answers it with the generic Hierarchical instead.
    """


@dataclass(frozen=True)
class SelectedItem:
    """An item the program reached, and how many hops it is from the nearest anchor."""

    item: ItemRecord
    distance: int


@dataclass(frozen=True)
class NeedSelection:
    """What a program selected; empty `items` means it found nothing beyond the anchors."""

    #: The primitive calls made, as text, for the trace.
    program: tuple[str, ...]
    #: Nearest first, ties by tag.
    items: tuple[SelectedItem, ...]
    edges: tuple[ItemEdge, ...]


class _Collector:
    """Gathers the results of a program's calls: each item once (at its nearest), each edge once."""

    def __init__(self) -> None:
        self._records: dict[str, ItemRecord] = {}
        self._distance: dict[str, int] = {}
        self._edges: dict[tuple[str, str, str], ItemEdge] = {}
        self._calls: list[str] = []

    def add_subgraph(self, call: str, result: Subgraph) -> None:
        self._calls.append(call)
        for item in result.start:
            self._add_item(item, 0)
        for member in result.members:
            self._add_item(member.item, member.hops)
        self._add_edges(result.edges)

    def add_path(self, call: str, result: PathResult) -> None:
        self._calls.append(call)
        last = len(result.items) - 1
        for position, item in enumerate(result.items):
            # the middle of a path is the farthest from both ends, so it is cut first
            self._add_item(item, min(position, last - position))
        self._add_edges(result.edges)

    def selection(self) -> NeedSelection:
        ordered = sorted(
            self._records, key=lambda i: (self._distance[i], self._records[i].tag or "", i)
        )
        items = tuple(SelectedItem(self._records[i], self._distance[i]) for i in ordered)
        return NeedSelection(tuple(self._calls), items, tuple(self._edges.values()))

    def _add_item(self, item: ItemRecord, distance: int) -> None:
        self._records[item.item_id] = item
        self._distance[item.item_id] = min(distance, self._distance.get(item.item_id, distance))

    def _add_edges(self, edges: tuple[ItemEdge, ...]) -> None:
        for edge in edges:
            self._edges[(edge.source, edge.target, edge.relation)] = edge


Program = Callable[[Anchors, PlantApi], NeedSelection]


def run_program(label: NeedLabel, anchors: Anchors, api: PlantApi) -> NeedSelection:
    """Run the program of `label` over the anchors.

    Raises:
        NeedPreconditionError: the anchors do not fit the program, or the plant lacks a class
            the program names.
        ValueError: `label` has no program (`GENERIC` never reaches here).
    """
    program = _PROGRAMS.get(label)
    if program is None:
        raise ValueError(f"expected a need label with a program, found {label.value}")
    try:
        return program(anchors, api)
    except PlantApiError as error:  # e.g. the plant has no OperatedValve to stop at
        raise NeedPreconditionError(str(error)) from error


# --- the programs ------------------------------------------------------------------------------


def _anchors_only(anchors: Anchors, api: PlantApi) -> NeedSelection:
    return NeedSelection(program=(), items=(), edges=())


def _neighbours(direction: Direction, anchors: Anchors, api: PlantApi) -> NeedSelection:
    """One flow hop from every named tag."""
    collector = _Collector()
    for tag in _tag_texts(anchors, minimum=1):
        result = api.neighbours(tag, direction, "flow")
        collector.add_subgraph(f'neighbours("{tag}", {direction}, flow)', result)
    return collector.selection()


def _signal_chain(anchors: Anchors, api: PlantApi) -> NeedSelection:
    collector = _Collector()
    for tag in _tag_texts(anchors, minimum=1):
        result = api.traverse(tag, "both", "signal", max_hops=_SIGNAL_HOPS)
        collector.add_subgraph(f'traverse("{tag}", both, signal, max_hops={_SIGNAL_HOPS})', result)
    return collector.selection()


def _path(anchors: Anchors, api: PlantApi) -> NeedSelection:
    """From the first tag to each other one; if flow goes only the other way, that way."""
    first, *others = _tag_texts(anchors, minimum=2)
    collector = _Collector()
    for other in others:
        forward = api.path(first, other)
        collector.add_path(f'path("{first}", "{other}")', forward)
        if not forward.found:
            collector.add_path(f'path("{other}", "{first}")', api.path(other, first))
    return collector.selection()


def _to_first_valve(direction: Direction, anchors: Anchors, api: PlantApi) -> NeedSelection:
    """Every branch from the first tag back (or on) to the first operated valve on it."""
    tag = _tag_texts(anchors, minimum=1)[0]
    result = api.traverse(tag, direction, "flow", stop_at=_OPERATED_VALVE)
    collector = _Collector()
    collector.add_subgraph(
        f'traverse("{tag}", {direction}, flow, stop_at={{label: OperatedValve}})', result
    )
    return collector.selection()


def _all_the_way(direction: Direction, anchors: Anchors, api: PlantApi) -> NeedSelection:
    """Everything the first tag's flow reaches in `direction`, inside the unit if one is named."""
    tag = _tag_texts(anchors, minimum=1)[0]
    unit = anchors.units[0].unit_id if anchors.units else None
    walk_only = ItemFilter(unit=unit) if unit is not None else None
    result = api.traverse(tag, direction, "flow", walk_only=walk_only)
    restriction = f", walk_only={{unit: {unit}}}" if unit is not None else ""
    collector = _Collector()
    collector.add_subgraph(f'traverse("{tag}", {direction}, flow{restriction})', result)
    return collector.selection()


def _unit_scope(anchors: Anchors, api: PlantApi) -> NeedSelection:
    """Each named unit's items and the lines crossing its boundary (their flow neighbours)."""
    if not anchors.units:
        raise NeedPreconditionError("expected at least 1 unit anchor, found 0")
    collector = _Collector()
    for unit in anchors.units:
        members = api.find(ItemFilter(unit=unit.unit_id), limit=1)
        if members.total == 0:
            raise NeedPreconditionError(f"expected items in unit {unit.unit_id}, found none")
        boundary = api.neighbours(members.handle, "both", "flow")
        collector.add_subgraph(f"neighbours(find(unit={unit.unit_id}), both, flow)", boundary)
    return collector.selection()


def _tag_texts(anchors: Anchors, *, minimum: int) -> list[str]:
    """The tags as written in the question, in text order; fewer than `minimum` is an error."""
    if len(anchors.tags) < minimum:
        raise NeedPreconditionError(
            f"expected at least {minimum} tag anchor(s), found {len(anchors.tags)}"
        )
    return [tag.text for tag in anchors.tags]


_PROGRAMS: dict[NeedLabel, Program] = {
    NeedLabel.ITEM: _anchors_only,
    NeedLabel.NEIGHBOURS_DOWNSTREAM: partial(_neighbours, "downstream"),
    NeedLabel.NEIGHBOURS_UPSTREAM: partial(_neighbours, "upstream"),
    NeedLabel.SIGNAL_CHAIN: _signal_chain,
    NeedLabel.PATH: _path,
    NeedLabel.UPSTREAM_TO_FIRST_VALVE: partial(_to_first_valve, "upstream"),
    NeedLabel.DOWNSTREAM_TO_FIRST_VALVE: partial(_to_first_valve, "downstream"),
    NeedLabel.UPSTREAM_ALL: partial(_all_the_way, "upstream"),
    NeedLabel.DOWNSTREAM_ALL: partial(_all_the_way, "downstream"),
    NeedLabel.UNIT_SCOPE: _unit_scope,
}
