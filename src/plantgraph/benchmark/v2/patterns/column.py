"""U1, the distillation column system (design realism 7.2; pid-vocabulary 5.2, 13.3).

A **distillation column** separates a liquid mixture by boiling point. Feed enters mid-height; heat
from a **reboiler** at the bottom drives vapour up the column; at the top a **condenser** turns the
vapour back to liquid, which collects in a **reflux drum**. A **reflux pump** sends part of that
liquid back down the column (the *reflux*, which sharpens the separation) and the rest leaves as
*distillate*. What stays liquid at the bottom leaves as *bottoms* through a second pump set.

Control loops (textbook practice, not taken from a source: design 7 marks them [U]): column
pressure `PIC` moves a valve on the drum's vapour outlet; reflux flow `FIC` its valve; drum level
`LIC` the distillate valve; bottoms level `LIC` the bottoms valve; a tray temperature `TIC` the
reboiler steam. With `p_cascade` the temperature (and the distillate level) controller sets the
set point of a flow controller instead of moving the valve directly.

Variants (one deck each, `variants.PATTERN_DECKS`): vacuum device none / air ejector / liquid-ring
pump (`vacuum.py`), condenser class, feed preheater, reflux sight glass. `p_column_combined` draws
the system on one sheet, else on two (column and reboiler, then condenser and drum); the combined
sheet falls back to two when it would hold more equipment than a sheet may (pid-vocabulary 13.6).
`p_side_draw` adds a tray draw as a further liquid out-port. Ports: `feed`, `distillate`,
[`side_draw`], [`vapour`], `bottoms` last, because the flowsheet grammar feeds the next unit from
the last port of a phase (the bottoms of one column feed the next separation).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.config import SheetKnobs
from plantgraph.benchmark.v2.patterns.assembly import (
    equipment_plan,
    line_containing,
    quiet,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.column_parts import (
    bottoms_set,
    column_instruments,
    drum_instruments,
    feed_lines,
    overhead_lines,
    reboiler_lines,
    reflux_set,
    side_draw_lines,
    vapour_lines,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.exchanger import (
    STEAM,
    ExchangerTrims,
    SteamLoop,
    exchanger_code,
    exchanger_trims,
    utility_for,
)
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    Port,
    PortDirection,
    open_end_port,
)
from plantgraph.benchmark.v2.patterns.pump_set import PumpSet
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.graph.schema import NodeClass

PATTERN_ID = "U1"
SYSTEM_CODE = "DST"
_TUBULAR = NodeClass.TUBULAR_HEAT_EXCHANGER.value


class _Choices(BaseModel):
    """What one column instance drew from its decks and chances."""

    model_config = ConfigDict(frozen=True)

    vacuum: str  # `none`, `air_ejector` or `liquid_ring`
    condenser: str
    preheater: bool
    sight_glass: bool
    combined: bool
    side_draw: bool


def _draw_choices(ctx: PatternContext) -> _Choices:
    return _Choices(
        vacuum=ctx.deal("U1.vacuum"),
        condenser=ctx.deal("U1.condenser"),
        preheater=ctx.deal("U1.feed_preheater") == "present",
        sight_glass=ctx.deal("U1.reflux_sight_glass") == "present",
        combined=ctx.chance(ctx.knobs.p_column_combined),
        side_draw=ctx.chance(ctx.flowsheet.p_side_draw),
    )


class _Heater(BaseModel):
    """One exchanger of the column: its id, its equipment plan and its trims."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    equipment: TrimPlan
    trims: ExchangerTrims

    @property
    def ids(self) -> tuple[str, ...]:
        """The exchanger and its condensate drain pots."""
        return (self.node_id, *self.trims.pot_ids)


_SELF = "self"  # `loop_on` value: the steam loop senses the exchanger's own outlet


def _heater(
    ctx: PatternContext,
    node_class: str,
    role: str,
    service: str | None,
    loop_on: str | None = None,
    cascade: bool = False,
) -> _Heater:
    """An exchanger with its trims; `loop_on` (an equipment id, or `_SELF`) adds the steam loop."""
    equipment = equipment_plan(ctx, node_class, exchanger_code(node_class), role)
    node_id = equipment.ports["equipment"]
    location = node_id if loop_on == _SELF else loop_on
    loop = SteamLoop(location_id=location, cascade=cascade) if location else None
    trims = exchanger_trims(ctx, node_id, node_class, service, loop)
    return _Heater(node_id=node_id, equipment=quiet(equipment), trims=trims)


