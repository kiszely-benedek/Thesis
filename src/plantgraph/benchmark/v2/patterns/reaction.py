"""U3, the heater-reactor-separator (design realism 7.2; pid-vocabulary 5.2, 13.3).

A **reactor system** turns a feed into products and splits them. The feed is warmed in a
**feed/effluent exchanger** by the hot product leaving the reactor, heated further in a **fired
heater** (a furnace that burns fuel gas), reacts in the **reactor** and, after giving heat to the
feed, is cooled in an air cooler and separated into gas and liquid in the **separator**. A pump set
sends the liquid on.

Control and protection (textbook practice, not taken from a source: design 7 marks them [U]):
- heater outlet temperature `TIC` moves the fuel-gas valve; fuel-gas pressure `PIC` its own valve;
- a flame sensor (`BE -> BSL`) shuts the fuel gas; a **double block and bleed** (two valves and
  a vent between them) isolates the furnace;
- the reactor inlet temperature `TIC` moves a bypass valve around the exchanger;
- separator pressure `PIC` moves the gas valve; its level `LIC` the liquid valve, a letdown valve
  followed by a **spec break** (the pipe class changes, so the line number does); high separator
  pressure (`PT -> PSHH`) shuts the valve on its inlet;
- the reactor has a safety valve and a rupture disc; with `p_multivariable` a multivariable
  controller `UC` reads its temperature and pressure.

Furnace and blower: the furnace is drawn without a blower or chimney (the allowlist leaves them
out), so its group holds the furnace alone. Variants: plain or agitated reactor (deck
`U3.reactor`; the agitator is a motor-driven stirrer, started by a hand switch), skillet blinds
(`p_skillet`) at the furnace and reactor inlets. Ports: `feed`, `recycle_gas` (in), `gas`, `liquid`
(out, last, because the grammar feeds the next unit from the last port of a phase).
Drawing groups: G1 furnace, G2 exchanger and reactor, G3 cooler, separator and pumps.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.instruments_extra import monitor_points
from plantgraph.benchmark.v2.patterns.assembly import (
    equipment_plan,
    line_between,
    line_containing,
    quiet,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.exchanger import exchanger_code, exchanger_trims
from plantgraph.benchmark.v2.patterns.machines import agitator_plan, motor_drive
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    PortDirection,
    PortKind,
    open_end_port,
)
from plantgraph.benchmark.v2.patterns.pump_set import PumpSet, build_pump_set
from plantgraph.benchmark.v2.patterns.reaction_parts import (
    cooler_to_separator,
    exchanger_to_cooler,
    feed_side,
    fuel_gas_line,
    heater_to_reactor,
    letdown_header,
    reactor_instruments,
    reactor_to_exchanger,
    recycle_gas_line,
    separator_gas_outlet,
)
from plantgraph.benchmark.v2.patterns.separation import level_control_valve
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.patterns.vessel_parts import level_instruments
from plantgraph.benchmark.v2.trim_plan import combine
from plantgraph.graph.schema import NodeClass

PATTERN_ID = "U3"
SYSTEM_CODE = "RXN"
_TUBULAR = NodeClass.TUBULAR_HEAT_EXCHANGER.value
_COOLER = NodeClass.AIR_COOLING_SYSTEM.value
_SEPARATOR = NodeClass.GRAVITATIONAL_SEPARATOR.value
_VESSEL = NodeClass.PRESSURE_VESSEL.value


def build_reactor_system(ctx: PatternContext) -> PatternInstance:
    """Exchanger, furnace, reactor, cooler, separator and pumps; see the module docstring."""
    agitated = ctx.deal("U3.reactor") == "agitated"
    exchanger_eq = equipment_plan(
        ctx, _TUBULAR, exchanger_code(_TUBULAR), "feed_effluent_exchanger"
    )
    furnace_eq = equipment_plan(ctx, NodeClass.FURNACE.value, "H", "fired_heater")
    reactor_eq = equipment_plan(ctx, _VESSEL, "V", "reactor")
    cooler_eq = equipment_plan(ctx, _COOLER, exchanger_code(_COOLER), "effluent_cooler")
    separator_eq = equipment_plan(ctx, _SEPARATOR, "V", "separator")
    exchanger, furnace, reactor, cooler, separator = (
        plan.ports["equipment"]
        for plan in (exchanger_eq, furnace_eq, reactor_eq, cooler_eq, separator_eq)
    )
    agitator = agitator_plan(ctx, reactor) if agitated else None

    feed = feed_side(ctx, exchanger, furnace, reactor)
    gas_out, pressure_valve = separator_gas_outlet(ctx, separator, _SEPARATOR)
    header = letdown_header(ctx, level_control_valve(ctx, separator))
    pumps = build_pump_set(ctx, separator, "CentrifugalPump", "liquid_pump", header=header)
    parts = [
        *(quiet(eq) for eq in (exchanger_eq, furnace_eq, reactor_eq, cooler_eq, separator_eq)),
        *([quiet(agitator)] if agitator else []),
        feed.plan,
        heater_to_reactor(ctx, furnace, reactor),
        reactor_to_exchanger(ctx, reactor, exchanger),
        exchanger_to_cooler(ctx, exchanger, cooler),
        cooler_to_separator(ctx, cooler, separator),
        gas_out,
        recycle_gas_line(ctx, feed.recycle_tee),
        fuel_gas_line(ctx, furnace),
        pumps.plan,
        exchanger_trims(ctx, exchanger, _TUBULAR, None).plan,
        exchanger_trims(ctx, cooler, _COOLER, None).plan,
        reactor_instruments(ctx, reactor),
        monitor_points(ctx.trim, ctx.style, ctx.density, furnace),
        level_instruments(ctx, separator, low_low=True),
        *([motor_drive(ctx, agitator.ports["equipment"])] if agitator else []),
    ]
    plan = with_stream_kinds(combine(*(quiet(part) for part in parts)))
    stirrer = [agitator.ports["equipment"]] if agitator else []
    groups = _drawing_groups(furnace, [exchanger, reactor, *stirrer], [cooler, separator], pumps)
    feed_line = line_between(plan, None, exchanger)
    recycle_line = line_between(plan, None, feed.recycle_tee)
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=variant_label(reactor="agitated" if agitated else "plain") + f"|{pumps.variant}",
        plan=plan,
        ports=(
            open_end_port("feed", PortDirection.IN, Phase.LIQUID, feed_line),
            open_end_port(
                "recycle_gas", PortDirection.IN, Phase.GAS, recycle_line, PortKind.RECYCLE
            ),
            open_end_port(
                "gas", PortDirection.OUT, Phase.GAS, line_containing(plan, pressure_valve)
            ),
            pumps.discharge.model_copy(update={"name": "liquid"}),
        ),
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _drawing_groups(
    furnace: str, middle: list[str], last: list[str], pumps: PumpSet
) -> DrawingGroups:
    """G1 the furnace, G2 exchanger and reactor (and its agitator), G3 cooler, separator, pumps.

    A pump set drawn on its own sheet (deck `pump_set.group`) is a pinned fourth group.
    """
    groups = DrawingGroups()
    groups.put([furnace], "G1")
    groups.put(middle, "G2")
    groups.put([*last, *([] if pumps.own_sheet else pumps.pump_ids)], "G3")
    if pumps.own_sheet:
        groups.put(pumps.pump_ids, "G4", pinned=True)
    return groups
