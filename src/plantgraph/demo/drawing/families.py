"""Which kind of symbol a graph node is drawn as, and the text printed on it.

The drawing shows only what the system itself sees (a node's visible properties), never the
answer key. A node whose `node_class` the schema does not know is an error, not a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import networkx as nx

from plantgraph.demo.drawing.glyph_families import SMALL_GLYPH_SIZE, TALL_GLYPHS, glyph_of
from plantgraph.demo.drawing.models import Family, LayoutConfig
from plantgraph.graph import schema
from plantgraph.graph.schema import NodeCategory, NodeClass

#: Symbols that sit in the pipe-flow drawing; the others sit in the instrument band above it.
FLOW_FAMILIES: frozenset[str] = frozenset(
    {"equipment", "valve", "fitting", "junction", "primary_element", "break", "pipe_flag"}
)

#: The piping kinds that are neither valves nor equipment, each its own layout family.
_INLINE_FAMILY: dict[str, Family] = {
    "fitting": "fitting",
    "junction": "junction",
    "primary_element": "primary_element",
    "break": "break",
}
_PIPE_FLAG_CLASSES = frozenset(
    {
        NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value,
        NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value,
    }
)
_SIGNAL_FLAG_CLASSES = frozenset(
    {
        NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value,
        NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
    }
)


#: Families printed as tag plus class name (an untagged item shows the class name alone).
_CLASS_LABELLED = frozenset(
    {"equipment", "valve", "fitting", "junction", "primary_element", "break"}
)

#: Every instrumentation class (a sensor, a controller, an actuator): drawn as a bubble in the band.
_INSTRUMENT_CLASSES: frozenset[str] = frozenset(
    node_class.value
    for node_class, spec in schema.CLASS_SPECS.items()
    if spec.category is NodeCategory.INSTRUMENTATION
)


@dataclass(frozen=True)
class NodeInfo:
    """What the layout needs to know about one sheet node."""

    node_id: str
    family: Family
    node_class: str
    attrs: dict[str, Any]

    @property
    def is_flow(self) -> bool:
        """True for symbols drawn in the pipe-flow part (not the instrument band)."""
        return self.family in FLOW_FAMILIES

    @property
    def flag_direction(self) -> Literal["in", "out"] | None:
        """For an off-page connector: whether flow comes in from, or goes out to, another sheet."""
        if self.family not in ("pipe_flag", "signal_flag"):
            return None
        return "in" if "FlowIn" in self.node_class else "out"


def family_of(node_class: str) -> Family:
    """The symbol family of a schema node class."""
    if node_class in schema.EQUIPMENT_CLASSES or node_class == NodeClass.GENERIC_ITEM.value:
        return "equipment"  # a class the schema did not curate is drawn as a plain box
    if node_class in schema.VALVE_CLASSES:
        return "valve"
    if node_class in _INSTRUMENT_CLASSES:
        return "instrument"
    inline = _inline_family(node_class)
    if inline is not None:
        return inline
    if node_class in _PIPE_FLAG_CLASSES:
        return "pipe_flag"
    if node_class in _SIGNAL_FLAG_CLASSES:
        return "signal_flag"
    raise ValueError(f"cannot draw node_class {node_class!r}; expected one of the sheet classes")


def _inline_family(node_class: str) -> Family | None:
    """The family of a piping class that is not a valve (fitting, pipe tee, flow meter, break)."""
    try:
        kind = schema.CLASS_SPECS[NodeClass(node_class)].piping_kind
    except ValueError:
        return None  # not a schema class at all; `family_of` raises for it
    return None if kind is None else _INLINE_FAMILY.get(kind)


def classify_nodes(graph: nx.DiGraph[str]) -> dict[str, NodeInfo]:
    """Every node of a sheet graph as a `NodeInfo`, keyed by node id."""
    infos: dict[str, NodeInfo] = {}
    for node_id, attrs in graph.nodes(data=True):
        node_class = attrs.get("node_class")
        if not isinstance(node_class, str):
            raise ValueError(f"node {node_id!r} has no node_class; found {node_class!r}")
        infos[node_id] = NodeInfo(node_id, family_of(node_class), node_class, dict(attrs))
    return infos


def symbol_size(
    family: Family, config: LayoutConfig, node_class: str | None = None
) -> tuple[float, float]:
    """Width and height of a symbol: flags are larger (more text).

    In the ISO style inline items are smaller and columns taller; classic ignores `node_class`.
    """
    if family in ("pipe_flag", "signal_flag"):
        return config.flag_width, config.flag_height
    width, height = config.box_width, config.box_height
    if config.glyph_style == "classic":
        return width, height
    factors = SMALL_GLYPH_SIZE.get(family)
    if factors is None and node_class is not None:
        factors = TALL_GLYPHS.get(glyph_of(node_class))
    return (width, height) if factors is None else (width * factors[0], height * factors[1])


def target_sheet(info: NodeInfo) -> str | None:
    """The sheet an off-page connector points to (None for other symbols or unresolved flags)."""
    reference = info.attrs.get("referenced_drawing_number")
    if info.family not in ("pipe_flag", "signal_flag") or reference is None:
        return None
    return str(reference)


def symbol_labels(info: NodeInfo) -> tuple[str, ...]:
    """The text lines printed inside a symbol; properties the node lacks are left out."""
    attrs = info.attrs
    if info.family in _CLASS_LABELLED:
        return _present(attrs.get("tag"), info.node_class)
    if info.family == "instrument":
        # an actuating function has no tag of its own: it shares its valve's
        return _present(attrs.get("loop_tag") or attrs.get("tag"), attrs.get("measured_variable"))
    return _flag_labels(info)


def _flag_labels(info: NodeInfo) -> tuple[str, ...]:
    attrs = info.attrs
    direction = "FROM" if info.flag_direction == "in" else "TO"
    reference = attrs.get("referenced_drawing_number")
    heading = f"{direction} DWG {reference if reference is not None else '?'}"
    if info.family == "signal_flag":
        return _present(heading, attrs.get("loop_tag"))
    number = attrs.get("connector_number")
    referenced = attrs.get("referenced_connector_number")
    return _present(
        heading,
        attrs.get("line_number"),
        attrs.get("fluid_code"),
        None if number is None else f"CONN {number}",
        None if referenced is None else f"REF {referenced}",
    )


def _present(*values: object) -> tuple[str, ...]:
    return tuple(str(value) for value in values if value not in (None, ""))