def build_distillation_column(ctx: PatternContext) -> PatternInstance:
    """Column, reboiler, condenser, drum and two pump sets; see the module docstring for ports."""
    choices = _draw_choices(ctx)
    column_eq = equipment_plan(ctx, NodeClass.PROCESS_COLUMN.value, "T", "column")
    drum_eq = equipment_plan(ctx, NodeClass.PRESSURE_VESSEL.value, "D", "reflux_drum")
    column, drum = column_eq.ports["equipment"], drum_eq.ports["equipment"]
    # the reboiler's steam is set by a tray temperature; the preheater's by its own outlet
    reboiler = _heater(
        ctx, _TUBULAR, "reboiler", STEAM, column, cascade=ctx.chance(ctx.instruments.p_cascade)
    )
    condenser = _heater(
        ctx, choices.condenser, "condenser", utility_for(choices.condenser, steam=False)
    )
    preheater = (
        _heater(ctx, _TUBULAR, "feed_preheater", STEAM, loop_on=_SELF)
        if choices.preheater
        else None
    )
    pre_id = preheater.node_id if preheater else None

    feed, feed_tee = feed_lines(ctx, column, pre_id)
    overhead = overhead_lines(ctx, column, condenser.node_id, drum)
    vapour = vapour_lines(ctx, choices.vacuum, column, drum)
    reflux, reflux_branches = reflux_set(ctx, drum, column, choices.sight_glass)
    bottoms = bottoms_set(ctx, column)
    side, side_flow = side_draw_lines(ctx, column) if choices.side_draw else (None, "")

    parts = [
        quiet(column_eq),
        quiet(drum_eq),
        reboiler.equipment,
        condenser.equipment,
        *([preheater.equipment] if preheater else []),
        feed,
        overhead,
        vapour.plan,
        reboiler_lines(ctx, column, reboiler.node_id),
        quiet(reflux.plan),
        reflux_branches,
        quiet(bottoms.plan),
        *([side] if side is not None else []),
        column_instruments(ctx, column),
        drum_instruments(ctx, drum),
        reboiler.trims.plan,
        condenser.trims.plan,
        *([preheater.trims.plan] if preheater else []),
    ]
    plan = with_stream_kinds(combine(*(quiet(part) for part in parts)))
    column_side = [*reboiler.ids, *(preheater.ids if preheater else ())]
    overhead_side = [*condenser.ids, *vapour.equipment_ids]
    groups, layout = _drawing_groups(
        [column, *column_side], [drum, *overhead_side], reflux, bottoms, choices.combined
    )
    ports = _ports(plan, choices, feed_tee, vapour.valve_body_id, reflux, bottoms, side_flow)
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=_label(choices, layout, reflux, bottoms),
        plan=plan,
        ports=ports,
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _ports(
    plan: TrimPlan,
    choices: _Choices,
    feed_tee: str,
    pressure_valve: str,
    reflux: PumpSet,
    bottoms: PumpSet,
    side_flow: str,
) -> tuple[Port, ...]:
    """In declaration order: feed, distillate, [side draw], [vapour], bottoms (last)."""
    ports = [
        open_end_port("feed", PortDirection.IN, Phase.LIQUID, line_containing(plan, feed_tee)),
        reflux.discharge.model_copy(update={"name": "distillate"}),
    ]
    if choices.side_draw:
        line = line_containing(plan, side_flow)
        ports.append(open_end_port("side_draw", PortDirection.OUT, Phase.LIQUID, line))
    if choices.vacuum == "none":  # with a vacuum device the vapour ends in the silencer, no port
        line = line_containing(plan, pressure_valve)
        ports.append(open_end_port("vapour", PortDirection.OUT, Phase.GAS, line))
    ports.append(bottoms.discharge.model_copy(update={"name": "bottoms"}))
    return tuple(ports)


def _drawing_groups(
    column_side: list[str],
    overhead_side: list[str],
    reflux: PumpSet,
    bottoms: PumpSet,
    combined: bool,
) -> tuple[DrawingGroups, str]:
    """G1 column side, G2 overhead side (one group when combined); own-sheet pump sets pinned after.

    Returns the groups and the layout drawn: `combined`, or `two_sheets` (also the fallback when a
    combined sheet would hold more equipment than the sheet cap, pid-vocabulary 13.6 rule 2).
    """
    column_ids = [*column_side, *([] if bottoms.own_sheet else bottoms.pump_ids)]
    overhead_ids = [*overhead_side, *([] if reflux.own_sheet else reflux.pump_ids)]
    groups = DrawingGroups()
    fits = len(column_ids) + len(overhead_ids) <= SheetKnobs().max_equipment_per_sheet
    layout = "combined" if combined and fits else "two_sheets"
    if layout == "combined":
        groups.put([*column_ids, *overhead_ids], "G1")
        next_group = 2
    else:
        groups.put(column_ids, "G1")
        groups.put(overhead_ids, "G2")
        next_group = 3
    for pumps in (reflux, bottoms):
        if pumps.own_sheet:
            groups.put(pumps.pump_ids, f"G{next_group}", pinned=True)
            next_group += 1
    return groups, layout


def _label(choices: _Choices, layout: str, reflux: PumpSet, bottoms: PumpSet) -> str:
    """The choices as the answer key's variant text."""
    base = variant_label(
        vacuum=choices.vacuum,
        condenser=choices.condenser,
        preheater=choices.preheater,
        sight_glass=choices.sight_glass,
        layout=layout,
        side_draw=choices.side_draw,
    )
    return f"{base}|reflux[{reflux.variant}]|bottoms[{bottoms.variant}]"
