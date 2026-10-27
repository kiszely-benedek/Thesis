"""U5, the exchanger train (design realism 7.2; pid-vocabulary 13.3).

An **exchanger train** is two to four heat exchangers in series on one liquid line: the cold stream
passes through each in turn and leaves warmer. An optional electric heater after the last one trims
the temperature. Each exchanger gets steam or cooling water from a utility stub (`exchanger.py`).

Control loop (textbook practice, not taken from a source: design 7 marks it [U]): a temperature
controller `TIC` on the train outlet holds the outlet temperature. If the last exchanger with a
utility is steam-heated the controller throttles its steam; otherwise it moves a valve on a bypass
that lets part of the stream skip that exchanger (the bypass hangs on a pair of tees).

Variants (decks, `variants.PATTERN_DECKS`): exchanger count, class of each exchanger (tubular or
plate), the electric trim heater, the utility of each exchanger. Ports: `cold` in, `heated` out.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.instrument_draft import part_of
from plantgraph.benchmark.v2.instruments import control_loop
from plantgraph.benchmark.v2.patterns.assembly import (
    close_run,
    equipment_plan,
    flow_indicator_plan,
    line_containing,
    pressure_gauge_tap,
    quiet,
    run_of,
    tee_plan,
    thermometer_tap,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.exchanger import (
    ExchangerTrims,
    SteamLoop,
    exchanger_code,
    exchanger_trims,
    utility_for,
    wants_safety_valve,
)
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    PortDirection,
    open_end_port,
)
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims_valves import battery_limit, control_valve
from plantgraph.graph.schema import NodeClass

PATTERN_ID = "U5"
SYSTEM_CODE = "HXT"
_ELECTRIC = NodeClass.ELECTRIC_HEATER.value
_MAX_ONE_SHEET = 4  # a train of up to four exchangers is one drawing; a longer one is cut in two


class _Choices(BaseModel):
    """What one train drew from its decks: classes and utilities, in flow order."""

    model_config = ConfigDict(frozen=True)

    classes: tuple[str, ...]  # the exchangers, then the electric heater when drawn
    steam: tuple[bool, ...]  # per exchanger (not the heater): steam, else cooling water

    @property
    def exchanger_count(self) -> int:
        """The exchangers that take a utility; an electric heater after them is not counted."""
        return len(self.steam)

    @property
    def label(self) -> str:
        """The choices as the answer key's variant text."""
        utilities = "+".join("steam" if steam else "cooling_water" for steam in self.steam)
        return variant_label(
            exchangers=self.exchanger_count,
            classes="+".join(self.classes),
            utilities=utilities,
            trim_heater=len(self.classes) > self.exchanger_count,
        )


def _draw_choices(ctx: PatternContext) -> _Choices:
    count = int(ctx.deal("U5.exchanger_count"))
    classes = [ctx.deal("U5.exchanger") for _ in range(count)]
    steam = tuple(ctx.deal("U5.utility") == "steam" for _ in range(count))
    if ctx.deal("U5.trim_heater") == _ELECTRIC:
        classes.append(_ELECTRIC)
    return _Choices(classes=tuple(classes), steam=steam)


def build_exchanger_train(ctx: PatternContext) -> PatternInstance:
    """The exchangers in series with utilities, taps and the outlet temperature loop."""
    choices = _draw_choices(ctx)
    equipment = [
        equipment_plan(ctx, node_class, exchanger_code(node_class), _role(node_class))
        for node_class in choices.classes
    ]
    ids = [plan.ports["equipment"] for plan in equipment]
    controlled = choices.exchanger_count - 1  # the last exchanger that has a utility
    steam_valve = choices.steam[controlled]
    trims = [
        _trims(ctx, choices, ids, index, steam_valve and index == controlled)
        for index in range(len(ids))
    ]
    lines, inlet_tee, outlet_tee = _process_lines(ctx, ids, controlled, bypass=not steam_valve)
    parts = [*(quiet(plan) for plan in equipment), lines, *(trim.plan for trim in trims)]
    plan = with_stream_kinds(combine(*(quiet(part) for part in parts)))
    pots = [trim.pot_ids for trim in trims]
    groups = _drawing_groups([(node, *pot) for node, pot in zip(ids, pots, strict=True)])
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=choices.label,
        plan=plan,
        ports=(
            open_end_port("cold", PortDirection.IN, Phase.LIQUID, line_containing(plan, inlet_tee)),
            open_end_port(
                "heated", PortDirection.OUT, Phase.LIQUID, line_containing(plan, outlet_tee)
            ),
        ),
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _role(node_class: str) -> str:
    return "trim_heater" if node_class == _ELECTRIC else "exchanger"


