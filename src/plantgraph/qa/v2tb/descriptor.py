"""Naming a valve that prints no tag: the descriptor, and how it is resolved to a plant node.

Some drawing sets print no tag on their manual valves (Toghraei p.113). An engineer still names
such a valve: "the gate valve on line 6-P-1203-A1A just upstream of FV-1203". That sentence is a
**descriptor**: the valve's class, its line number, the tagged item it sits next to, and on which
side of that item (along the flow) it sits.

Resolution reads the gold plant (a `networkx` graph whose `send_to` edges carry the line number).
A descriptor means: every untagged node of that class on that line whose **nearest tagged
neighbour** on that side is `next_to`. The walk follows `send_to` edges of the same line only and
passes through untagged nodes; it stops at the first tagged node on each branch.

Answer items travel through the frozen `FinalAnswer`, which holds only strings, so a descriptor is
written as a JSON string with sorted keys (`encode_descriptor`); a tag stays a plain string.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from enum import Enum

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from plantgraph.graph.schema import Relation
from plantgraph.qa.scoring import normalize_scalar

_SEND_TO = Relation.SEND_TO.value
_NON_WORD = re.compile(r"[^A-Za-z0-9]+")
#: Inch marks and spaces are how a model re-types `6"-P-1203`; the plant stores neither.
_LINE_NUMBER_NOISE = re.compile(r"[\s\"'″”]+")


class Side(str, Enum):
    """Where the valve sits relative to `next_to`, along the flow."""

    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


class Descriptor(BaseModel):
    """A valve named by its class, line number and the tagged item beside it."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    class_name: str = Field(alias="class")
    line_number: str
    next_to: str
    side: Side


def fold_class(name: str) -> str:
    """`GateValve`, `gate valve` and `Gate-Valve` fold to the same key."""
    return _NON_WORD.sub("", name).casefold()


def fold_line_number(line_number: str) -> str:
    """Case, spaces and inch marks removed, so `6"-p-1203-A1A` equals `6-P-1203-A1A`."""
    return _LINE_NUMBER_NOISE.sub("", line_number).upper()


def encode_descriptor(descriptor: Descriptor) -> str:
    """The descriptor as the one string that stands for it in a `FinalAnswer`."""
    fields = descriptor.model_dump(by_alias=True, mode="json")
    return json.dumps(fields, sort_keys=True)


def decode_item(item: str) -> str | Descriptor:
    """A tag stays a string; a string holding a JSON descriptor becomes a `Descriptor`.

    Raises:
        ValueError: the string looks like a descriptor (starts with `{`) but is not one.
    """
    if not item.lstrip().startswith("{"):
        return item
    try:
        return Descriptor.model_validate_json(item)
    except ValidationError as error:
        raise ValueError(
            f"expected a descriptor with class, line_number, next_to and side: {error}"
        ) from error


def descriptor_from_object(obj: dict[str, object]) -> Descriptor:
    """A descriptor from the dict a model wrote; an extra key is ignored, a missing one is refused.

    Raises:
        ValueError: a key is missing or of the wrong kind.
    """
    try:
        return Descriptor.model_validate(obj)
    except ValidationError as error:
        raise ValueError(
            f"expected a descriptor with class, line_number, next_to and side: {error}"
        ) from error


