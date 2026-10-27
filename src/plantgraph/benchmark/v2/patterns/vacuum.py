"""The vacuum system of a distillation column (design pid-vocabulary 5.2, U1 vacuum variant).

A column run under vacuum draws the uncondensed vapour off the reflux drum with a **vacuum device**
instead of venting it. Two devices are drawn:

- **air ejector** (`air_ejector`): a jet pump with no moving parts. Motive steam rushing through a
  nozzle drags the vapour along. Two stages in series with an inter-condenser between them (it
  condenses the steam of the first stage so the second stage has less to move); each stage is an
  installed pair A/B so one can run while the other is serviced. The exhaust passes a silencer
  and ends open to the atmosphere.
- **liquid-ring pump** (`liquid_ring`): a rotary machine (class `RotaryCompressor`) with a motor.

Both take over the drum's vapour line from the pressure control valve onward, so the caller passes
the plan of that line (top tee, valve, loop) with its `run` still open and gets the plan back with
the line closed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.instruments import machine_monitor
from plantgraph.benchmark.v2.instruments_extra import machine_start_stop, monitor_points
from plantgraph.benchmark.v2.patterns.assembly import (
    block_valve_plan,
    close_run,
    equipment_plan,
    part_plan,
    quiet,
    run_of,
    spare_set_plan,
    spared_set,
    tee_plan,
    thermometer_tap,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.exchanger import COOLING_WATER, exchanger_trims
from plantgraph.benchmark.v2.plan_models import EquipmentSpec
from plantgraph.benchmark.v2.trim_context import LineStyle
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims import compressor_discharge, compressor_suction
from plantgraph.benchmark.v2.trims_utility import steam_stub_relief, utility_supply_stub
from plantgraph.graph.schema import NodeClass

MOTIVE_STEAM = "MPS"  # medium-pressure steam: the motive jet needs a higher pressure than heating
VACUUM_KINDS = ("air_ejector", "liquid_ring")


class Vacuum(BaseModel):
    """A built vacuum system: its plan (the vapour line closed) and the equipment it added."""

    model_config = ConfigDict(frozen=True)

    plan: TrimPlan
    equipment_ids: tuple[str, ...]


def build_vacuum(
    ctx: PatternContext, kind: str, source_id: str, vapour: TrimPlan, style: LineStyle
) -> Vacuum:
    """The vacuum system `kind`, drawing from `source_id` along the open run of `vapour`."""
    if kind == "air_ejector":
        return _air_ejector_system(ctx, source_id, vapour, style)
    if kind == "liquid_ring":
        return _liquid_ring_system(ctx, source_id, vapour, style)
    raise ValueError(f"expected a vacuum kind in {list(VACUUM_KINDS)}, got {kind!r}")


# ---- liquid-ring pump ----------------------------------------------------------------------------


def _liquid_ring_system(
    ctx: PatternContext, source_id: str, vapour: TrimPlan, style: LineStyle
) -> Vacuum:
    """`vapour -> suction block, strainer -> pump -> check, block -> open end` (as a compressor)."""
    (pump,) = spared_set(ctx, NodeClass.ROTARY_COMPRESSOR.value, "K", 1, has_motor=True)
    machine = TrimPlan(equipment=(pump,), roles={pump.node_id: "liquid_ring_pump"})
    suction = close_run(
        ctx,
        combine(vapour, quiet(compressor_suction(ctx.trim, style))),
        source_id,
        pump.node_id,
        style=style,
    )
    discharge = close_run(
        ctx, compressor_discharge(ctx.trim, style), pump.node_id, None, style=style
    )
    parts = [machine, suction, discharge, *_pump_instruments(ctx, style, pump.node_id)]
    return Vacuum(plan=combine(*(quiet(part) for part in parts)), equipment_ids=(pump.node_id,))


def _pump_instruments(ctx: PatternContext, style: LineStyle, pump_id: str) -> list[TrimPlan]:
    """Start/stop, the optional bearing thermometer and motor current, and the monitoring points."""
    parts = [machine_start_stop(ctx.trim, style, ctx.instruments, pump_id)]
    if ctx.chance(ctx.density.p_bearing_temperature):
        parts.append(machine_monitor(ctx.trim, style, pump_id, "bearing_temperature"))
    if ctx.chance(ctx.density.p_motor_current):
        parts.append(machine_monitor(ctx.trim, style, pump_id, "motor_current"))
    parts.append(monitor_points(ctx.trim, style, ctx.density, pump_id))
    return parts


# ---- two-stage air ejector -----------------------------------------------------------------------


def _air_ejector_system(
    ctx: PatternContext, source_id: str, vapour: TrimPlan, style: LineStyle
) -> Vacuum:
    """`drum -> stage 1 (A/B) -> inter-condenser -> stage 2 (A/B) -> silencer -> open end`."""
    first = spared_set(ctx, NodeClass.AIR_EJECTOR.value, "EJ", 2)
    second = spared_set(ctx, NodeClass.AIR_EJECTOR.value, "EJ", 2)
    cooler = equipment_plan(ctx, NodeClass.TUBULAR_HEAT_EXCHANGER.value, "E", "intercondenser")
    cooler_id = cooler.ports["equipment"]
    cooler_trims = exchanger_trims(
        ctx, cooler_id, NodeClass.TUBULAR_HEAT_EXCHANGER.value, COOLING_WATER
    )
    outlet_tee = tee_plan(ctx, "intercondenser_outlet_tee")
    stage_one = _ejector_stage(ctx, style, first, source_id, vapour, (), cooler_id)
    silencer = part_plan(ctx, NodeClass.SILENCER.value, "ejector_silencer")
    stage_two = _ejector_stage(ctx, style, second, cooler_id, outlet_tee, (silencer,), None)
    outlet_ti = thermometer_tap(ctx, outlet_tee.ports["tee"], "intercondenser_outlet_ti")
    steam = [_motive_steam(ctx, ejector.node_id) for ejector in (*first, *second)]
    machines = combine(spare_set_plan(first, "air_ejector"), spare_set_plan(second, "air_ejector"))
    parts = [quiet(cooler), machines, stage_one, stage_two, outlet_ti, cooler_trims.plan, *steam]
    ids = (*(e.node_id for e in (*first, *second)), cooler_id)
    return Vacuum(plan=combine(*(quiet(part) for part in parts)), equipment_ids=ids)


def _ejector_stage(
    ctx: PatternContext,
    style: LineStyle,
    pair: list[EquipmentSpec],
    source_id: str,
    head: TrimPlan,
    after_merge: tuple[TrimPlan, ...],
    dst_id: str | None,
) -> TrimPlan:
    """One stage: a split tee, ejector A and B in parallel each between two blocks, a merge tee.

    `head` is the open run that leads to the split tee. The merge tee sits in A's outlet line, so
    that line comes before B's, which ends at it (a line may only end at a tee already written).
    """
    a, b = (ejector.node_id for ejector in pair)
    split, merge = tee_plan(ctx, "ejector_split_tee"), tee_plan(ctx, "ejector_merge_tee")
    to_a = close_run(
        ctx,
        combine(head, run_of(split, _block(ctx, "ejector_inlet_block"))),
        source_id,
        a,
        style=style,
    )
    to_b = close_run(
        ctx, run_of(_block(ctx, "ejector_inlet_block")), split.ports["tee"], b, style=style
    )
    outlet = run_of(_block(ctx, "ejector_outlet_block"), merge, *after_merge)
    from_a = close_run(ctx, outlet, a, dst_id, style=style)
    from_b = close_run(
        ctx, run_of(_block(ctx, "ejector_outlet_block")), b, merge.ports["tee"], style=style
    )
    return combine(to_a, to_b, from_a, from_b)


def _block(ctx: PatternContext, role: str) -> TrimPlan:
    return block_valve_plan(ctx, role)


def _motive_steam(ctx: PatternContext, ejector_id: str) -> TrimPlan:
    """The steam stub of one ejector with an atmospheric relief valve (pid-vocabulary 5.4)."""
    supply = utility_supply_stub(ctx.trim, ctx.style, MOTIVE_STEAM, ejector_id, relief_tee=True)
    relief = steam_stub_relief(ctx.trim, ctx.style, supply.ports["relief_tee"], MOTIVE_STEAM)
    return combine(quiet(supply), quiet(relief))
