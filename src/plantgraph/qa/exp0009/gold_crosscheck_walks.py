"""The isolation walk and the valve naming of the scope X cross-check, written from the definitions.

Definitions used (design `v2t-b-system-revision.md` §4, §5, §10 R1):

- **Isolation.** To cut an item off from everything upstream (downstream), go against (with)
  the flow.
  On every route the valve to close is the first *operated* valve met; a check or safety valve is
  passed through. If some route ends at a source (a sink) before meeting an operated valve, there is
  nothing to close on that route and the item is not a candidate.
- **Descriptor.** An untagged valve is named by its class, one of its own line numbers, a tagged
  item `next_to`, and a `side`. `side = upstream` says the valve sits upstream of `next_to`, so
  `next_to` is found by walking downstream from the valve. The walk follows every `send_to` edge,
  passes through untagged nodes and stops at the first tagged node on each branch (R1).
  A descriptor resolves to every untagged node of that class and line whose reached set holds
  `next_to`. A valve is *nameable* when some descriptor resolves to exactly that valve.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass

from plantgraph.qa.exp0009.gold_crosscheck_graph import (
    FlowGraph,
    fold_class,
    fold_line,
    fold_tag,
)

#: Valves an operator opens or closes by hand or actuator (not check or safety valves).
OPERATED_CLASSES = frozenset(
    {
        "AngleBallValve",
        "AngleGlobeValve",
        "AnglePlugValve",
        "AngleValve",
        "BallValve",
        "ButterflyValve",
        "GateValve",
        "GlobeValve",
        "NeedleValve",
        "OperatedValve",
        "PlugValve",
        "StraightwayValve",
    }  # fmt: skip
)
#: Process equipment: the items an isolation question is asked about.
EQUIPMENT_CLASSES = frozenset(
    {
        "Agitator",
        "AirCoolingSystem",
        "AirEjector",
        "CentrifugalCompressor",
        "CentrifugalPump",
        "Compressor",
        "EjectorPump",
        "ElectricHeater",
        "ElectricalSeparator",
        "Filter",
        "Furnace",
        "GasFilter",
        "GravitationalSeparator",
        "HeatExchanger",
        "Heater",
        "LiquidFilter",
        "Mixer",
        "PlateHeatExchanger",
        "PressureVessel",
        "ProcessColumn",
        "Pump",
        "ReciprocatingCompressor",
        "ReciprocatingPump",
        "RotaryCompressor",
        "RotaryMixer",
        "RotaryPump",
        "ScrubbingSeparator",
        "Separator",
        "SpiralHeatExchanger",
        "StaticMixer",
        "Tank",
        "TubularHeatExchanger",
        "Vessel",
    }  # fmt: skip
)
#: A valve in one of these positions is already closed in ordinary operation (design §4).
CLOSED_POSITIONS = frozenset({"NC", "LC", "CSC"})


def is_operated(graph: FlowGraph, node: str) -> bool:
    """Whether the node is an operated valve."""
    return graph.classes[node] in OPERATED_CLASSES


def isolation_valves(graph: FlowGraph, start: str, *, upstream: bool) -> frozenset[str] | None:
    """The first operated valve on every route from `start`; `None` if some route has none.

    Mechanics: collect every non-valve node reachable without crossing an operated valve (the
    "walked region"). The answer is the operated valves touching that region. A node of the region
    with nothing further on is a route that ends before any valve, so the item is no candidate.
    """
    onward = graph.predecessors if upstream else graph.successors
    region, pending = {start}, [start]
    valves: set[str] = set()
    while pending:
        node = pending.pop()
        neighbours = onward.get(node, frozenset())
        if not neighbours:
            return None
        for neighbour in neighbours:
            if is_operated(graph, neighbour):
                valves.add(neighbour)
            elif neighbour not in region:
                region.add(neighbour)
                pending.append(neighbour)
    return frozenset(valves)


def tagged_ends(graph: FlowGraph, start: str, *, forward: bool) -> frozenset[str]:
    """The tagged nodes first reached from `start` along `send_to`, through untagged nodes only."""
    onward = graph.successors if forward else graph.predecessors
    found: set[str] = set()
    seen, pending = {start}, [start]
    while pending:
        for neighbour in onward.get(pending.pop(), frozenset()):
            if neighbour in graph.tags:
                found.add(neighbour)
            elif neighbour not in seen:
                seen.add(neighbour)
                pending.append(neighbour)
    return frozenset(found)


@dataclass(frozen=True)
class Descriptor:
    """An untagged valve named by class, line, nearest tagged item and side (all folded)."""

    class_key: str
    line_key: str
    next_to: str
    side: str  # "upstream" or "downstream"


def decode_descriptor(item: str) -> Descriptor:
    """The descriptor in an encoded reference item (`{"class": ..., "line_number": ...}`).

    Raises:
        ValueError: a key is missing or `side` is neither upstream nor downstream.
    """
    fields = json.loads(item)
    missing = [k for k in ("class", "line_number", "next_to", "side") if k not in fields]
    if missing or fields["side"] not in ("upstream", "downstream"):
        raise ValueError(f"expected class, line_number, next_to and a side, found {item!r}")
    return Descriptor(
        class_key=fold_class(fields["class"]),
        line_key=fold_line(fields["line_number"]),
        next_to=fold_tag(fields["next_to"]),
        side=fields["side"],
    )


class Namer:
    """Resolves descriptors on one flow graph and decides which valves can be named."""

    def __init__(self, graph: FlowGraph) -> None:
        self._graph = graph
        self._untagged: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
        for node, lines in graph.lines.items():
            if node in graph.tags:
                continue
            for line in lines:
                self._untagged[(fold_class(graph.classes[node]), line)].append(node)
        self._reached: dict[tuple[str, bool], frozenset[str]] = {}

    def _next_to_tags(self, node: str, *, forward: bool) -> frozenset[str]:
        """Folded tags of the tagged nodes first reached from `node` in one direction."""
        key = (node, forward)
        if key not in self._reached:
            ends = tagged_ends(self._graph, node, forward=forward)
            self._reached[key] = frozenset(self._graph.tags[end] for end in ends)
        return self._reached[key]

    def resolve(self, descriptor: Descriptor) -> frozenset[str]:
        """Every untagged node the descriptor picks out; empty when it matches none."""
        forward = descriptor.side == "upstream"  # upstream of next_to: next_to lies ahead
        pool = self._untagged.get((descriptor.class_key, descriptor.line_key), [])
        return frozenset(
            node for node in pool if descriptor.next_to in self._next_to_tags(node, forward=forward)
        )

    def _descriptors_of(self, valve: str) -> Iterator[Descriptor]:
        """Every descriptor shape the valve could be named by: its lines, sides, neighbours."""
        class_key = fold_class(self._graph.classes[valve])
        for line in sorted(self._graph.lines.get(valve, frozenset())):
            for forward, side in ((True, "upstream"), (False, "downstream")):
                for tag in sorted(self._next_to_tags(valve, forward=forward)):
                    yield Descriptor(class_key, line, tag, side)

    def is_nameable(self, valve: str) -> bool:
        """Whether some descriptor resolves to exactly this valve (an untagged valve's test)."""
        return any(self.resolve(d) == {valve} for d in self._descriptors_of(valve))

    def resolve_item(self, item: str) -> frozenset[str]:
        """The operated valves a reference item names: a tag, or an encoded descriptor."""
        if item.lstrip().startswith("{"):
            return self.resolve(decode_descriptor(item))
        tagged = self._graph.nodes_with_tag(fold_tag(item))
        return frozenset(node for node in tagged if is_operated(self._graph, node))
