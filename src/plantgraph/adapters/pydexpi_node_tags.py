"""A node's printed tag, read from the attributes pyDEXPI's `GraphLoader` flattened onto it.

A **tag** is the identifier printed on the drawing next to a symbol (`P-101` for a pump,
`PICSA-4712.02` for an instrument bubble); the graph finds a node by it.
"""

from __future__ import annotations

from collections.abc import Mapping

from plantgraph.adapters.pydexpi_loop_tags import BUBBLE_CLASSES
from plantgraph.graph import schema


def tag_of(node_class: str, attrs: Mapping[str, object]) -> str | None:
    """A node's tag, or None for a class that carries none (§3.6 "Node rules")."""
    if node_class in schema.EQUIPMENT_CLASSES:
        return as_str(attrs.get("tagName"))
    if node_class in schema.PIPING_CLASSES:
        # a safety device keeps its number in `positionNumber`, other parts in the component one
        return as_str(attrs.get("pipingComponentNumber")) or as_str(attrs.get("positionNumber"))
    if node_class == schema.NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value:
        return as_str(attrs.get("processSignalGeneratingFunctionNumber"))
    if node_class == schema.NodeClass.ACTUATING_FUNCTION.value:
        return as_str(attrs.get("actuatingFunctionNumber"))
    if node_class in BUBBLE_CLASSES:
        return bubble_tag(attrs)
    return None


def bubble_tag(attrs: Mapping[str, object]) -> str | None:
    """`<first letter><other letters>-<number>`, e.g. `PICSA-4712.02`; None if nothing is set.

    The other letters sit in `...Modifier` in our generated models but in `...Functions` in a
    real DEXPI file (EX01), so both are read; dropping `Functions` lost the drawing's `ICSA`.
    """
    parts = [
        as_str(attrs.get("processInstrumentationFunctionCategory")) or "",
        as_str(attrs.get("processInstrumentationFunctionModifier")) or "",
        as_str(attrs.get("processInstrumentationFunctions")) or "",
    ]
    letters = "".join(parts)
    number = as_str(attrs.get("processInstrumentationFunctionNumber")) or ""
    if not letters and not number:
        return None  # an empty bubble has no tag; validation reports it as missing
    return f"{letters}-{number}"


def as_str(value: object) -> str | None:
    """The value if it is a string, else None."""
    return value if isinstance(value, str) else None
