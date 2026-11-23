"""The safety valves API 14C and Toghraei ask for beyond what the patterns draw (design 17.13 R8).

Three additions, in the priority order the valve band allows (the pass withdraws the last first if
the pooled valves per sheet pass the stop):

1. TOG236: an **emergency vent** on every hydrocarbon atmospheric tank, a pressure safety valve
   (PSV) that opens to the air if the normal breather cannot pass the vapour (Toghraei p.236);
2. SAC A-8.2 e: a PSV on each compressor suction tee, to the flare;
3. SAC A-6.2 l: a PSV on the heater outlet tee of a furnace whose tubes no other PSV protects.

A PSV takes no block valves here (API wants it unisolable), so each addition is one valve. Nothing
is drawn from a random stream: every addition follows from the structure.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.v2.hidden_state import FluidClass
from plantgraph.benchmark.v2.protection_scope import a4_vessels, compressors, furnaces, tanks
from plantgraph.benchmark.v2.protection_switches import (
    HEATER_OUTLET_TEE_ROLE,
    SUCTION_TEE_ROLE,
    tee_of_unit,
)
from plantgraph.benchmark.v2.sac_structure import (
    Facts,
    reaches_safety_valve,
    valve_free_equipment,
)
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.graph.schema import NodeClass

EMERGENCY_VENT_ROLE = "tank_emergency_vent"
EMERGENCY_VENT_END_ROLE = "tank_emergency_vent_end"
SUCTION_PSV_ROLE = "compressor_suction_psv"
TUBE_PSV_ROLE = "heater_tube_psv"
_PSV = NodeClass.SPRING_LOADED_GLOBE_SAFETY_VALVE.value
_FLARE = "FL"

#: the three additions in R8's priority order; the last one is withdrawn first
PRIORITY: tuple[str, ...] = (EMERGENCY_VENT_ROLE, SUCTION_PSV_ROLE, TUBE_PSV_ROLE)


def tube_protected_by_other_psv(facts: Facts, furnace: str) -> bool:
    """SAC A-6.2 l.3: a valve-free route from the furnace leads to a vessel with its own PSV.

    The skillet blind counts as an isolating part, so a furnace drawn with one is not covered.
    """
    reached = valve_free_equipment(facts, furnace) & set(a4_vessels(facts))
    return any(reaches_safety_valve(facts, vessel) for vessel in reached)


def emergency_vents(
    ctx: TrimContext, style: LineStyle, facts: Facts, fluids: dict[str, FluidClass]
) -> list[TrimPlan]:
    """TOG236: a PSV and an open vent end on a branch off every hydrocarbon tank."""
    plans = []
    for tank in tanks(facts):
        if fluids.get(tank) is FluidClass.NON_FLAMMABLE:
            continue  # scope:non_hydrocarbon (design 17.13 R7 i)
        # rule TOG236-TANK-EMERGENCY-VENT: a tank has a normal vent and an emergency vent (p.236)
        draft = TrimDraft(ctx, style)
        valve = draft.part(_PSV, EMERGENCY_VENT_ROLE)
        end = draft.part(NodeClass.VENTILATION_DEVICE.value, EMERGENCY_VENT_END_ROLE)
        draft.line(tank, [valve, end], None, style=style.branch(service="PG"))
        plans.append(draft.finish())
    return plans


def compressor_suction_psvs(ctx: TrimContext, style: LineStyle, facts: Facts) -> list[TrimPlan]:
    """SAC A-8.2 e: a PSV to the flare on the suction tee of each compressor."""
    plans = []
    for compressor in compressors(facts):
        # rule API14C-SAC: a suction PSV no valve isolates from the compressor (A-8.2 p.47, e)
        tee = tee_of_unit(facts, compressor, SUCTION_TEE_ROLE)
        plans.append(_flare_psv(ctx, style, tee, SUCTION_PSV_ROLE))
    return plans


def furnace_tube_psvs(ctx: TrimContext, style: LineStyle, facts: Facts) -> list[TrimPlan]:
    """SAC A-6.2 l: a PSV to the flare on the heater outlet tee where l.3 does not hold."""
    plans = []
    for furnace in furnaces(facts):
        if tube_protected_by_other_psv(facts, furnace):
            continue
        # rule API14C-SAC: a PSV on the heater tubes unless l.3 holds (A-6.2 p.38, item l)
        tee = tee_of_unit(facts, furnace, HEATER_OUTLET_TEE_ROLE)
        plans.append(_flare_psv(ctx, style, tee, TUBE_PSV_ROLE))
    return plans


def _flare_psv(ctx: TrimContext, style: LineStyle, tee: str, role: str) -> TrimPlan:
    draft = TrimDraft(ctx, style)
    valve = draft.part(_PSV, role)
    draft.line(tee, [valve], None, style=style.branch(service=_FLARE))
    return draft.finish()


def valve_additions(
    ctx: TrimContext,
    style: LineStyle,
    facts: Facts,
    fluids: dict[str, FluidClass],
    enabled: Sequence[str],
) -> list[TrimPlan]:
    """The additions named in `enabled` (a prefix of `PRIORITY`), in priority order."""
    plans: list[TrimPlan] = []
    if EMERGENCY_VENT_ROLE in enabled:
        plans += emergency_vents(ctx, style, facts, fluids)
    if SUCTION_PSV_ROLE in enabled:
        plans += compressor_suction_psvs(ctx, style, facts)
    if TUBE_PSV_ROLE in enabled:
        plans += furnace_tube_psvs(ctx, style, facts)
    return plans
