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

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.flowsheet import SLOT_TITLES, OpenOut, UnitSlot, draw_flowsheet, wire
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.registry import available_patterns, build_pattern
from plantgraph.benchmark.v2.patterns.variants import all_deck_variants
from plantgraph.benchmark.v2.plan_models import PlantBuilderV2, TrainRecord, draw_train_records
from plantgraph.benchmark.v2.sheets import UnitSheets, assign_unit_sheets
from plantgraph.benchmark.v2.streams import unit_rng
from plantgraph.benchmark.v2.trim_context import LineStyle

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
    units: list[PlannedUnit] = []
    open_outs: tuple[OpenOut, ...] = ()
    for slot in slots:
        built = _build_unit(config, slot, trains, decks)
        wired, open_outs = wire(built, slot.unit_no, open_outs)
        sheets = assign_unit_sheets(slot.unit_no, wired, config.sheets)
        units.append(PlannedUnit(slot=slot, instance=wired, sheets=sheets))
    return PlantPlanV2(
        config=config, trains=trains, units=tuple(units), open_stub_count=len(open_outs)
    )


def _build_unit(
    config: GeneratorConfigV2,
    slot: UnitSlot,
    trains: tuple[TrainRecord, ...],
    decks: VariantDecks,
) -> PatternInstance:
    conventions = trains[slot.train_no - 1].conventions
    ctx = PatternContext.from_config(
        config,
        slot.unit_no,
        unit_rng(config.seed, slot.unit_no),
        conventions,
        decks,
        MAIN_LINE_STYLE,
    )
    return build_pattern(slot.pattern_id, ctx)
