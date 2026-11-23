"""The network units and interarea units of a v2.2 plant (design 7).

A **network unit** is one header of one service for one train, drawn on its own P&ID sheets:
a pipe with one tee per tie-in, and a battery limit at the end that leaves the modelled region
(toward the utility generation, or toward the flare and closed-drain treatment, which are out of
scope). A sheet holds at most `max_tie_ins_per_network_sheet` tie-ins; the header then continues on
the next sheet. The sheets cut by the splitter, one connector pair per cut edge, pair the header
with the process sheets: the feeder lines of this module are the edges that get cut.

An **interarea unit** carries the one line that joins two trains (design 7, TOG p.33): a straight
pipe with the battery-limit isolation of TOG p.34 on its own sheet.

Everything here draws from per-unit streams (the unit's own `TrimContext`), after every process
unit has drawn, so no process draw moves.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.network_models import (
    INTERAREA,
    Crossing,
    NetworkUnit,
    TieDirection,
    network_unit_no,
)
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec, StreamKindV2, TrainRecord
from plantgraph.benchmark.v2.sheets import UnitSheets
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.benchmark.v2.trims_extra import tee_part
from plantgraph.benchmark.v2.trims_utility import utility_style
from plantgraph.benchmark.v2.trims_valves import battery_limit

TITLES = {
    "FL": "Flare header",
    "CHD": "Closed drain header",
    "CWS": "Cooling water supply header",
    "CWR": "Cooling water return header",
    "LPS": "LP steam header",
    "MPS": "MP steam header",
    "CD": "Condensate header",
    "FG": "Fuel gas header",
    INTERAREA: "Interarea connection",
}
_HEADER_SIZE, _FEEDER_SIZE = 8, 4


def network_context(
    config: GeneratorConfigV22, trains: Sequence[TrainRecord], decks: VariantDecks,
    train_no: int, unit_no: int,
) -> TrimContext:  # fmt: skip
    """The trim context of a network unit: its own stream and counters, the train's conventions."""
    return TrimContext(
        unit_no,
        random.Random(f"{config.seed}:network:{unit_no}"),
        config.trims,
        trains[train_no - 1].conventions,
        decks,
        handbook=True,
        handbook_knobs=config.handbook,
        seed=config.seed,
    )


def build_network_units(
    config: GeneratorConfigV22,
    trains: Sequence[TrainRecord],
    decks: VariantDecks,
    crossings: Sequence[Crossing],
) -> list[NetworkUnit]:
    """One unit per (train, service) that has a crossing, in unit-number order."""
    # rule TOG32-NETWORK-SHEETS: relief, drain, utility lines go on network sheets (TOG p.32–34)
    groups: dict[tuple[int, str], list[Crossing]] = defaultdict(list)
    for crossing in crossings:
        groups[(crossing.train_no, crossing.service)].append(crossing)
    units = []
    for (train_no, service), members in sorted(
        groups.items(), key=lambda g: network_unit_no(*g[0])
    ):
        unit_no = network_unit_no(train_no, service)
        ctx = network_context(config, trains, decks, train_no, unit_no)
        units.append(_header_unit(ctx, train_no, service, members, config))
    return units


