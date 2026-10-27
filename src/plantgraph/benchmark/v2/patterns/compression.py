"""U2, the compressor stage (design realism 7.2; pid-vocabulary 5.1, 5.2, 13.3).

A **compressor** raises a gas's pressure. The gas first passes a **knock-out drum** (a vessel that
drops out liquid droplets, which would damage the machine), then, optionally, a filter, the
compressor, an **aftercooler** (compression heats the gas) and optionally a second drum.

Control and protection (textbook practice, not taken from a source: design 7 marks them [U]):
- an **anti-surge loop** `FT -> FIC -> FV` opens a recycle valve from the aftercooler outlet back to
  the inlet, so the compressor never runs far below its design flow (the recycle stream);
- the suction pressure `PIC` moves a valve on the suction line, or, with a variable-speed drive
  (`p_vfd`), the compressor's speed;
- a drum's high-level trip (`LT -> LSHH`) shuts an on-off valve on the suction;
- the drum liquid leaves through a level valve to a drain stub, not through a port, so the
  flowsheet's liquid wiring never takes it.

Variants (decks, `variants.PATTERN_DECKS`): compressor class (centrifugal, reciprocating, rotary:
the screw machine), aftercooler class, suction filter, second drum; the drive from `p_vfd`.
Ports: `gas` in, `compressed` out. The stage is one drawing group.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.patterns.assembly import (
    equipment_plan,
    line_containing,
    quiet,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.column_parts import gas_style
from plantgraph.benchmark.v2.patterns.compression_parts import (
    SCRUBBER,
    anti_surge,
    discharge_line,
    drum_liquid_outlet,
    inlet_line,
    machine_instruments,
    outlet_lines,
    recycle_line,
    suction_lines,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.exchanger import exchanger_code, exchanger_trims, utility_for
from plantgraph.benchmark.v2.patterns.machines import machine_plan
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    PortDirection,
    open_end_port,
)
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.patterns.vessel_parts import level_instruments
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.graph.schema import NodeClass

PATTERN_ID = "U2"
SYSTEM_CODE = "CMP"


class _Choices(BaseModel):
    """What one compressor stage drew from its decks and chances."""

    model_config = ConfigDict(frozen=True)

    compressor: str
    aftercooler: str
    suction_filter: bool
    second_drum: bool
    speed_drive: bool  # a variable-speed drive (VFD) instead of a suction pressure valve

    @property
    def label(self) -> str:
        """The choices as the answer key's variant text."""
        return variant_label(
            compressor=self.compressor,
            aftercooler=self.aftercooler,
            suction_filter=self.suction_filter,
            discharge_ko_drum=self.second_drum,
            drive="vfd" if self.speed_drive else "fixed_speed",
        )


def _draw_choices(ctx: PatternContext) -> _Choices:
    return _Choices(
        compressor=ctx.deal("U2.compressor"),
        aftercooler=ctx.deal("U2.aftercooler"),
        suction_filter=ctx.deal("U2.suction_filter") == "present",
        second_drum=ctx.deal("U2.discharge_ko_drum") == "present",
        speed_drive=ctx.chance(ctx.density.p_vfd),
    )


def build_compressor_stage(ctx: PatternContext) -> PatternInstance:
    """Drum, [filter], compressor, aftercooler, [drum]; ports `gas` (in) and `compressed` (out)."""
    choices = _draw_choices(ctx)
    style = gas_style(ctx)
    drum_eq = equipment_plan(ctx, SCRUBBER, "V", "suction_ko_drum")
    machine_eq = machine_plan(ctx, choices.compressor, "compressor", has_motor=True)
    cooler_eq = equipment_plan(
        ctx, choices.aftercooler, exchanger_code(choices.aftercooler), "aftercooler"
    )
    filter_eq = _optional_equipment(
        ctx, choices.suction_filter, NodeClass.GAS_FILTER, "F", "suction_filter"
    )
    second_eq = _optional_equipment(
        ctx, choices.second_drum, NodeClass.SCRUBBING_SEPARATOR, "V", "discharge_ko_drum"
    )
    equipment = [drum_eq, machine_eq, cooler_eq, *filter_eq, *second_eq]
    ids = [plan.ports["equipment"] for plan in equipment]
    drum, machine, cooler = ids[:3]
    filter_id = filter_eq[0].ports["equipment"] if filter_eq else None
    second_id = second_eq[0].ports["equipment"] if second_eq else None

    inlet, return_tee = inlet_line(ctx, style, drum)
    element, recycle_valve = anti_surge(ctx, style)
    suction = suction_lines(ctx, style, drum, filter_id, machine, element, choices.speed_drive)
    discharge = discharge_line(ctx, style, machine, cooler)
    outlet = outlet_lines(ctx, style, cooler, second_id)
    recycle = recycle_line(ctx, style, recycle_valve, outlet.takeoff_tee, return_tee)
    drums = [drum, *([second_id] if second_id else [])]
    parts = [
        *(quiet(plan) for plan in equipment),
        inlet,
        suction,
        discharge,
        outlet.plan,
        recycle,
        *(drum_liquid_outlet(ctx, drum_id) for drum_id in drums),
        *(level_instruments(ctx, drum_id) for drum_id in drums),
        machine_instruments(ctx, style, machine, drum, choices.speed_drive),
        _cooler_trims(ctx, cooler, choices.aftercooler),
    ]
    plan = with_stream_kinds(combine(*(quiet(part) for part in parts)))
    groups = DrawingGroups()
    groups.put(ids, "G1")
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=choices.label,
        plan=plan,
        ports=(
            open_end_port("gas", PortDirection.IN, Phase.GAS, line_containing(plan, return_tee)),
            open_end_port(
                "compressed",
                PortDirection.OUT,
                Phase.GAS,
                line_containing(plan, outlet.last_tee),
            ),
        ),
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _optional_equipment(
    ctx: PatternContext, present: bool, node_class: NodeClass, type_code: str, role: str
) -> list[TrimPlan]:
    """One equipment plan when `present`, else none."""
    if not present:
        return []
    return [equipment_plan(ctx, node_class.value, type_code, role)]


def _cooler_trims(ctx: PatternContext, cooler_id: str, cooler_class: str) -> TrimPlan:
    """Cooling-water stubs (none for an air cooler), vent and drain, monitoring points."""
    service = utility_for(cooler_class, steam=False)
    return exchanger_trims(ctx, cooler_id, cooler_class, service).plan
