"""U8, blending (design realism 7.2; pid-vocabulary 5.1, 5.2, 13.3).

**Blending** mixes a main liquid with a small, accurately metered stream of an additive. The main
stream arrives on one line, the additive from a day tank through **dosing pumps** (reciprocating
pumps, an installed pair), and both meet in a mixer. The product may then collect in an agitated
vessel before it leaves.

Control (textbook practice, not taken from a source: design 7 marks it [U]): a **ratio controller**
`FFIC` compares the main flow with the additive flow and moves the additive valve; with `p_vfd`
the dosing pumps' variable-speed drives take the valve's place. An optional analyser on the blend
is drawn as an indicator only: a cascade master over a two-sensor controller would break the
cascade invariant (S22). A vessel level `LIC` moves the outlet valve.

Variants (decks, `variants.PATTERN_DECKS`): the mixer is a static mixer (inline vanes), a rotary
mixer (driven by a motor through a gear box) or an **eductor** (`EjectorPump`: the main liquid is
the motive jet that sucks the additive in); an agitated vessel after the mixer; an in-line mixer
on the additive injection. Ports: `main`, `additive` (in), `blend` (out).
Drawing groups: G1 mixer, day tank and pumps; G2 vessel and agitator.
"""

from __future__ import annotations

import dataclasses

from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.instruments import control_loop
from plantgraph.benchmark.v2.patterns.assembly import (
    close_run,
    equipment_plan,
    line_between,
    line_containing,
    quiet,
    run_of,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.blending_parts import (
    ADDITIVE_METER,
    MAIN_METER,
    additive_fill_line,
    blend_line,
    dosing_header,
    dosing_speed_loops,
    flow_meter,
    join_pumps_to_mixer,
    main_line,
)
from plantgraph.benchmark.v2.patterns.column_parts import gas_style
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.machines import agitator_plan, machine_plan, motor_drive
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    PortDirection,
    open_end_port,
)
from plantgraph.benchmark.v2.patterns.pump_set import PumpSet, build_pump_set
from plantgraph.benchmark.v2.patterns.storage_parts import tank_fittings
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.patterns.vessel_parts import level_instruments
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims_valves import battery_limit, control_valve
from plantgraph.benchmark.v2.trims_vessel import vessel_trims
from plantgraph.graph.schema import NodeClass

PATTERN_ID = "U8"
SYSTEM_CODE = "BLD"
_ROTARY_MIXER = NodeClass.ROTARY_MIXER.value
_VESSEL = NodeClass.PRESSURE_VESSEL.value