def _header_unit(
    ctx: TrimContext, train_no: int, service: str, members: list[Crossing],
    config: GeneratorConfigV22,
) -> NetworkUnit:  # fmt: skip
    distribution = members[0].direction is TieDirection.DISTRIBUTION
    capacity = config.handbook.max_tie_ins_per_network_sheet
    # rule PLT-NETWORK-CLOSURE: at most 16 tie-ins a sheet, then the header goes on (TOG p.32–34)
    chunks = [members[i : i + capacity] for i in range(0, len(members), capacity)]
    style = utility_style(LineStyle(size=_HEADER_SIZE), service)
    draft = TrimDraft(ctx, style)
    # rule TOG34-BL-ISOLATION: a header ends at a battery limit (Toghraei 2019 p.34)
    limit = battery_limit(ctx, style, forced=True)
    kind = _kind(service)
    nodes_of_sheet: list[list[str]] = []
    tees: list[LineItemSpec] = []
    previous: str | None = None
    for number, chunk in enumerate(chunks, start=1):
        sheet_tees = [tee_part(draft, "header_tee") for _ in chunk]
        parts = list(sheet_tees)
        if distribution and number == 1:
            parts = [*limit.run, *parts]
        if not distribution and number == len(chunks):
            parts = [*parts, *limit.run]
        draft.line(previous, parts, None, kind, style)
        nodes_of_sheet.append([part.node_id for part in parts])
        tees += sheet_tees
        previous = sheet_tees[-1].node_id
    feeder_style = style.branch(size=_FEEDER_SIZE)
    for position, (crossing, tee) in enumerate(zip(members, tees, strict=True)):
        root = _feeder(draft, crossing, tee, kind, feeder_style, distribution)
        if root is not None:
            nodes_of_sheet[position // capacity].append(root.node_id)
    plan = draft.finish()
    plan = plan.model_copy(update={"roles": {**plan.roles, **limit.roles}})
    return _unit(ctx.unit_no, train_no, service, plan, nodes_of_sheet)


def _feeder(
    draft: TrimDraft, crossing: Crossing, tee: LineItemSpec, kind: StreamKindV2,
    style: LineStyle, distribution: bool,
) -> LineItemSpec | None:  # fmt: skip
    """The line between the header tee and the process sub-header; returns its root valve."""
    if not distribution:
        # collection tie-ins get no root valve (design 7)
        draft.line(crossing.node_id, [], tee.node_id, kind, style)
        return None
    root = draft.dealt_part("block_valve", "network_root_block")
    draft.line(tee.node_id, [root], crossing.node_id, kind, style)
    return root


def _kind(service: str) -> StreamKindV2:
    return StreamKindV2.TRIM if service in ("FL", "CHD") else StreamKindV2.UTILITY_STUB


def _unit(
    unit_no: int, train_no: int, service: str, plan: TrimPlan, nodes_of_sheet: list[list[str]]
) -> NetworkUnit:
    """The unit with its sheets: sheet k of the unit holds the nodes of header chunk k."""
    group_of = {n: f"G{k}" for k, nodes in enumerate(nodes_of_sheet, 1) for n in nodes}
    sheet_of = {n: f"{unit_no}:{k}" for k, nodes in enumerate(nodes_of_sheet, 1) for n in nodes}
    sheets = UnitSheets(group_of=group_of, sheet_of=sheet_of, sheet_count=len(nodes_of_sheet))
    return NetworkUnit(
        unit_no=unit_no, train_no=train_no, service=service, title=TITLES[service],
        plan=plan, sheets=sheets,
    )  # fmt: skip


# ---- interarea ----------------------------------------------------------------------------------


def interarea_unit(
    ctx: TrimContext, train_no: int, joins: Sequence[tuple[str, str, str]]
) -> NetworkUnit:
    """The interarea unit of train `train_no`: one straight line per join.

    `joins` holds `(source node, destination node, fluid code)` of every line that leaves the
    train for the next one. Each becomes one straight line on the interarea sheet with the
    battery-limit isolation in it; the caller opens the destination line's source end.
    """
    # rule TOG33-INTERAREA: lines between trains run over an interarea sheet (Toghraei 2019 p.33)
    draft = TrimDraft(ctx, LineStyle(size=_HEADER_SIZE))
    nodes: list[str] = []
    roles: dict[str, str] = {}
    for source, destination, fluid in joins:
        style = LineStyle(size=_HEADER_SIZE, service=fluid)
        limit = battery_limit(ctx, style, forced=True)
        line = draft.line(source, list(limit.run), destination, StreamKindV2.CROSS_UNIT, style)
        nodes += [part.node_id for part in line.items]
        roles.update(limit.roles)
    plan = draft.finish()
    plan = plan.model_copy(update={"roles": {**plan.roles, **roles}})
    return _unit(ctx.unit_no, train_no, INTERAREA, plan, [nodes])


def first_in_port_joins(
    instances: Sequence[PatternInstance], train_nos: Sequence[int]
) -> dict[int, list[tuple[str, str, str]]]:
    """Per source train, the in-port lines fed by another train: (source, in-port node, fluid)."""
    train_of: dict[str, int] = {}
    for instance, train_no in zip(instances, train_nos, strict=True):
        train_of.update(_node_ids(instance, train_no))
    joins: dict[int, list[tuple[str, str, str]]] = defaultdict(list)
    for instance, train_no in zip(instances, train_nos, strict=True):
        for port in instance.ports:
            line = _line_of(instance, port.line_number)
            source_train = train_of.get(line.src_id or "")
            if port.direction.value == "in" and source_train not in (None, train_no):
                assert line.src_id is not None and source_train is not None
                joins[source_train].append((line.src_id, port.node_id, line.fluid_code))
    return joins


def _node_ids(instance: PatternInstance, train_no: int) -> dict[str, int]:
    plan = instance.plan
    ids = [e.node_id for e in plan.equipment]
    ids += [item.node_id for line in plan.lines for item in line.items]
    return dict.fromkeys(ids, train_no)


def _line_of(instance: PatternInstance, number: str) -> LineSpec:
    return next(line for line in instance.plan.lines if line.line_number == number)
