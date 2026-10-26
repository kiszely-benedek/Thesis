"""Ports, drawing groups and the result type of every process pattern (design realism 7, 7.2).

A **port** is where a pattern meets the rest of the plant: a pipe that enters or leaves the unit.
In the plan it is a line with one open end (an in-port line starts open, an out-port line ends
open), so a port left unwired is already a valid stub that leaves the drawing. The flowsheet grammar
joins two ports by giving the in-port's line the node `node_id` of the out-port as its source; the
DEXPI builder takes only equipment, a pipe tee or a spec break as a line end, so the grammar must
pick the joint accordingly.

A **drawing group** is the set of equipment one drawn sheet shows (the drafter decides which
equipment goes on which sheet). A *pinned* group is never merged into a neighbour.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from plantgraph.benchmark.v2.plan_models import EquipmentSpec, LineSpec, StreamKindV2
from plantgraph.benchmark.v2.trim_plan import TrimPlan


class PortDirection(str, Enum):
    """Whether the stream enters or leaves the unit."""

    IN = "in"
    OUT = "out"


class Phase(str, Enum):
    """The phase a port carries; the grammar never joins a gas out-port to a liquid in-port."""

    LIQUID = "L"
    GAS = "G"


class PortKind(str, Enum):
    """`process`: an ordinary stream; `recycle`: a stream that returns to an earlier unit."""

    PROCESS = "process"
    RECYCLE = "recycle"


class Port(BaseModel):
    """One typed connection point; `line_number` names the open line, `node_id` its last node.

    For an out-port `node_id` is the last node before the open end, for an in-port the first node
    after it.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    direction: PortDirection
    phase: Phase
    kind: PortKind = PortKind.PROCESS
    line_number: str
    node_id: str


def open_end_port(
    name: str, direction: PortDirection, phase: Phase, line: LineSpec, kind: PortKind | None = None
) -> Port:
    """The port at the open end of `line`: its destination for `out`, its source for `in`."""
    is_out = direction is PortDirection.OUT
    if (line.dst_id if is_out else line.src_id) is not None:
        end = "dst_id" if is_out else "src_id"
        raise ValueError(f"port {name!r}: line {line.line_number!r} is not open at its {end}")
    node_id = _open_end_node(line, is_out)
    if node_id is None:  # unreachable: a line joins at least two nodes
        raise ValueError(f"port {name!r}: line {line.line_number!r} has no node at its open end")
    return Port(
        name=name,
        direction=direction,
        phase=phase,
        kind=kind or PortKind.PROCESS,
        line_number=line.line_number,
        node_id=node_id,
    )


def _open_end_node(line: LineSpec, is_out: bool) -> str | None:
    """The node next to the open end: the last item for an out-port, the first for an in-port."""
    if line.items:
        return line.items[-1].node_id if is_out else line.items[0].node_id
    return line.src_id if is_out else line.dst_id


class DrawingGroups:
    """Collects `equipment id -> group` while a pattern is built."""

    def __init__(self) -> None:
        self._group_of: dict[str, str] = {}
        self._pinned: set[str] = set()

    def put(self, node_ids: Iterable[str], group: str, pinned: bool = False) -> None:
        """Put the equipment into `group`; a pinned group is never merged into a neighbour."""
        for node_id in node_ids:
            if node_id in self._group_of:
                raise ValueError(f"{node_id!r} is already in group {self._group_of[node_id]!r}")
            self._group_of[node_id] = group
        if pinned:
            self._pinned.add(group)

    @property
    def group_of(self) -> dict[str, str]:
        """The equipment id of each machine and its group."""
        return dict(self._group_of)

    @property
    def pinned(self) -> frozenset[str]:
        """The groups that must stay a sheet of their own."""
        return frozenset(self._pinned)


class PatternInstance(BaseModel):
    """One built pattern: the plan, its ports and the drawing group of each piece of equipment.

    `variant` names the choices the pattern drew (`tanks=3|metering=none|...`), for the answer key.
    """

    model_config = ConfigDict(frozen=True)

    pattern: str  # `U6`
    system_code: str  # `FLS`: the three letters of the drawing title
    variant: str
    plan: TrimPlan
    ports: tuple[Port, ...] = ()
    drawing_group_of: dict[str, str] = Field(default_factory=dict)
    pinned_groups: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _check_consistent(self) -> PatternInstance:
        equipment = {item.node_id for item in self.plan.equipment}
        if set(self.drawing_group_of) != equipment:
            raise ValueError(
                f"{self.pattern}: every piece of equipment needs exactly one drawing group; "
                f"equipment without one: {sorted(equipment - set(self.drawing_group_of))}, "
                f"groups for unknown equipment: {sorted(set(self.drawing_group_of) - equipment)}"
            )
        names = [port.name for port in self.ports]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.pattern}: port names must be unique, got {sorted(names)}")
        lines = {line.line_number for line in self.plan.lines}
        stray = [port.name for port in self.ports if port.line_number not in lines]
        if stray:
            raise ValueError(f"{self.pattern}: ports {stray} name lines that are not in the plan")
        return self

    def port(self, name: str) -> Port:
        """The port called `name`; raises with the known names when there is none."""
        for port in self.ports:
            if port.name == name:
                return port
        raise ValueError(f"{self.pattern} has no port {name!r}; its ports are {self.port_names}")

    @property
    def port_names(self) -> list[str]:
        """The names of all ports, in declaration order."""
        return [port.name for port in self.ports]

    @property
    def equipment(self) -> tuple[EquipmentSpec, ...]:
        """The pattern's equipment, in plan order."""
        return self.plan.equipment


def with_in_port_source(
    instance: PatternInstance,
    port_name: str,
    src_id: str,
    kind: StreamKindV2 = StreamKindV2.CROSS_UNIT,
) -> PatternInstance:
    """The instance with its in-port line fed from `src_id`, normally another unit's out-port node.

    This is how the flowsheet grammar joins two units: the out-port's `node_id` becomes the
    source of the in-port's line, which keeps its own line number and records `kind`. The line
    was open at its source; the out-port's own line stays open at its end.
    """
    port = instance.port(port_name)
    if port.direction is not PortDirection.IN:
        raise ValueError(
            f"expected an in-port, but {port_name!r} of {instance.pattern} is an out-port"
        )
    lines = tuple(
        line.model_copy(update={"src_id": src_id}) if line.line_number == port.line_number else line
        for line in instance.plan.lines
    )
    kinds = {**instance.plan.stream_kinds, port.line_number: kind}
    plan = instance.plan.model_copy(update={"lines": lines, "stream_kinds": kinds})
    return instance.model_copy(update={"plan": plan})
