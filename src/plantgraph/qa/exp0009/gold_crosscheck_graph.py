"""The flow graph of a B view, rebuilt from the view alone, for the scope X gold cross-check.

The B view is an *occurrence* graph: a pump drawn on two sheets is two nodes, and a pipe that leaves
one sheet ends in an **off-page connector** (a stub symbol saying "this line continues on sheet N")
whose partner stub starts the pipe on the next sheet. The stored gold walks the unsplit plant, where
none of that exists. To walk the same plant from the view, this module folds the view back:

- the occurrences of one item (`same_tagged_item_as` edges) become one node;
- a stub pair (`continues_as` edge) is removed and the pipe is joined across it.

Everything is read from `view.items()` and `view.edges()`: no generator plan, no occurrence map.
Independence note: this file shares no code with `descriptor.py`, `scope_x.py` or the stored walks.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from plantgraph.qa.graph_view import EdgeRecord, ItemRecord

SEND_TO = "send_to"
CONTINUES_AS = "continues_as"
SAME_ITEM = "same_tagged_item_as"
#: the property the B view adds to a positioned valve
OPERATING_POSITION = "operating_position"
_STUB_SUFFIX = "OffPageConnector"
_WHITESPACE = re.compile(r"\s+")
_LINE_NOISE = re.compile(r"[\s\"'″”]+")  # spaces and the inch mark, in four spellings
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def fold_tag(tag: str) -> str:
    """Case and runs of spaces folded: `p-101 ` and `P-101` are the same printed tag."""
    return _WHITESPACE.sub(" ", tag.strip()).upper()


def fold_line(line_number: str) -> str:
    """Spaces and inch marks dropped, upper case: `6"-p-1203-A1A` equals `6-P-1203-A1A`."""
    return _LINE_NOISE.sub("", line_number).upper()


def fold_class(class_name: str) -> str:
    """`GateValve`, `gate valve` and `Gate-Valve` give one key."""
    return _NON_ALNUM.sub("", class_name).casefold()


class OccurrenceSource(Protocol):
    """What the fold reads: a view's items and edges (any `GraphView` fits)."""

    def items(self) -> Sequence[ItemRecord]:
        """Every occurrence."""
        ...

    def edges(self) -> Sequence[EdgeRecord]:
        """Every relationship."""
        ...


@dataclass(frozen=True)
class FlowGraph:
    """One node per physical item, joined by `send_to` flow; stubs are gone."""

    successors: Mapping[str, frozenset[str]]
    predecessors: Mapping[str, frozenset[str]]
    #: node -> its folded printed tag; untagged nodes are absent
    tags: Mapping[str, str]
    classes: Mapping[str, str]
    #: node -> folded line numbers of its `send_to` edges (stub edges included)
    lines: Mapping[str, frozenset[str]]
    #: valve -> position code, where the view carries one
    positions: Mapping[str, str]
    #: node -> the view's occurrence keys folded into it
    occurrences: Mapping[str, tuple[str, ...]]

    def nodes_with_tag(self, folded_tag: str) -> frozenset[str]:
        """Every node whose folded tag is `folded_tag`."""
        return frozenset(node for node, tag in self.tags.items() if tag == folded_tag)


class _Merger:
    """Union-find over occurrence keys; the representative is the smallest key of a group."""

    def __init__(self, keys: list[str]) -> None:
        self._parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def union(self, first: str, second: str) -> None:
        root_a, root_b = self.find(first), self.find(second)
        if root_a != root_b:
            self._parent[max(root_a, root_b)] = min(root_a, root_b)


def build_flow_graph(view: OccurrenceSource) -> FlowGraph:
    """Fold the view's occurrence graph into one flow graph.

    Raises:
        ValueError: two stubs are joined by a `send_to` edge (a chain the bridge does not handle).
    """
    items = {item.local_key: item for item in view.items()}
    edges = list(view.edges())
    stubs = {key for key, item in items.items() if item.node_class.endswith(_STUB_SUFFIX)}
    merger = _Merger([key for key in items if key not in stubs])
    for edge in edges:
        if edge.relation == SAME_ITEM:
            merger.union(edge.source, edge.target)
    flow = _Flow(merger, stubs)
    for edge in edges:
        if edge.relation == SEND_TO:
            flow.add_send_to(edge)
    for edge in edges:
        if edge.relation == CONTINUES_AS:
            flow.bridge(edge.source, edge.target)
    return _assemble(items, stubs, merger, flow)


class _Flow:
    """The logical `send_to` edges, collected while the view's edges are read."""

    def __init__(self, merger: _Merger, stubs: set[str]) -> None:
        self._merger = merger
        self._stubs = stubs
        self.pairs: set[tuple[str, str]] = set()
        self.lines: defaultdict[str, set[str]] = defaultdict(set)
        self._into_stub: defaultdict[str, list[str]] = defaultdict(list)
        self._out_of_stub: defaultdict[str, list[str]] = defaultdict(list)

    def add_send_to(self, edge: EdgeRecord) -> None:
        """Record a `send_to` edge: a plain one directly, a stub one for `bridge` to join."""
        source_is_stub, target_is_stub = edge.source in self._stubs, edge.target in self._stubs
        if source_is_stub and target_is_stub:
            raise ValueError(f"expected no stub-to-stub send_to edge, found {edge.source!r}")
        line = edge.properties.get("line_number")
        for end in (edge.source, edge.target):
            if end not in self._stubs and line:
                self.lines[self._merger.find(end)].add(fold_line(str(line)))
        if target_is_stub:
            self._into_stub[edge.target].append(edge.source)
        elif source_is_stub:
            self._out_of_stub[edge.source].append(edge.target)
        else:
            self._add_pair(edge.source, edge.target)

    def bridge(self, stub_a: str, stub_b: str) -> None:
        """Join the pipe that enters one stub of a pair to the pipe that leaves the other."""
        for entering, leaving in ((stub_a, stub_b), (stub_b, stub_a)):
            for source in self._into_stub.get(entering, ()):
                for target in self._out_of_stub.get(leaving, ()):
                    self._add_pair(source, target)

    def _add_pair(self, source: str, target: str) -> None:
        first, second = self._merger.find(source), self._merger.find(target)
        if first != second:  # two occurrences of one item joined by a pipe is not a flow edge
            self.pairs.add((first, second))


def _assemble(
    items: Mapping[str, ItemRecord], stubs: set[str], merger: _Merger, flow: _Flow
) -> FlowGraph:
    successors: defaultdict[str, set[str]] = defaultdict(set)
    predecessors: defaultdict[str, set[str]] = defaultdict(set)
    for source, target in flow.pairs:
        successors[source].add(target)
        predecessors[target].add(source)
    members: defaultdict[str, list[str]] = defaultdict(list)
    for key in sorted(items):
        if key not in stubs:
            members[merger.find(key)].append(key)
    tags, classes, positions = {}, {}, {}
    for node, keys in members.items():
        classes[node] = items[keys[0]].node_class
        tag = next((t for k in keys if (t := items[k].tag)), None)
        if tag:
            tags[node] = fold_tag(tag)
        code = next((c for k in keys if (c := items[k].properties.get(OPERATING_POSITION))), None)
        if code:
            positions[node] = str(code)
    return FlowGraph(
        successors={n: frozenset(s) for n, s in successors.items()},
        predecessors={n: frozenset(p) for n, p in predecessors.items()},
        tags=tags,
        classes=classes,
        lines={n: frozenset(lines) for n, lines in flow.lines.items()},
        positions=positions,
        occurrences={n: tuple(keys) for n, keys in members.items()},
    )
