"""The v2 planner: from a config to a whole plant plan, with no pyDEXPI and no database.

`plan_plant` draws the flowsheet (`flowsheet.py`), builds each unit's pattern from the unit's own
random stream, joins the units through their ports and assigns every node a sheet (`sheets.py`).
The result is a `PlantPlanV2` that any `PlantBuilderV2` backend can write.

Prefix stability (design 8.2): unit *u* reads only its own stream, the shared variant decks in unit
order, and the open out-ports of the units before it, so the first *n* units of a larger plant are
identical to the *n*-unit plant.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.boundary import close_plant_boundary
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.deck import VariantDecks
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
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.registry import available_patterns, build_pattern
from plantgraph.benchmark.v2.patterns.variants import all_deck_variants
from plantgraph.benchmark.v2.plan_models import PlantBuilderV2, TrainRecord, draw_train_records
from plantgraph.benchmark.v2.sheets import UnitSheets, assign_unit_sheets
from plantgraph.benchmark.v2.streams import unit_rng
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.valve_positions import with_valve_positions

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

    def write(self, builder: PlantBuilderV2) -> None:
        """Add every unit, in unit order, so a joined line finds its source already written."""
        for unit in self.units:
            builder.add_section(unit.slot.unit_no, unit.title)
            unit.instance.plan.write(builder)

    @property
    def sheet_count(self) -> int:
        """The number of sheets the plant is drawn on."""
        return sum(unit.sheets.sheet_count for unit in self.units)


def plan_plant(config: GeneratorConfigV2) -> PlantPlanV2:
    """Plan a plant of `config.n_units` units; same config, same plan."""
    slots = draw_flowsheet(config.seed, config.n_units, config.flowsheet, available_patterns())
    trains = draw_train_records(config.seed, slots[-1].train_no)
    decks = VariantDecks(config.seed, all_deck_variants(config.patterns, config.trims))
    open_outs: tuple[OpenOut, ...] = ()
    instances: list[PatternInstance] = []
    trims: list[TrimContext] = []
    for position, slot in enumerate(slots):
        built, trim = _build_unit(config, slot, trains, decks, open_outs)
        wired, open_outs = wire(built, slot.unit_no, open_outs, slot.train_no)
        if _closes_core_loop(config, slot, slots[position - 1] if position else None):
            wired, open_outs = close_recycle_loop(instances[-1], wired, slot.unit_no, open_outs)
        instances.append(wired)
        trims.append(trim)
    if _is_handbook(config):
        # the joins are final only now, so this is the first moment a plant-boundary end is known
        instances = close_plant_boundary(instances, trims, MAIN_LINE_STYLE)
        # last, so the battery-limit and make-up valves the boundary pass added are positioned too
        instances = _with_valve_positions(config, instances)
    units = [
        PlannedUnit(
            slot=slot,
            instance=instance,
            sheets=assign_unit_sheets(slot.unit_no, instance, config.sheets),
        )
        for slot, instance in zip(slots, instances, strict=True)
    ]
    return PlantPlanV2(
        config=config, trains=trains, units=tuple(units), open_stub_count=len(open_outs)
    )


def _is_handbook(config: GeneratorConfigV2) -> bool:
    """True for a v2.2 plant with the handbook rules on; v2.1 and knobs-off plants are pinned."""
    return isinstance(config, GeneratorConfigV22) and config.handbook.enabled


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
        train_no=slot.train_no,
    )
    return build_pattern(slot.pattern_id, ctx), ctx.trim
