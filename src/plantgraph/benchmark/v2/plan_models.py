"""The data the v2 planner hands to a backend, and the answer key it keeps (realism note 2, 11).

**Why a protocol.** The planner decides *what* the plant contains (pure Python, no pyDEXPI); a
`PlantBuilderV2` backend builds it. The DEXPI backend comes later; `tests/graph_plant_builder_v2.py`
is the simple graph backend that serves as its oracle. Every spec below is frozen: the planner
creates it once and the backend only reads it.

Terms: a **line** is one run of pipe with a line number, between two ends. An end is a machine, a
pipe tee on another line (a branch or a merge), or open (a stub that leaves the drawing). An
**inline item** is a small part sitting on the line: a valve, a tee, a flow element.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from plantgraph.benchmark.v2.streams import train_rng
from plantgraph.benchmark.v2.vocabulary import ItemKind, TrainConventions, draw_train_conventions
from plantgraph.graph.schema import Relation


class StreamKindV2(str, Enum):
    """Why a line exists. **Gold**: it enters the answer key, never the graph under retrieval."""

    PROCESS = "process"  # port to port inside a train
    CROSS_UNIT = "cross_unit"  # between two units
    RECYCLE = "recycle"  # compressor anti-surge, gas recycle, pump minimum flow
    TRIM = "trim"  # vents, drains, bypasses, taps, relief lines
    UTILITY_STUB = "utility_stub"  # a utility line that ends at the sheet edge


class _Spec(BaseModel):
    model_config = ConfigDict(frozen=True)


class EquipmentSpec(_Spec):
    """One machine or vessel. `has_motor` means an electric motor drives it (design 5.1)."""

    node_id: str
    node_class: str
    unit_no: int = Field(ge=1)
    tag: str
    has_motor: bool = False


class LineItemSpec(_Spec):
    """One inline part of a line; `tag` is None for untagged parts (tee, reducer, flange)."""

    node_id: str
    node_class: str
    tag: str | None = None


class LineSpec(_Spec):
    """One run of pipe: `src_id`, then `items` in flow order, then `dst_id`.

    A None end is open (the line enters or leaves the drawing there). An end that names an inline
    tee of another line makes this line a branch or a merge. Edges carry the line number and
    fluid code; all inline items belong to `unit_no`.
    """

    line_number: str
    fluid_code: str
    unit_no: int = Field(ge=1)
    src_id: str | None
    dst_id: str | None
    items: tuple[LineItemSpec, ...] = ()

    @model_validator(mode="after")
    def _check_has_a_pipe(self) -> LineSpec:
        connected = len(self.items) + (self.src_id is not None) + (self.dst_id is not None)
        if connected < 2:
            raise ValueError(
                f"line {self.line_number!r} must join at least two nodes (items plus connected "
                f"ends); got {len(self.items)} items, src_id={self.src_id!r}, "
                f"dst_id={self.dst_id!r}"
            )
        return self


class InstrumentSpec(_Spec):
    """One instrument node: a sensor, an indicator or controller, or an actuator.

    `tag` is None for an actuator (drawn as part of its valve). `loop_tag` is the tag of the
    loop's controller bubble; `measured_variable` is the first ISA letter (`F`, `T`, ...).
    """

    node_id: str
    node_class: str
    unit_no: int = Field(ge=1)
    tag: str | None
    loop_tag: str
    measured_variable: str


#: The edges a planner may add between existing nodes; `send_to` edges come from `LineSpec`.
LINK_RELATIONS: frozenset[Relation] = frozenset(
    {Relation.MEASURED_BY, Relation.SEND_SIGNAL_TO, Relation.CONTROL, Relation.HAS_AGITATOR}
)


class LinkSpec(_Spec):
    """One edge between two existing nodes: a sensing, a signal, an actuation or an agitator."""

    relation: Relation
    source_id: str
    target_id: str

    @model_validator(mode="after")
    def _check_relation(self) -> LinkSpec:
        if self.relation not in LINK_RELATIONS:
            allowed = sorted(relation.value for relation in LINK_RELATIONS)
            raise ValueError(
                f"a link relation must be one of {allowed}, got {self.relation.value!r}"
            )
        return self


class PlantBuilderV2(Protocol):
    """What a backend must do. Callers add nodes before any line or link that names them."""

    @property
    def backend_version(self) -> str:
        """Identifier of the backend; ends up in `GenerationRecordV2.pydexpi_version`."""
        ...

    def add_section(self, unit_no: int, name: str) -> None:
        """Add one process unit; `name` is its drawing title, e.g. `DST Crude column`."""
        ...

    def add_equipment(self, spec: EquipmentSpec) -> None:
        """Add one piece of equipment to its unit."""
        ...

    def add_line(self, spec: LineSpec) -> None:
        """Add one line with its inline items."""
        ...

    def add_instrument(self, spec: InstrumentSpec) -> None:
        """Add one instrument node."""
        ...

    def add_link(self, spec: LinkSpec) -> None:
        """Add one measured_by / send_signal_to / control / has_agitator edge."""
        ...


# --- the answer key ----------------------------------------------------------------------------


class NodeGold(_Spec):
    """What a node is *for* in its pattern, and which drawing group it is planned into."""

    role: str  # e.g. `reflux_drum`, `cv_station_bypass`
    drawing_group: str


class TrainRecord(_Spec):
    """One train and the naming conventions its design contractor used."""

    train_no: int = Field(ge=1)
    conventions: TrainConventions


class UnitRecord(_Spec):
    """Which pattern and variant a unit is, and the train it belongs to."""

    unit_no: int = Field(ge=1)
    train_no: int = Field(ge=1)
    pattern: str
    variant: str


class GenerationRecordV2(BaseModel):
    """The generation's answer key (gold): never stored in the graph under retrieval.

    `generator_config` is the config's JSON, so this one record can reproduce the run.
    """

    plant_id: str
    seed: int
    generator_config: str
    pydexpi_version: str
    trains: tuple[TrainRecord, ...] = ()
    units: tuple[UnitRecord, ...] = ()
    stream_kind: dict[str, StreamKindV2] = Field(default_factory=dict)  # by line number
    item_kind: dict[str, ItemKind] = Field(default_factory=dict)  # by tag
    node_gold: dict[str, NodeGold] = Field(default_factory=dict)  # by node id
    #: wiring never raises: an unmatched out-port becomes an open stub, an unmatched in-port takes
    #: the train's feed farm (base 8.2); both counts are reported
    open_stub_count: int = 0
    feed_farm_fill_count: int = 0


def draw_train_records(seed: int, n_trains: int) -> tuple[TrainRecord, ...]:
    """Draw the conventions of trains 1..n_trains; each train reads only its own stream."""
    return tuple(
        TrainRecord(
            train_no=train_no, conventions=draw_train_conventions(train_rng(seed, train_no))
        )
        for train_no in range(1, n_trains + 1)
    )
