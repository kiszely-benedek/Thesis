"""The line view: item-to-item flow through the pipe parts nobody names.

On a v2 drawing, two items (pumps, tanks, valves...) are rarely joined directly: a pipe tee, a
blind flange or a reducer sits between them. Those parts carry no printed tag, so a question such
as "what is downstream of valve V-1?" means the next *tagged line item*, not the tee. The line view
folds every flow edge that runs through such parts into one `LineEdge` from item to item:

- a **line item** is an equipment item or a valve (`EQUIPMENT_CLASSES | VALVE_CLASSES`);
- every other node on the pipe is *passed through*: an untagged fitting is counted
  (`n_fittings`), a tagged inline component (a strainer, an orifice) is named (`via_tags`);
- a line item with no line edge in (or out) is a **line end**: it marks where a line starts (or
  stops), which is how "nothing flows into it" questions are answered.

This module is pure and sees only classes, tags and flow edges, so the same code serves the
plant API and the Neo4j loader. It must never import the answer key: the gold side has its own,
independent walk (`qa.questions.common.next_path_items`), and `line_view_fidelity` compares them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.graph.schema import (
    CLASS_SPECS,
    CONNECTOR_CLASSES,
    EQUIPMENT_CLASSES,
    PIPING_CLASSES,
    UNRESOLVED_CONNECTOR_LABEL,
    VALVE_CLASSES,
    NodeCategory,
    NodeClass,
)

#: What a node is, in the words a question uses. `inline` = a part on the pipe (fitting, strainer,
#: flow element) that a line passes through.
Kind = Literal["equipment", "valve", "instrument", "actuator", "connector", "inline"]

#: The classes a line view reports as items.
LINE_ITEM_CLASSES: frozenset[str] = EQUIPMENT_CLASSES | VALVE_CLASSES

_ACTUATOR_CLASSES = frozenset(
    {NodeClass.ACTUATING_FUNCTION.value, NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value}
)
_INSTRUMENT_CLASSES = (
    frozenset(
        node_class.value
        for node_class, spec in CLASS_SPECS.items()
        if spec.category is NodeCategory.INSTRUMENTATION
    )
    - _ACTUATOR_CLASSES
)

NO_INFLOW_MARK = "[no inflow]"
NO_OUTFLOW_MARK = "[no outflow]"


class LineEdge(BaseModel):
    """Flow from one line item to the next, with what the pipe passes through on the way."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    #: Tags of tagged inline components passed through (strainers, orifices), in flow order.
    via_tags: tuple[str, ...] = ()
    #: How many untagged pipe parts (tees, flanges, reducers) were passed through.
    n_fittings: int = 0


class LineEnds(BaseModel):
    """The line items a line starts or stops at."""

    model_config = ConfigDict(frozen=True)

    no_inflow: frozenset[str]
    no_outflow: frozenset[str]

    def marks_of(self, item: str) -> tuple[str, ...]:
        """`[no inflow]` and/or `[no outflow]`; empty for an item in the middle of a line."""
        marks = (
            (item in self.no_inflow, NO_INFLOW_MARK),
            (item in self.no_outflow, NO_OUTFLOW_MARK),
        )
        return tuple(mark for applies, mark in marks if applies)


def kind_of(node_class: str) -> Kind:
    """The kind of a node class.

    Raises:
        ValueError: the class is a structural node or unknown, which is no item on a drawing.
    """
    if node_class in EQUIPMENT_CLASSES:
        return "equipment"
    if node_class in VALVE_CLASSES:
        return "valve"
    if node_class in _ACTUATOR_CLASSES:
        return "actuator"
    if node_class in _INSTRUMENT_CLASSES:
        return "instrument"
    if node_class in CONNECTOR_CLASSES or node_class == UNRESOLVED_CONNECTOR_LABEL:
        return "connector"
    # whatever else sits on a pipe: fittings, flow elements, and the `GenericItem` fallback
    if node_class in PIPING_CLASSES or node_class == NodeClass.GENERIC_ITEM.value:
        return "inline"
    raise ValueError(f"expected a drawing item's node class, found {node_class!r}")


def fold_line_edges(
    classes: Mapping[str, str],
    tags: Mapping[str, str | None],
    flow_edges: Iterable[tuple[str, str]],
) -> list[LineEdge]:
    """Fold flow edges into line edges, sorted by (source, target).

    Args:
        classes: node id -> node class, for every node a flow edge touches.
        tags: node id -> printed tag, or `None` for an untagged part.
        flow_edges: `(from, to)` pairs of the flow relation (`send_to`).

    Raises:
        ValueError: a flow edge touches a node whose class is not given.
    """
    successors = _successors(classes, flow_edges)
    edges: list[LineEdge] = []
    for source in sorted(n for n, c in classes.items() if c in LINE_ITEM_CLASSES):
        edges += _edges_from(source, successors, classes, tags)
    return edges


def _successors(
    classes: Mapping[str, str], flow_edges: Iterable[tuple[str, str]]
) -> dict[str, list[str]]:
    found: dict[str, set[str]] = {}
    for source, target in flow_edges:
        for node in (source, target):
            if node not in classes:
                raise ValueError(
                    f"expected a node class for {node!r} (a flow edge end), found none"
                )
        found.setdefault(source, set()).add(target)
    return {node: sorted(targets) for node, targets in found.items()}


def _edges_from(
    source: str,
    successors: Mapping[str, list[str]],
    classes: Mapping[str, str],
    tags: Mapping[str, str | None],
) -> list[LineEdge]:
    """Breadth-first over pipe parts: a part is passed through, a line item ends the walk.

    An item reached by two routes keeps the shorter one (a tie: the route met first).
    """
    found: dict[str, tuple[str, ...]] = {}
    seen = {source}
    frontier: list[tuple[str, tuple[str, ...]]] = [(source, ())]
    while frontier:
        next_frontier: list[tuple[str, tuple[str, ...]]] = []
        for current, passed in frontier:
            for nxt in successors.get(current, ()):
                if nxt in seen:
                    continue
                if classes[nxt] in LINE_ITEM_CLASSES:
                    found.setdefault(nxt, passed)
                else:
                    seen.add(nxt)
                    next_frontier.append((nxt, (*passed, nxt)))
        frontier = next_frontier
    return [_line_edge(source, target, passed, tags) for target, passed in sorted(found.items())]


def _line_edge(
    source: str, target: str, passed: tuple[str, ...], tags: Mapping[str, str | None]
) -> LineEdge:
    passed_tags = tuple(tag for node in passed if (tag := tags.get(node)) is not None)
    return LineEdge(
        source=source,
        target=target,
        via_tags=passed_tags,
        n_fittings=len(passed) - len(passed_tags),
    )


def line_ends(line_items: Iterable[str], edges: Iterable[LineEdge]) -> LineEnds:
    """Which of `line_items` have no line edge into them, and which none out of them."""
    edge_list = list(edges)
    with_inflow = {edge.target for edge in edge_list}
    with_outflow = {edge.source for edge in edge_list}
    items = set(line_items)
    return LineEnds(
        no_inflow=frozenset(items - with_inflow), no_outflow=frozenset(items - with_outflow)
    )
