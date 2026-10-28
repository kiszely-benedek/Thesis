"""Item, edge and filter types of the plant API (design §3.1-§3.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.graph.line_view import Kind
from plantgraph.graph.schema import UNRESOLVED_CONNECTOR_LABEL

#: The edge relations of an item graph: the four of `graph.schema.Relation`, plus `line_to`, which
#: exists only in a graph built with the line view (flow from one line item to the next, through
#: the untagged pipe parts between them; `graph/line_view.py`).
ItemRelation = Literal["send_to", "send_signal_to", "control", "measured_by", "line_to"]
#: Which relations a primitive follows: material flow, instrument signals, both, or (line view
#: only) item-to-item flow that passes through fittings.
RelationGroup = Literal["flow", "signal", "any", "line"]
#: "downstream" follows edge direction, "upstream" reverses it, "both" ignores it.
Direction = Literal["downstream", "upstream", "both"]
GroupBy = Literal["node_class", "unit", "sheet"]
#: A property value as a prompt or a GraphML file can hold it (lists are joined into a string).
PropertyValue = str | int | float | bool

RELATION_GROUPS: dict[RelationGroup, frozenset[str]] = {
    "flow": frozenset({"send_to"}),
    "signal": frozenset({"send_signal_to", "control", "measured_by"}),
    "any": frozenset({"send_to", "send_signal_to", "control", "measured_by"}),
    "line": frozenset({"line_to"}),
}

#: `node_class` of an off-page connector whose partner the resolver did not find.
UNRESOLVED_CONNECTOR_CLASS = UNRESOLVED_CONNECTOR_LABEL


class PlantApiError(ValueError):
    """A call the API cannot answer: unknown tag, handle, label or tool, or bad arguments.

    An agent loop turns this into an `error: ...` observation, so the message
    says what was expected and what was found.
    """


class UnknownTagError(PlantApiError):
    """A call named a tag (or untagged item id) the plant does not have."""

    def __init__(self, tag: str, message: str) -> None:
        super().__init__(message)
        self.tag = tag


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
    #: What the item is in a question's words; set only in a graph built with the line view.
    kind: Kind | None = None
    #: `[no inflow]` / `[no outflow]` for a line item where a line starts or stops (line view only).
    line_marks: tuple[str, ...] = ()


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
    #: `line_to` edges only: tags of tagged inline components (strainers, orifices) passed through.
    via_tags: tuple[str, ...] = ()
    #: `line_to` edges only: how many untagged pipe parts (tees, flanges) were passed through.
    n_fittings: int = 0


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
    #: `equipment`, `valve`, ... (line view only). The label `"Valve"` means `kind="valve"`.
    kind: Kind | None = None


def sheet_of_key(local_key: str) -> str:
    """The sheet of a local key, which reads `<sheet>:<id>`."""
    return local_key.partition(":")[0]