def build_blending(ctx: PatternContext) -> PatternInstance:
    """Mixer, day tank, dosing pumps and an optional agitated vessel; see the module docstring."""
    mixer_class = ctx.deal("U8.mixer")
    with_vessel = ctx.deal("U8.agitated_vessel") == "present"
    injection = ctx.deal("U8.additive_injection")
    speed_drive = ctx.chance(ctx.density.p_vfd)
    analyser = ctx.chance(ctx.density.p_optional_instrument)
    dosing = dataclasses.replace(ctx, style=ctx.style.branch())  # the additive lines are smaller

    mixer_eq = machine_plan(ctx, mixer_class, "mixer", has_motor=mixer_class == _ROTARY_MIXER)
    tank_eq = equipment_plan(dosing, NodeClass.TANK.value, "TK", "additive_tank")
    vessel_eq = equipment_plan(ctx, _VESSEL, "V", "blend_vessel") if with_vessel else None
    mixer, tank = mixer_eq.ports["equipment"], tank_eq.ports["equipment"]
    vessel = vessel_eq.ports["equipment"] if vessel_eq else None
    agitator = agitator_plan(ctx, vessel) if vessel else None

    main_meter = flow_meter(ctx, MAIN_METER, "main_flow_meter")
    wild_id = main_meter.ports["element"]
    additive_meter = flow_meter(dosing, ADDITIVE_METER, "additive_flow_meter")
    header = dosing_header(dosing, wild_id, additive_meter, injection, speed_drive)
    pumps = build_pump_set(dosing, tank, "ReciprocatingPump", "dosing_pump", header=header)
    blend, blend_tee = blend_line(ctx, mixer, vessel, analyser)
    outlet, outlet_valve = _vessel_lines(ctx, vessel) if vessel else (None, blend_tee)
    parts = [
        quiet(mixer_eq),
        quiet(tank_eq),
        *([quiet(vessel_eq)] if vessel_eq else []),
        *([quiet(agitator)] if agitator else []),
        main_line(ctx, main_meter, mixer),
        additive_fill_line(dosing, tank),
        join_pumps_to_mixer(pumps, mixer),
        blend,
        *_speed_loops(dosing, speed_drive, wild_id, additive_meter, pumps),
        tank_fittings(dosing, tank, flammable=False, viscous=False),
        *([motor_drive(ctx, mixer)] if mixer_class == _ROTARY_MIXER else []),
        *([outlet, level_instruments(ctx, vessel)] if outlet and vessel else []),
        *([motor_drive(ctx, agitator.ports["equipment"])] if agitator else []),
    ]
    plan = with_stream_kinds(combine(*(quiet(part) for part in parts)))
    groups = _drawing_groups([mixer, tank], [vessel] if vessel else [], agitator, pumps)
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=_label(mixer_class, with_vessel, injection, speed_drive, pumps),
        plan=plan,
        ports=(
            open_end_port("main", PortDirection.IN, Phase.LIQUID, line_between(plan, None, mixer)),
            open_end_port(
                "additive", PortDirection.IN, Phase.LIQUID, line_between(plan, None, tank)
            ),
            open_end_port(
                "blend", PortDirection.OUT, Phase.LIQUID, line_containing(plan, outlet_valve)
            ),
        ),
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _speed_loops(
    ctx: PatternContext, speed_drive: bool, wild_id: str, meter: TrimPlan, pumps: PumpSet
) -> list[TrimPlan]:
    if not speed_drive:
        return []
    return [dosing_speed_loops(ctx, wild_id, meter, pumps.pump_ids)]


def _vessel_lines(ctx: PatternContext, vessel_id: str) -> tuple[TrimPlan, str]:
    """The vessel's vent (trims on its top tee, ending open) and its level-controlled outlet.

    Returns the plan and the id of the outlet valve (the out-port's line holds it).
    """
    style = gas_style(ctx)
    top = vessel_trims(ctx.trim, style, vessel_id, _VESSEL)
    vent = close_run(ctx, run_of(top), vessel_id, None, StreamKindV2.TRIM, style)
    valve = control_valve(ctx.trim, ctx.style, "L")
    body = part_of(valve, "body")
    loop = control_loop(ctx.trim, ctx.style, body, vessel_id)
    outlet = run_of(valve, loop, battery_limit(ctx.trim, ctx.style))
    return combine(vent, close_run(ctx, outlet, vessel_id, None)), body.node_id


def _drawing_groups(
    first: list[str], second: list[str], agitator: TrimPlan | None, pumps: PumpSet
) -> DrawingGroups:
    """G1 mixer, tank and pumps; G2 the vessel with its agitator; own-sheet pumps pinned last."""
    groups = DrawingGroups()
    groups.put([*first, *([] if pumps.own_sheet else pumps.pump_ids)], "G1")
    if second and agitator is not None:
        groups.put([*second, agitator.ports["equipment"]], "G2")
    if pumps.own_sheet:
        groups.put(pumps.pump_ids, "G3" if second else "G2", pinned=True)
    return groups


def _label(
    mixer_class: str, with_vessel: bool, injection: str, speed_drive: bool, pumps: PumpSet
) -> str:
    base = variant_label(
        mixer=mixer_class,
        agitated_vessel=with_vessel,
        injection=injection,
        dosing="vfd" if speed_drive else "ratio_valve",
    )
    return f"{base}|{pumps.variant}"
