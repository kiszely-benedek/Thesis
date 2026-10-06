"""Item, edge and filter types of the plant API (design §3.1-§3.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.graph.schema import UNRESOLVED_CONNECTOR_LABEL

#: The four topology relations an item edge can carry (`graph.schema.Relation`).
ItemRelation = Literal["send_to", "send_signal_to", "control", "measured_by"]
#: Which relations a primitive follows: material flow, instrument signals, or both.
RelationGroup = Literal["flow", "signal", "any"]
#: "downstream" follows edge direction, "upstream" reverses it, "both" ignores it.
Direction = Literal["downstream", "upstream", "both"]
GroupBy = Literal["node_class", "unit", "sheet"]
#: A property value as a prompt or a GraphML file can hold it (lists are joined into a string).
PropertyValue = str | int | float | bool

RELATION_GROUPS: dict[RelationGroup, frozenset[str]] = {
    "flow": frozenset({"send_to"}),
    "signal": frozenset({"send_signal_to", "control", "measured_by"}),
    "any": frozenset({"send_to", "send_signal_to", "control", "measured_by"}),
}

#: `node_class` of an off-page connector whose partner the resolver did not find.
UNRESOLVED_CONNECTOR_CLASS = UNRESOLVED_CONNECTOR_LABEL


class PlantApiError(ValueError):
    """A call the API cannot answer: unknown tag, handle, label or tool, or bad arguments.

    An agent loop turns this into an `error: ...` observation, so the message
    says what was expected and what was found.
    """


class ItemRecord(BaseModel):
    """One plant item: every drawing of the same physical thing, merged."""

    model_config = ConfigDict(frozen=True)

    #: The home occurrence's local key; shown to a model only as the name of an untagged item.
    item_id: str
    #: The drawn tag (e.g. `P-101`), else an imported valve's printed name; `None` for a stub.
    tag: str | None
    node_class: str
    #: The class and its ancestors, e.g. `("BallValve", "OperatedValve", "PipingComponent")`.
    labels: tuple[str, ...]
    unit_id: str | None
    #: Every sheet the item is drawn on, sorted.
    sheets: tuple[str, ...]
    #: Local keys of every drawing of the item, for the trace and evidence recall.
    occurrence_keys: tuple[str, ...]
    #: Visible properties of the home drawing (`graph.schema.VISIBLE_NODE_PROPERTIES` without
    #: `node_class`, which is a field), with `unit_id` filled as the field is.
    properties: dict[str, PropertyValue] = Field(default_factory=dict)


class ItemEdge(BaseModel):
    """A directed connection between two items, with any off-page connectors it crosses."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    relation: ItemRelation
    #: Local keys of the connector stubs crossed (out-stub, in-stub, ...); empty on one sheet.
    via: tuple[str, ...] = ()
    #: Visible edge properties (`line_number`, `fluid_code`, `dexpi_label`) of the drawn edge;
    #: across a stub pair, the edge into the outgoing stub, as `resolution/merge.py` keeps it.
    properties: dict[str, PropertyValue] = Field(default_factory=dict)


class ItemFilter(BaseModel):
    """The only predicate language: every set field must match (AND); unset fields are ignored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Any label in the class chain: `"Pump"`, `"OperatedValve"`, `"Equipment"`, ...
    label: str | None = None
    #: Exact class name, e.g. `"CentrifugalPump"`.
    node_class: str | None = None
    unit: str | None = None
    #: Items whose unit is not this one (items with no unit pass).
    not_unit: str | None = None
    sheet: str | None = None
    #: Matched as `find_by_tag` does: case and whitespace folded.
    tag: str | None = None


def sheet_of_key(local_key: str) -> str:
    """The sheet of a local key, which reads `<sheet>:<id>`."""
    return local_key.partition(":")[0]
