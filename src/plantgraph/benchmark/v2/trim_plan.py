"""What a trim returns (`TrimPlan`) and the small recorder trims use to build one (`TrimDraft`).

A trim does not write to a backend itself. It returns a frozen `TrimPlan` holding

- `run`: parts that sit *inline* on the caller's main line, in flow order (a pump's suction block
  and strainer). The caller puts them into its own `LineSpec`;
- `equipment`, `lines`, `instruments`, `links`: everything else the trim adds, in the form the
  `PlantBuilderV2` protocol takes (branches, vent lines, local gauges);
- the answer key: a role per node, a stream kind per line, and named `ports` the caller may wire
  further (the tee a relief line starts from).

`TrimPlan.write` sends a plan to any backend: the graph oracle in the tests or the DEXPI builder.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    InstrumentSpec,
    LineItemSpec,
    LineSpec,
    LinkSpec,
    PlantBuilderV2,
    StreamKindV2,
)
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.vocabulary import LINE_SPECS
from plantgraph.graph.schema import NodeClass, Relation

_PSGF = NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value
_BREAK = NodeClass.PROPERTY_BREAK.value


class TrimPlan(BaseModel):
    """The planned parts of one trim (or of several, after `combine`). Frozen once built."""

    model_config = ConfigDict(frozen=True)

    run: tuple[LineItemSpec, ...] = ()
    equipment: tuple[EquipmentSpec, ...] = ()
    lines: tuple[LineSpec, ...] = ()
    instruments: tuple[InstrumentSpec, ...] = ()
    links: tuple[LinkSpec, ...] = ()
    roles: dict[str, str] = Field(default_factory=dict)  # node id -> role, for the answer key
    stream_kinds: dict[str, StreamKindV2] = Field(default_factory=dict)  # by line number
    ports: dict[str, str] = Field(default_factory=dict)  # port name -> node id
    #: gold: the node ids of every installed A/B(/C) set (two or more identical machines).
    #: Consecutive spare naming (`P-1203`, `P-1204`) leaves no trace of a set in the tags, so it is
    #: kept here. Left out of dumps on purpose: the frozen plan digest (design 14.2) hashes only
    #: what is drawn.
    spare_sets: tuple[tuple[str, ...], ...] = Field(default=(), exclude=True)

    def write(self, builder: PlantBuilderV2) -> None:
        """Send the plan to `builder`: equipment, lines, instruments, links, in that order.

        A branch line may start at a tee of an earlier line, so `lines` keeps creation order.
        """
        if self.run:
            raise ValueError(
                f"the plan still has an inline run {[part.node_id for part in self.run]}; "
                "close it with with_main_line first"
            )
        for equipment in self.equipment:
            builder.add_equipment(equipment)
        for line in self.lines:
            builder.add_line(line)
        for instrument in self.instruments:
            builder.add_instrument(instrument)
        for link in self.links:
            builder.add_link(link)

    def with_main_line(self, main: LineSpec) -> TrimPlan:
        """The plan with `run` closed into the caller's line `main`, which comes first.

        `main` must contain every part of the run: branches may start at its tees.
        """
        present = {part.node_id for part in main.items}
        missing = [part.node_id for part in self.run if part.node_id not in present]
        if missing:
            raise ValueError(
                f"main line {main.line_number!r} lacks the run parts {missing}; "
                "expected the caller's line to contain the whole run"
            )
        return self.model_copy(update={"run": (), "lines": (main, *self.lines)})

    def with_port_prefix(self, prefix: str) -> TrimPlan:
        """The same plan with every port renamed `<prefix>.<name>`, so plans can be combined."""
        renamed = {f"{prefix}.{name}": node_id for name, node_id in self.ports.items()}
        return self.model_copy(update={"ports": renamed})


def combine(*plans: TrimPlan) -> TrimPlan:
    """One plan from several: runs and lists are joined in order, keyed fields must not collide."""
    return TrimPlan(
        run=tuple(part for plan in plans for part in plan.run),
        equipment=tuple(item for plan in plans for item in plan.equipment),
        lines=tuple(line for plan in plans for line in plan.lines),
        instruments=tuple(item for plan in plans for item in plan.instruments),
        links=tuple(link for plan in plans for link in plan.links),
        roles=_merge_keyed([plan.roles for plan in plans], "role"),
        stream_kinds=_merge_keyed([plan.stream_kinds for plan in plans], "stream kind"),
        ports=_merge_keyed([plan.ports for plan in plans], "port"),
        spare_sets=tuple(spare for plan in plans for spare in plan.spare_sets),
    )


def _merge_keyed[V](tables: list[Mapping[str, V]], what: str) -> dict[str, V]:
    merged: dict[str, V] = {}
    for table in tables:
        clash = sorted(set(merged) & set(table))
        if clash:
            raise ValueError(f"two plans define the same {what} {clash}; rename with a prefix")
        merged.update(table)
    return merged


def main_line(
    ctx: TrimContext,
    style: LineStyle,
    src_id: str | None,
    run: tuple[LineItemSpec, ...],
    dst_id: str | None,
) -> LineSpec:
    """The caller's main line around a trim's `run`, with the next line number of the unit.

    A `PropertyBreak` in the run is a spec change (rule L20), so the stretch after it gets a new
    line number whose spec is the next piping class (`_style_after_break`).
    """
    after_break = None
    if any(part.node_class == _BREAK for part in run):
        after_break = ctx.numbering.line_number(_style_after_break(style))
    return LineSpec(
        line_number=ctx.numbering.line_number(style),
        fluid_code=style.service,
        unit_no=ctx.unit_no,
        src_id=src_id,
        dst_id=dst_id,
        items=run,
        line_number_after_break=after_break,
    )


def _style_after_break(style: LineStyle) -> LineStyle:
    """The next piping class in rating order (the last steps back): the spec always changes."""
    index = LINE_SPECS.index(style.spec)
    following = LINE_SPECS[index + 1] if index + 1 < len(LINE_SPECS) else LINE_SPECS[index - 1]
    return style.model_copy(update={"spec": following})


class TrimDraft:
    """Collects the parts of one trim and hands out ids, tags and line numbers as it goes."""

    def __init__(self, ctx: TrimContext, style: LineStyle) -> None:
        self.ctx = ctx
        self.style = style
        self._equipment: list[EquipmentSpec] = []
        self._lines: list[LineSpec] = []
        self._instruments: list[InstrumentSpec] = []
        self._links: list[LinkSpec] = []
        self._roles: dict[str, str] = {}
        self._stream_kinds: dict[str, StreamKindV2] = {}

    # ---- parts ----------------------------------------------------------------------------------

    def part(self, node_class: str, role: str) -> LineItemSpec:
        """An inline part with the tag its class prints (None for a tee, flange, reducer)."""
        return self.tagged_part(node_class, role, self.ctx.numbering.part_tag(node_class))

    def tagged_part(self, node_class: str, role: str, tag: str | None) -> LineItemSpec:
        """An inline part with a tag the caller chose (a loop-numbered valve or flow element)."""
        spec = LineItemSpec(node_id=self.ctx.numbering.node_id(), node_class=node_class, tag=tag)
        self._roles[spec.node_id] = role
        return spec

    def dealt_part(self, deck_role: str, role: str) -> LineItemSpec:
        """An inline part whose class is the next card of `deck_role`'s deck."""
        return self.part(self.ctx.deal_class(deck_role), role)

    def equipment(self, node_class: str, type_code: str, role: str) -> EquipmentSpec:
        """A piece of equipment a trim adds (a condensate drain pot)."""
        spec = EquipmentSpec(
            node_id=self.ctx.numbering.node_id(),
            node_class=node_class,
            unit_no=self.ctx.unit_no,
            tag=self.ctx.numbering.equipment_tag(type_code),
        )
        self._equipment.append(spec)
        self._roles[spec.node_id] = role
        return spec

    # ---- lines ----------------------------------------------------------------------------------

    def line(
        self,
        src_id: str | None,
        parts: list[LineItemSpec],
        dst_id: str | None,
        kind: StreamKindV2 = StreamKindV2.TRIM,
        style: LineStyle | None = None,
    ) -> LineSpec:
        """A branch line: its own line number, the stream kind for the answer key."""
        used = style or self.style
        spec = LineSpec(
            line_number=self.ctx.numbering.line_number(used),
            fluid_code=used.service,
            unit_no=self.ctx.unit_no,
            src_id=src_id,
            dst_id=dst_id,
            items=tuple(parts),
        )
        self._lines.append(spec)
        self._stream_kinds[spec.line_number] = kind
        return spec

    # ---- instruments ----------------------------------------------------------------------------

    def sensor(self, tag: str, loop_tag: str, location_id: str, role: str) -> str:
        """A sensor (PSGF) located on `location_id`; returns its id."""
        spec = InstrumentSpec(
            node_id=self.ctx.numbering.node_id(),
            node_class=_PSGF,
            unit_no=self.ctx.unit_no,
            tag=tag,
            loop_tag=loop_tag,
            measured_variable=loop_tag[0],
        )
        self._instruments.append(spec)
        self._roles[spec.node_id] = role
        self.link(Relation.MEASURED_BY, location_id, spec.node_id)
        return spec.node_id

    def bubble(self, tag: str, sensor_id: str, role: str) -> str:
        """An indicator bubble (PIF) fed by `sensor_id`; the sensor's loop tag is the bubble's."""
        spec = InstrumentSpec(
            node_id=self.ctx.numbering.node_id(),
            node_class=NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
            unit_no=self.ctx.unit_no,
            tag=tag,
            loop_tag=tag,
            measured_variable=tag[0],
        )
        self._instruments.append(spec)
        self._roles[spec.node_id] = role
        self.link(Relation.SEND_SIGNAL_TO, sensor_id, spec.node_id)
        return spec.node_id

    def local_indicator(self, letters: str, location_id: str, role: str) -> str:
        """A gauge: one sensor `PI-12021` that is its own loop (convention I-2)."""
        tag = self.ctx.numbering.instrument_tag(letters)
        return self.sensor(tag, tag, location_id, role)

    def link(self, relation: Relation, source_id: str, target_id: str) -> None:
        """Add one edge between two nodes of the plan."""
        self._links.append(LinkSpec(relation=relation, source_id=source_id, target_id=target_id))

    def finish(
        self, run: tuple[LineItemSpec, ...] = (), **ports: str | LineItemSpec | EquipmentSpec
    ) -> TrimPlan:
        """The plan; a port given as a spec stands for that spec's node id."""
        return self.finish_with_ports(ports, run)

    def finish_with_ports(
        self,
        ports: Mapping[str, str | LineItemSpec | EquipmentSpec],
        run: tuple[LineItemSpec, ...] = (),
    ) -> TrimPlan:
        """As `finish`, for ports collected in a dict (`finish(**dict)` could clash with `run`)."""
        return TrimPlan(
            run=run,
            equipment=tuple(self._equipment),
            lines=tuple(self._lines),
            instruments=tuple(self._instruments),
            links=tuple(self._links),
            roles=dict(self._roles),
            stream_kinds=dict(self._stream_kinds),
            ports={name: _node_id_of(value) for name, value in ports.items()},
        )


def _node_id_of(value: str | LineItemSpec | EquipmentSpec) -> str:
    return value if isinstance(value, str) else value.node_id
