"""A heat exchanger and everything that hangs on it except its process lines (design realism 7.2).

A **heat exchanger** passes heat between the process stream and a *utility* (steam to heat, cooling
water to cool). The process stream enters and leaves through lines the pattern draws; this module
adds the rest: the utility supply and return stubs (6.13, 6.14), the vent and drain (6.15), an
optional safety valve, the monitoring points of a major item and, for a steam heater, the
temperature loop that throttles the steam. Both the distillation column (reboiler, condenser,
preheater) and the exchanger train use it, so the steam loop is written once.

An air cooler and an electric heater have no utility lines (air and electricity are not piped), so
`service=None` skips them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.config import MONITORED_MAJOR_CLASSES
from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.instruments import control_loop, flow_control_loop
from plantgraph.benchmark.v2.instruments_extra import (
    cascade_master,
    drain_pot_instruments,
    monitor_points,
    point_level_alarm,
)
from plantgraph.benchmark.v2.patterns.assembly import quiet
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.trim_context import LineStyle
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import P_OPTIONAL_ITEM
from plantgraph.benchmark.v2.trims_utility import (
    STEAM_SERVICES,
    exchanger_vent_drain,
    utility_return_stub,
    utility_style,
    utility_supply_stub,
)
from plantgraph.benchmark.v2.trims_valves import control_valve, flow_element
from plantgraph.benchmark.v2.trims_vessel import vessel_psv
from plantgraph.graph.schema import CLASS_SPECS, NodeClass

_UTILITY_FREE_CLASSES = frozenset(
    {NodeClass.AIR_COOLING_SYSTEM.value, NodeClass.ELECTRIC_HEATER.value}
)
STEAM = "LPS"  # low-pressure steam; no source ranks the steam levels, so one is used (decision)
COOLING_WATER = "CWS"  # supply side; the return line is `CWR`


class SteamLoop(BaseModel):
    """The temperature loop of a steam heater: a sensor on `location_id` throttles the steam.

    With `cascade` the temperature controller sets the set point of a steam-flow controller.
    """

    model_config = ConfigDict(frozen=True)

    location_id: str
    cascade: bool = False


class ExchangerTrims(BaseModel):
    """What `exchanger_trims` built; `pot_ids` are the drain pots (equipment) it added."""

    model_config = ConfigDict(frozen=True)

    plan: TrimPlan
    pot_ids: tuple[str, ...]


def exchanger_trims(
    ctx: PatternContext,
    exchanger_id: str,
    node_class: str,
    service: str | None,
    steam_loop: SteamLoop | None = None,
    with_psv: bool = False,
) -> ExchangerTrims:
    """Utility stubs, vent and drain, [safety valve], monitoring points and [steam loop]."""
    if steam_loop is not None and service not in STEAM_SERVICES:
        raise ValueError(
            f"a steam loop needs a steam service {sorted(STEAM_SERVICES)}, got {service}"
        )
    parts: list[TrimPlan] = []
    pot_ids: tuple[str, ...] = ()
    if service is not None:
        parts += _supply(ctx, exchanger_id, service, steam_loop)
        returns, pot_ids = _return(ctx, exchanger_id, service)
        parts += returns
    parts.append(exchanger_vent_drain(ctx.trim, ctx.style, exchanger_id))
    if with_psv:
        parts.append(vessel_psv(ctx.trim, ctx.style, exchanger_id))
    if node_class in MONITORED_MAJOR_CLASSES:
        parts.append(monitor_points(ctx.trim, ctx.style, ctx.density, exchanger_id))
    return ExchangerTrims(plan=combine(*(quiet(part) for part in parts)), pot_ids=pot_ids)


def exchanger_code(node_class: str) -> str:
    """The tag letters of an exchanger class: `E` (shell and tube, plate), `EA`, `EH`."""
    prefix = CLASS_SPECS[NodeClass(node_class)].tag_prefix
    if prefix is None:
        raise ValueError(f"expected an equipment class with a tag prefix, got {node_class!r}")
    return prefix


def wants_safety_valve(ctx: PatternContext) -> bool:
    """A PSV on an exchanger shell that can be blocked in: an optional item, even odds (Rule V)."""
    return ctx.chance(P_OPTIONAL_ITEM)


# ---- supply: the stub, and the steam valve inside it ---------------------------------------------


def _supply(
    ctx: PatternContext, exchanger_id: str, service: str, steam_loop: SteamLoop | None
) -> list[TrimPlan]:
    if steam_loop is None:
        return [utility_supply_stub(ctx.trim, ctx.style, service, exchanger_id)]
    control = _steam_control(ctx, utility_style(ctx.style, service), steam_loop)
    stub = utility_supply_stub(ctx.trim, ctx.style, service, exchanger_id, inline=control.run)
    # the control valve's station branches hang on tees of the stub line, so they follow it
    return [stub, control.model_copy(update={"run": ()})]


def _steam_control(ctx: PatternContext, style: LineStyle, loop: SteamLoop) -> TrimPlan:
    """The steam valve and its loop; the plan's `run` is the valve (or its station)."""
    if loop.cascade:
        slave = flow_control_loop(
            ctx.trim,
            style,
            flow_element(ctx.trim, style, "gas"),
            control_valve(ctx.trim, style, "F"),
        )
        return quiet(combine(slave, cascade_master(ctx.trim, style, slave, "T", loop.location_id)))
    valve = control_valve(ctx.trim, style, "T")
    return quiet(
        combine(valve, control_loop(ctx.trim, style, part_of(valve, "body"), loop.location_id))
    )


# ---- return: the stub, and the instruments of a drain pot ----------------------------------------


def _return(
    ctx: PatternContext, exchanger_id: str, service: str
) -> tuple[list[TrimPlan], tuple[str, ...]]:
    stub = utility_return_stub(ctx.trim, ctx.style, service, exchanger_id)
    pots = tuple(item.node_id for item in stub.equipment)
    if not pots:
        return [stub], ()
    plans = [stub, drain_pot_instruments(ctx.trim, ctx.style, stub)]
    if ctx.chance(ctx.density.p_point_level_switch):
        plans.append(point_level_alarm(ctx.trim, ctx.style, pots[0], "H"))
    return plans, pots


def utility_for(node_class: str, steam: bool) -> str | None:
    """The utility service of a tubular or plate exchanger; air coolers and heaters have none."""
    if node_class in _UTILITY_FREE_CLASSES:
        return None
    return STEAM if steam else COOLING_WATER
