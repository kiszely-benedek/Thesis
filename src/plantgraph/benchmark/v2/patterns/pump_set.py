"""The pump set: the building block every pattern's pumps come from (design realism 7.1).

A **pump set** is one to three identical pumps that share a suction header and a discharge header:
an installed spare (`P-1203A` running, `P-1203B` standing by) is drawn next to the duty pump so the
plant can switch over. With more than one pump the suction side splits at a tee per extra pump and
the discharge side merges again; the first pump's lines carry those tees and every other pump
branches off them. Each pump has its own suction trim (6.1/6.2), discharge trim (6.3), vent and
drain (6.4), relief (6.5) and minimum-flow line (6.6), all from `trims.pump_trims`.

Variants drawn here: how many pumps (`p_single_pump`, `p_triple_pump_set`), whether a spared set is
drawn on a sheet of its own (deck `pump_set.group`), and whether pressure is read by a gauge per
pump or one transmitter on the header (deck `pump_set.pressure`).
"""

from __future__ import annotations

from typing import cast, get_args

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.config import PumpPressureMode
from plantgraph.benchmark.v2.instruments import machine_monitor
from plantgraph.benchmark.v2.instruments_extra import machine_start_stop
from plantgraph.benchmark.v2.patterns.assembly import (
    line_containing,
    quiet,
    spared_set,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import Phase, Port, PortDirection, open_end_port
from plantgraph.benchmark.v2.patterns.variants import (
    PUMP_SET_GROUP_DECK,
    PUMP_SET_PRESSURE_DECK,
    variant_label,
)
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, LineItemSpec
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.trims import pump_trims, suction_for
from plantgraph.benchmark.v2.trims_extra import header_pressure_tap, tee_part

_PUMP_TYPE_CODE = "P"


class PumpSet(BaseModel):
    """A built pump set. `discharge` is its out-port; `feed_tee_ids` take extra suction feeds."""

    model_config = ConfigDict(frozen=True)

    plan: TrimPlan
    pump_ids: tuple[str, ...]
    own_sheet: bool  # drawn on a sheet of its own (only a spared set can be)
    discharge: Port
    feed_tee_ids: tuple[str, ...]
    variant: str


class _Manifold(BaseModel):
    """The tees that join the pumps: where the suction splits and the discharge merges."""

    model_config = ConfigDict(frozen=True)

    feeds: tuple[LineItemSpec, ...]
    splits: tuple[LineItemSpec, ...]
    merges: tuple[LineItemSpec, ...]
    header_tee: LineItemSpec | None
    plan: TrimPlan  # the tees' roles and ports, no lines


def build_pump_set(
    ctx: PatternContext,
    vessel_id: str,
    pump_class: str,
    role: str,
    header: TrimPlan | None = None,
    feed_count: int = 0,
) -> PumpSet:
    """The pumps, their lines and instruments, drawing from `vessel_id`.

    `header` is a plan with an open `run` (a flow or level control valve) that closes the
    discharge header. `feed_count` extra tees on the suction line let other tanks feed the set.
    Every pump gets the class `pump_class` and the role `role`.
    """
    suction_for(pump_class)  # raises for a class that is not a centrifugal or PD pump
    count = _draw_pump_count(ctx)
    group = ctx.deal(PUMP_SET_GROUP_DECK) if count > 1 else "with_suction_vessel"
    pressure = _deal_pressure(ctx)
    pumps = spared_set(ctx, pump_class, _PUMP_TYPE_CODE, count, has_motor=True)
    manifold = _manifold(ctx, count, feed_count, with_header_tee=pressure == "header_pt")
    header_run = header.run if header is not None else ()
    pump_plans = [
        _pump_plan(ctx, pump, index, vessel_id, manifold, pressure, header_run)
        for index, pump in enumerate(pumps)
    ]
    # the header's valve branches start at tees of the first pump's discharge line: they come last
    header_extra = [header.model_copy(update={"run": ()})] if header is not None else []
    equipment = TrimPlan(equipment=tuple(pumps), roles={pump.node_id: role for pump in pumps})
    plan = combine(
        equipment,
        manifold.plan,
        *pump_plans,
        *_header_pressure_plan(ctx, manifold),
        *[extra.with_port_prefix("header") for extra in header_extra],
    )
    plan = with_stream_kinds(plan)
    first_discharge_check = plan.ports["pump0.discharge.check"]
    discharge = open_end_port(
        "discharge", PortDirection.OUT, Phase.LIQUID, line_containing(plan, first_discharge_check)
    )
    return PumpSet(
        plan=plan,
        pump_ids=tuple(pump.node_id for pump in pumps),
        own_sheet=group == "own_sheet",
        discharge=discharge,
        feed_tee_ids=tuple(tee.node_id for tee in manifold.feeds),
        variant=variant_label(pumps=count, group=group, pressure=pressure),
    )


def _draw_pump_count(ctx: PatternContext) -> int:
    """One pump with chance `p_single_pump`, three with `p_triple_pump_set`, else two."""
    roll = ctx.trim.rng.random()
    if roll < ctx.knobs.p_single_pump:
        return 1
    if roll < ctx.knobs.p_single_pump + ctx.knobs.p_triple_pump_set:
        return 3
    return 2


def _deal_pressure(ctx: PatternContext) -> PumpPressureMode:
    card = ctx.deal(PUMP_SET_PRESSURE_DECK)
    if card not in get_args(PumpPressureMode):
        raise ValueError(
            f"expected a pump pressure mode in {get_args(PumpPressureMode)}, got {card!r}"
        )
    return cast(PumpPressureMode, card)


def _manifold(ctx: PatternContext, count: int, feed_count: int, with_header_tee: bool) -> _Manifold:
    draft = TrimDraft(ctx.trim, ctx.style)
    feeds = tuple(tee_part(draft, "suction_feed_tee") for _ in range(feed_count))
    splits = tuple(tee_part(draft, "suction_split_tee") for _ in range(count - 1))
    merges = tuple(tee_part(draft, "discharge_merge_tee") for _ in range(count - 1))
    header_tee = tee_part(draft, "header_pressure_tee") if with_header_tee else None
    plan = draft.finish_with_ports({f"suction_feed{i}": tee for i, tee in enumerate(feeds)})
    return _Manifold(feeds=feeds, splits=splits, merges=merges, header_tee=header_tee, plan=plan)


def _pump_plan(
    ctx: PatternContext,
    pump: EquipmentSpec,
    index: int,
    vessel_id: str,
    manifold: _Manifold,
    pressure: PumpPressureMode,
    header_run: tuple[LineItemSpec, ...],
) -> TrimPlan:
    """The lines, trims and instruments of pump `index`; pump 0 carries the manifold tees."""
    is_first = index == 0
    trims = pump_trims(
        ctx.trim,
        ctx.style,
        pump.node_id,
        pump.node_class,
        vessel_id,
        dst_id=None if is_first else manifold.merges[index - 1].node_id,
        pressure_mode=pressure,
        suction_head=(*manifold.feeds, *manifold.splits) if is_first else (),
        suction_src_id=None if is_first else manifold.splits[index - 1].node_id,
        discharge_tail=_first_pump_tail(manifold, header_run) if is_first else (),
    )
    return combine(trims, _pump_instruments(ctx, pump.node_id)).with_port_prefix(f"pump{index}")


def _first_pump_tail(
    manifold: _Manifold, header_run: tuple[LineItemSpec, ...]
) -> tuple[LineItemSpec, ...]:
    """What follows the first pump's discharge trim: merge tees, pressure tap tee, the header."""
    header_tee = (manifold.header_tee,) if manifold.header_tee is not None else ()
    return (*manifold.merges, *header_tee, *header_run)


def _pump_instruments(ctx: PatternContext, pump_id: str) -> TrimPlan:
    """Hand switch with running status; a bearing thermometer with `p_bearing_temperature`."""
    parts = [quiet(machine_start_stop(ctx.trim, ctx.style, ctx.instruments, pump_id))]
    if ctx.chance(ctx.density.p_bearing_temperature):
        parts.append(quiet(machine_monitor(ctx.trim, ctx.style, pump_id, "bearing_temperature")))
    return combine(*parts)


def _header_pressure_plan(ctx: PatternContext, manifold: _Manifold) -> list[TrimPlan]:
    """One pressure transmitter and indicator on the discharge header (`header_pt` mode only)."""
    if manifold.header_tee is None:
        return []
    return [quiet(header_pressure_tap(ctx.trim, ctx.style, manifold.header_tee.node_id))]
