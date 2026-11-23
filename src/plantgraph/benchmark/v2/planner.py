"""The v2 planner: from a config to a whole plant plan, with no pyDEXPI and no database.

`plan_plant` draws the flowsheet (`flowsheet.py`), builds each unit's pattern from the unit's own
random stream, joins the units through their ports and assigns every node a sheet (`sheets.py`).
The result is a `PlantPlanV2` that any `PlantBuilderV2` backend can write.

Prefix stability (design 8.2): unit *u* reads only its own stream, the shared variant decks in unit
order, and the open out-ports of the units before it, so the first *n* units of a larger plant are
identical to the *n*-unit plant.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.v2.boundary import close_plant_boundary
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.documents import (
    DocumentRecord,
    document_of_train,
    draw_documents,
    trains_with_document_conventions,
)
from plantgraph.benchmark.v2.flowsheet import (
    SLOT_TITLES,
    OpenOut,
    Slot,
    UnitSlot,
    close_recycle_loop,
    closes_recycle_loop,
    draw_flowsheet,
    waiting_streams,
    wire,
)
from plantgraph.benchmark.v2.network_models import NetworkUnit
from plantgraph.benchmark.v2.networks import add_networks
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.registry import available_patterns, build_pattern
from plantgraph.benchmark.v2.patterns.variants import all_deck_variants
from plantgraph.benchmark.v2.plan_models import PlantBuilderV2, TrainRecord, draw_train_records
from plantgraph.benchmark.v2.protection import add_protection
from plantgraph.benchmark.v2.sheets import UnitSheets, assign_unit_sheets
from plantgraph.benchmark.v2.streams import unit_rng
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.valve_positions import with_plan_positions, with_valve_positions

#: the nominal size (inches) of every unit's main process lines; the trims derive smaller branches
MAIN_LINE_STYLE = LineStyle(size=6)


class PlannedUnit(BaseModel):
    """One process unit: its place in the flowsheet, its (wired) pattern and its sheets."""

    model_config = ConfigDict(frozen=True)

    slot: UnitSlot
    instance: PatternInstance
    sheets: UnitSheets

    @property
    def title(self) -> str:
        """The drawing title, `FIL Feed conditioning`."""
        return f"{self.instance.system_code} {SLOT_TITLES[self.slot.slot]}"


class PlantPlanV2(BaseModel):
    """Everything the planner decided; `write` hands it to a backend."""

    model_config = ConfigDict(frozen=True)

    config: GeneratorConfigV2
    trains: tuple[TrainRecord, ...]
    units: tuple[PlannedUnit, ...]
    open_stub_count: int  # out-ports no later unit took: they leave the drawing
    #: v2.2 only: the network header units and interarea units, written after every process unit.
    #: Left out of dumps so a v2.1 plan digest stays byte-identical (design 9)
    network_units: tuple[NetworkUnit, ...] = Field(default=(), exclude=True)
    #: v2.2 only: the conventions of each document; left out of dumps for the same reason
    documents: tuple[DocumentRecord, ...] = Field(default=(), exclude=True)

    def write(self, builder: PlantBuilderV2) -> None:
        """Add every unit, in unit order, so a joined line finds its source already written."""
        for unit in self.units:
            builder.add_section(unit.slot.unit_no, unit.title)
            unit.instance.plan.write(builder)
        for network in self.network_units:  # their lines name parts of the process units
            builder.add_section(network.unit_no, network.title)
            network.plan.write(builder)

    @property
    def sheet_count(self) -> int:
        """The number of sheets the plant is drawn on: process, network and interarea sheets."""
        return self.process_sheet_count + sum(n.sheets.sheet_count for n in self.network_units)

    @property
    def process_sheet_count(self) -> int:
        """The sheets of the process units alone."""
        return sum(unit.sheets.sheet_count for unit in self.units)

    @property
    def unit_plans(self) -> tuple[TrimPlan, ...]:
        """The plan of every unit, process units first, then network and interarea units."""
        return (
            *(unit.instance.plan for unit in self.units),
            *(network.plan for network in self.network_units),
        )

    @property
    def sheet_of(self) -> dict[str, str]:
        """Every drawn node and the sheet (`3:1`) it is on, over all units."""
        sheets = {
            node: sheet for unit in self.units for node, sheet in unit.sheets.sheet_of.items()
        }
        for network in self.network_units:
            sheets.update(network.sheets.sheet_of)
        return sheets


def plan_plant(config: GeneratorConfigV2) -> PlantPlanV2:
    """Plan a plant of `config.n_units` units; same config, same plan."""
    slots = draw_flowsheet(config.seed, config.n_units, config.flowsheet, available_patterns())
    # the v2.1 per-train draws are always taken; a v2.2 plant then ignores their values (design 5)
    trains = draw_train_records(config.seed, slots[-1].train_no)
    documents = _draw_documents(config, slots[-1].train_no)
    if documents:
        trains = trains_with_document_conventions(trains, documents, _per_document(config))
    decks = VariantDecks(config.seed, all_deck_variants(config.patterns, config.trims))
    open_outs: tuple[OpenOut, ...] = ()
    instances: list[PatternInstance] = []
    trims: list[TrimContext] = []
    for position, slot in enumerate(slots):
        built, trim = _build_unit(config, slot, trains, documents, decks, open_outs)
        wired, open_outs = wire(built, slot.unit_no, open_outs, slot.train_no)
        if _closes_core_loop(config, slot, slots[position - 1] if position else None):
            wired, open_outs = close_recycle_loop(instances[-1], wired, slot.unit_no, open_outs)
        instances.append(wired)
        trims.append(trim)
    network_units: list[NetworkUnit] = []
    if _is_handbook(config):
        # the joins are final only now, so this is the first moment a plant-boundary end is known
        instances = close_plant_boundary(instances, trims, MAIN_LINE_STYLE)
        # before the networks: a new relief valve ends open on a flare line the ties must pick up
        instances = add_protection(instances, trims, MAIN_LINE_STYLE)
        instances, network_units = _with_networks(
            config, slots, instances, trims, trains, documents, decks
        )
        # last, so the battery-limit and make-up valves the boundary pass added are positioned too
        instances = _with_valve_positions(config, instances)
        network_units = _with_unit_positions(config, network_units)
    units = [
        PlannedUnit(
            slot=slot,
            instance=instance,
            sheets=assign_unit_sheets(slot.unit_no, instance, config.sheets),
        )
        for slot, instance in zip(slots, instances, strict=True)
    ]
    return PlantPlanV2(
        config=config,
        trains=trains,
        units=tuple(units),
        open_stub_count=len(open_outs),
        network_units=tuple(network_units),
        documents=documents,
    )


def _is_handbook(config: GeneratorConfigV2) -> bool:
    """True for a v2.2 plant with the handbook rules on; v2.1 and knobs-off plants are pinned."""
    return isinstance(config, GeneratorConfigV22) and config.handbook.enabled


def _draw_documents(config: GeneratorConfigV2, n_trains: int) -> tuple[DocumentRecord, ...]:
    """The documents of a v2.2 plant with the handbook on; none for v2.1 and knobs-off plants."""
    if not isinstance(config, GeneratorConfigV22) or not config.handbook.enabled:
        return ()
    return draw_documents(config, n_trains)


def _per_document(config: GeneratorConfigV2) -> int:
    if not isinstance(config, GeneratorConfigV22):  # unreachable: only v2.2 has documents
        raise ValueError(f"expected a v2.2 config for documents, got {type(config).__name__}")
    return config.handbook.trains_per_document


def _with_networks(
    config: GeneratorConfigV2,
    slots: Sequence[UnitSlot],
    instances: list[PatternInstance],
    trims: list[TrimContext],
    trains: tuple[TrainRecord, ...],
    documents: tuple[DocumentRecord, ...],
    decks: VariantDecks,
) -> tuple[list[PatternInstance], list[NetworkUnit]]:
    if not isinstance(config, GeneratorConfigV22):  # unreachable: only handbook plants call this
        raise ValueError(f"expected a v2.2 config for networks, got {type(config).__name__}")
    return add_networks(config, slots, instances, trims, trains, documents, decks)


def _with_unit_positions(config: GeneratorConfigV2, units: list[NetworkUnit]) -> list[NetworkUnit]:
    if not isinstance(config, GeneratorConfigV22):  # unreachable: only handbook plants call this
        raise ValueError(f"expected a v2.2 config for valve positions, got {type(config).__name__}")
    return [
        unit.model_copy(update={"plan": with_plan_positions(unit.plan, config.handbook)})
        for unit in units
    ]


def _with_valve_positions(
    config: GeneratorConfigV2, instances: list[PatternInstance]
) -> list[PatternInstance]:
    if not isinstance(config, GeneratorConfigV22):  # unreachable: only handbook plants call this
        raise ValueError(f"expected a v2.2 config for valve positions, got {type(config).__name__}")
    return [with_valve_positions(instance, config.handbook) for instance in instances]


def _closes_core_loop(config: GeneratorConfigV2, slot: UnitSlot, previous: UnitSlot | None) -> bool:
    """v2.2 with the handbook on only: v2.1 keeps its open recycle ports (goldens are pinned)."""
    return _is_handbook(config) and closes_recycle_loop(slot, previous)


def _build_unit(
    config: GeneratorConfigV2,
    slot: UnitSlot,
    trains: tuple[TrainRecord, ...],
    documents: tuple[DocumentRecord, ...],
    decks: VariantDecks,
    open_outs: tuple[OpenOut, ...],
) -> tuple[PatternInstance, TrimContext]:
    """The unit's pattern and the trim context it was built with (the boundary pass reuses it)."""
    conventions = trains[slot.train_no - 1].conventions
    # only a product farm reads this: it needs a receipt line for every stream waiting for a tank
    waiting = waiting_streams(open_outs, slot.train_no) if slot.slot is Slot.PRODUCT_FARM else 0
    ctx = PatternContext.from_config(
        config,
        slot.unit_no,
        unit_rng(config.seed, slot.unit_no),
        conventions,
        decks,
        MAIN_LINE_STYLE,
        waiting_streams=waiting,
        document=_document_of(config, documents, slot.train_no),
    )
    return build_pattern(slot.pattern_id, ctx), ctx.trim


def _document_of(
    config: GeneratorConfigV2, documents: tuple[DocumentRecord, ...], train_no: int
) -> DocumentRecord | None:
    """The document a train belongs to; None on a plant without documents (v2.1)."""
    if not documents:
        return None
    return documents[document_of_train(train_no, _per_document(config)) - 1]