def _trims(
    ctx: PatternContext, choices: _Choices, ids: list[str], index: int, steam_loop: bool
) -> ExchangerTrims:
    """Utility lines and the rest of exchanger `index`; a steam loop senses the train outlet."""
    node_class = choices.classes[index]
    steam = index < choices.exchanger_count and choices.steam[index]
    loop = SteamLoop(location_id=ids[-1]) if steam_loop else None
    with_psv = node_class != _ELECTRIC and wants_safety_valve(ctx)
    return exchanger_trims(
        ctx, ids[index], node_class, utility_for(node_class, steam), loop, with_psv
    )


# ---- the process line ----------------------------------------------------------------------------


class _Tees(BaseModel):
    """The tees of the process line: gauge and thermometer taps, the bypass pair, the meter."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    inlet: TrimPlan  # inlet pressure gauge
    outlet: TrimPlan  # outlet pressure gauge
    after: tuple[TrimPlan, ...]  # outlet thermometer of each exchanger
    split: TrimPlan | None  # the bypass leaves here ...
    merge: TrimPlan | None  # ... and rejoins here
    flow: tuple[TrimPlan, ...]  # the optional inlet flow meter


def _draw_tees(ctx: PatternContext, count: int, bypass: bool) -> _Tees:
    return _Tees(
        inlet=tee_plan(ctx, "inlet_gauge_tee"),
        outlet=tee_plan(ctx, "outlet_gauge_tee"),
        after=tuple(tee_plan(ctx, "exchanger_outlet_tee") for _ in range(count)),
        split=tee_plan(ctx, "bypass_split_tee") if bypass else None,
        merge=tee_plan(ctx, "bypass_merge_tee") if bypass else None,
        flow=(flow_indicator_plan(ctx),) if _optional(ctx) else (),
    )


def _optional(ctx: PatternContext) -> bool:
    return ctx.chance(ctx.density.p_optional_instrument)


def _process_lines(
    ctx: PatternContext, ids: list[str], controlled: int, bypass: bool
) -> tuple[TrimPlan, str, str]:
    """The segments between the exchangers, their taps and the bypass.

    Segment `j` enters exchanger `j`; the last leaves the train. Returns the plan and the ids of
    the inlet and outlet gauge tees (the ports' lines hold them).
    """
    count = len(ids)
    tees = _draw_tees(ctx, count, bypass)
    mains = []
    for j in range(count + 1):
        src = ids[j - 1] if j > 0 else None
        dst = ids[j] if j < count else None
        mains.append(close_run(ctx, run_of(*_segment(ctx, tees, j, count, controlled)), src, dst))
    taps = [thermometer_tap(ctx, tee.ports["tee"], "exchanger_outlet_ti") for tee in tees.after]
    taps.append(pressure_gauge_tap(ctx, tees.inlet.ports["tee"], "inlet_pi"))
    taps.append(pressure_gauge_tap(ctx, tees.outlet.ports["tee"], "outlet_pi"))
    bypass_line = [_bypass_line(ctx, tees, ids[-1])] if bypass else []
    plan = combine(*mains, *taps, *bypass_line)
    return quiet(plan), tees.inlet.ports["tee"], tees.outlet.ports["tee"]


def _segment(
    ctx: PatternContext, tees: _Tees, j: int, count: int, controlled: int
) -> list[TrimPlan]:
    """The parts of segment `j` in flow order."""
    parts: list[TrimPlan] = []
    if j == 0:
        parts += [battery_limit(ctx.trim, ctx.style), tees.inlet, *tees.flow]
    else:
        if tees.merge is not None and j - 1 == controlled:
            parts.append(tees.merge)
        parts.append(tees.after[j - 1])
    if j == count:
        parts += [tees.outlet, battery_limit(ctx.trim, ctx.style)]
    elif tees.split is not None and j == controlled:
        parts.append(tees.split)
    return parts


def _bypass_line(ctx: PatternContext, tees: _Tees, outlet_id: str) -> TrimPlan:
    """`TT -> TIC -> TV` on a line around the controlled exchanger, split tee to merge tee."""
    if tees.split is None or tees.merge is None:
        raise ValueError("a bypass needs its split and merge tees")
    valve = control_valve(ctx.trim, ctx.style, "T")
    loop = control_loop(ctx.trim, ctx.style, part_of(valve, "body"), outlet_id)
    run = combine(quiet(valve), quiet(loop))
    return quiet(close_run(ctx, run, tees.split.ports["tee"], tees.merge.ports["tee"]))


def _drawing_groups(units: list[tuple[str, ...]]) -> DrawingGroups:
    """One group for up to four exchangers; a longer train is cut at the midpoint."""
    groups = DrawingGroups()
    if len(units) <= _MAX_ONE_SHEET:
        groups.put([node for unit in units for node in unit], "G1")
        return groups
    middle = len(units) // 2
    groups.put([node for unit in units[:middle] for node in unit], "G1")
    groups.put([node for unit in units[middle:] for node in unit], "G2")
    return groups