class PlantIndex:
    """The lookups descriptor resolution needs, built once from the gold plant."""

    def __init__(self, plant: nx.DiGraph[str]) -> None:
        self._plant = plant
        self._by_tag: dict[str, set[str]] = defaultdict(set)
        self._untagged: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._lines: dict[str, set[str]] = defaultdict(set)
        self._line_as_written: dict[str, str] = {}
        self._index_edges()
        self._index_nodes()
        self._walks: dict[tuple[str, str, bool], frozenset[str]] = {}

    def _index_edges(self) -> None:
        for source, target, data in self._plant.edges(data=True):
            line = data.get("line_number")
            if data.get("relation") == _SEND_TO and line:
                key = fold_line_number(str(line))
                self._line_as_written.setdefault(key, str(line))
                self._lines[source].add(key)
                self._lines[target].add(key)

    def _index_nodes(self) -> None:
        for node_id, data in self._plant.nodes(data=True):
            if data.get("tag"):
                self._by_tag[normalize_scalar(str(data["tag"]))].add(node_id)
                continue
            for line in self._lines.get(node_id, ()):
                self._untagged[(fold_class(data["node_class"]), line)].append(node_id)

    def nodes_with_tag(self, tag: str) -> frozenset[str]:
        """Every plant node that prints this tag (case and spacing folded)."""
        return frozenset(self._by_tag.get(normalize_scalar(tag), ()))

    def line_numbers(self, node_id: str) -> list[str]:
        """The folded line numbers of the node's `send_to` edges, sorted."""
        return sorted(self._lines.get(node_id, ()))

    def line_as_written(self, line_key: str) -> str:
        """The line number as the plant prints it (a descriptor quotes this, not the folded key)."""
        return self._line_as_written[line_key]

    def untagged_of(self, class_key: str, line_key: str) -> list[str]:
        """Untagged nodes of a folded class on a folded line."""
        return self._untagged.get((class_key, line_key), [])

    def tag_of(self, node_id: str) -> str | None:
        """The tag a node prints, or `None` for an untagged node."""
        tag = self._plant.nodes[node_id].get("tag")
        return str(tag) if tag else None

    def node_class_of(self, node_id: str) -> str:
        """The node's `node_class`."""
        return str(self._plant.nodes[node_id]["node_class"])

    def nearest_tagged(self, node_id: str, line_key: str, *, forward: bool) -> frozenset[str]:
        """Tagged nodes first reached from `node_id` along `send_to` edges of one line.

        Args:
            node_id: where the walk starts.
            line_key: the folded line number whose edges are followed.
            forward: True walks downstream (with the flow), False walks upstream.
        """
        key = (node_id, line_key, forward)
        if key not in self._walks:
            self._walks[key] = self._walk(node_id, line_key, forward)
        return self._walks[key]

    def _walk(self, start: str, line_key: str, forward: bool) -> frozenset[str]:
        found: set[str] = set()
        seen = {start}
        frontier = [start]
        while frontier:
            frontier = self._step(frontier, line_key, forward, seen, found)
        return frozenset(found)

    def _step(
        self, frontier: list[str], line_key: str, forward: bool, seen: set[str], found: set[str]
    ) -> list[str]:
        """One breadth-first layer: tagged neighbours end a branch, untagged ones are walked on."""
        onward: list[str] = []
        for node_id in frontier:
            for neighbour in self._same_line_neighbours(node_id, line_key, forward):
                if self.tag_of(neighbour) is not None:
                    found.add(neighbour)
                elif neighbour not in seen:
                    seen.add(neighbour)
                    onward.append(neighbour)
        return onward

    def _same_line_neighbours(self, node_id: str, line_key: str, forward: bool) -> Iterable[str]:
        edges = (
            self._plant.out_edges(node_id, data=True)
            if forward
            else self._plant.in_edges(node_id, data=True)
        )
        for source, target, data in edges:
            line = data.get("line_number")
            if (
                data.get("relation") == _SEND_TO
                and line
                and fold_line_number(str(line)) == line_key
            ):
                yield target if forward else source


def resolve_descriptor(index: PlantIndex, descriptor: Descriptor) -> frozenset[str]:
    """Every untagged node the descriptor picks out; empty when it matches none."""
    line_key = fold_line_number(descriptor.line_number)
    beside = index.nodes_with_tag(descriptor.next_to)
    # a valve upstream of `next_to` reaches it by walking downstream, and the other way round
    forward = descriptor.side is Side.UPSTREAM
    candidates = index.untagged_of(fold_class(descriptor.class_name), line_key)
    return frozenset(
        node_id
        for node_id in candidates
        if beside & index.nearest_tagged(node_id, line_key, forward=forward)
    )


def canonical_descriptor(index: PlantIndex, node_id: str) -> Descriptor | None:
    """The first descriptor that picks out exactly `node_id`, or `None` when none does.

    Order: each of the node's lines, sorted; downstream neighbour first, else upstream; among
    several tagged neighbours the tag that sorts first. `None` means the node cannot be named.
    """
    class_name = index.node_class_of(node_id)
    for line in index.line_numbers(node_id):
        for forward, side in ((True, Side.UPSTREAM), (False, Side.DOWNSTREAM)):
            for neighbour in _tags_beside(index, node_id, line, forward):
                found = _unique_descriptor(index, node_id, class_name, line, neighbour, side)
                if found is not None:
                    return found
    return None


def _tags_beside(index: PlantIndex, node_id: str, line: str, forward: bool) -> list[str]:
    reached = index.nearest_tagged(node_id, line, forward=forward)
    return sorted(tag for n in reached if (tag := index.tag_of(n)) is not None)


def _unique_descriptor(
    index: PlantIndex, node_id: str, class_name: str, line: str, next_to: str, side: Side
) -> Descriptor | None:
    written = index.line_as_written(line)
    descriptor = Descriptor(class_name=class_name, line_number=written, next_to=next_to, side=side)
    return descriptor if resolve_descriptor(index, descriptor) == {node_id} else None
