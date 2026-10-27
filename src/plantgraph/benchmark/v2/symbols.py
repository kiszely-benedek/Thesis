"""Which nodes are drawn as a symbol, and of what kind (the counting rule, design realism 12.1).

A P&ID **symbol** is one drawn shape: a machine, a valve, a fitting, a flow element, an instrument
bubble. The rule is fixed in the design before any measurement so it cannot be tuned: a symbol is
equipment, a valve, a fitting, a primary element (the flow element that senses a flow), a
signal-generating function (the sensor) or an indicating/controlling function (the bubble,
which includes the controller `ProcessControlFunction`). A `PipeTee` is a junction, not a symbol;
a spec break and the actuators are drawn as part of their line or valve.
"""

from __future__ import annotations

from enum import Enum

from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.graph import schema
from plantgraph.graph.schema import NodeClass


class SymbolKind(str, Enum):
    """The family of a node for counting."""

    EQUIPMENT = "equipment"
    VALVE = "valve"  # operated, check and safety valves
    FITTING = "fitting"
    PRIMARY_ELEMENT = "primary_element"
    INSTRUMENT = "instrument"  # sensor or bubble
    JUNCTION = "junction"  # pipe tee: not a symbol
    NOT_DRAWN = "not_drawn"  # spec break, actuators


_INSTRUMENT_CLASSES = frozenset(
    {
        NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
        NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
        # a controller bubble: pyDEXPI makes it a subclass of the instrumentation function
        NodeClass.PROCESS_CONTROL_FUNCTION.value,
    }
)


def symbol_kind(node_class: str) -> SymbolKind:
    """The counting family of `node_class`."""
    if node_class in schema.EQUIPMENT_CLASSES:
        return SymbolKind.EQUIPMENT
    if node_class in schema.VALVE_CLASSES:
        return SymbolKind.VALVE
    if node_class in schema.FITTING_CLASSES:
        return SymbolKind.FITTING
    if node_class in schema.PRIMARY_ELEMENT_CLASSES:
        return SymbolKind.PRIMARY_ELEMENT
    if node_class in _INSTRUMENT_CLASSES:
        return SymbolKind.INSTRUMENT
    if node_class in schema.JUNCTION_CLASSES:
        return SymbolKind.JUNCTION
    return SymbolKind.NOT_DRAWN


def is_symbol(node_class: str) -> bool:
    """True when a node of this class is drawn as a symbol (junctions and actuators are not)."""
    return symbol_kind(node_class) not in (SymbolKind.JUNCTION, SymbolKind.NOT_DRAWN)


def plan_node_classes(plan: TrimPlan) -> dict[str, str]:
    """Node id -> node class of every equipment, inline part and instrument of the plan."""
    classes = {item.node_id: item.node_class for item in plan.equipment}
    for line in plan.lines:
        classes.update({item.node_id: item.node_class for item in line.items})
    classes.update({item.node_id: item.node_class for item in plan.instruments})
    return classes
