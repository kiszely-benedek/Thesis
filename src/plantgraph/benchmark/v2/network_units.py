"""The network units and the interarea unit of a v2.2 plant (design 7, 17.14 N2).

A **network unit** is one header of one service for one **area** (a run of consecutive trains, the
plant region of one document), drawn on its own P&ID sheets: a pipe with one tee per tie-in, and a
battery limit at the end that leaves the modelled region (toward the utility generation, or toward
the flare and closed-drain treatment, which are out of scope). A sheet holds at most
`max_tie_ins_per_network_sheet` tie-ins; the header then continues on the next sheet. The sheets cut
by the splitter, one connector pair per cut edge, pair the header with the process sheets: the
feeder lines of this module are the edges that get cut.

The **interarea unit** is one per plant. It carries every line that crosses the border between two
areas (TOG pp.33-34): a straight pipe with the battery-limit isolation of TOG p.34, at most one
sheet's capacity of lines per sheet.

Everything here draws from per-unit streams (the unit's own `TrimContext`), after every process
unit has drawn, so no process draw moves.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.documents import DocumentRecord, document_of_train
from plantgraph.benchmark.v2.network_models import (
    INTERAREA,
    PLANT_INTERAREA_AREA,
    Crossing,
    Join,
    NetworkUnit,
    TieDirection,
    area_of_train,
    first_train_of_area,
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
    config: GeneratorConfigV22, trains: Sequence[TrainRecord],
    documents: Sequence[DocumentRecord], decks: VariantDecks, train_no: int, unit_no: int,
) -> TrimContext:  # fmt: skip
    """The trim context of a network unit: its own stream and counters.

    It takes the conventions of the document of `train_no` (the area's first train), manual valve
    tagging included.
    """
    document = documents[document_of_train(train_no, config.handbook.trains_per_document) - 1]
    return TrimContext(
        unit_no,
        random.Random(f"{config.seed}:network:{unit_no}"),
        config.trims,
        trains[train_no - 1].conventions,
        decks,
        handbook=True,
        handbook_knobs=config.handbook,
        seed=config.seed,
        manual_valves_untagged=document.manual_valves_untagged,
    )


def build_network_units(
    config: GeneratorConfigV22,
    trains: Sequence[TrainRecord],
    documents: Sequence[DocumentRecord],
    decks: VariantDecks,
    crossings: Sequence[Crossing],
) -> list[NetworkUnit]:
    """One unit per (area, service) that has a crossing, in unit-number order."""
    # rule TOG32-NETWORK-SHEETS: relief, drain, utility lines go on network sheets (TOG p.32–34)
    per_area = config.handbook.trains_per_area
    groups: dict[tuple[int, str], list[Crossing]] = defaultdict(list)
    for crossing in crossings:
        groups[(area_of_train(crossing.train_no, per_area), crossing.service)].append(crossing)
    units = []
    for (area_no, service), members in sorted(groups.items(), key=lambda g: network_unit_no(*g[0])):
        unit_no = network_unit_no(area_no, service)
        train_no = first_train_of_area(area_no, per_area)
        ctx = network_context(config, trains, documents, decks, train_no, unit_no)
        units.append(_header_unit(ctx, area_no, train_no, service, members, config))
    return units


def _header_unit(
    ctx: TrimContext, area_no: int, train_no: int, service: str, members: list[Crossing],
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
    return _unit(ctx.unit_no, area_no, train_no, service, plan, nodes_of_sheet)


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
    unit_no: int, area_no: int, train_no: int, service: str, plan: TrimPlan,
    nodes_of_sheet: list[list[str]],
) -> NetworkUnit:  # fmt: skip
    """The unit with its sheets: sheet k of the unit holds the nodes of header chunk k."""
    group_of = {n: f"G{k}" for k, nodes in enumerate(nodes_of_sheet, 1) for n in nodes}
    sheet_of = {n: f"{unit_no}:{k}" for k, nodes in enumerate(nodes_of_sheet, 1) for n in nodes}
    sheets = UnitSheets(group_of=group_of, sheet_of=sheet_of, sheet_count=len(nodes_of_sheet))
    return NetworkUnit(
        unit_no=unit_no, area_no=area_no, train_no=train_no, service=service,
        title=TITLES[service], plan=plan, sheets=sheets,
    )  # fmt: skip


# ---- interarea ----------------------------------------------------------------------------------


def interarea_unit(
    ctx: TrimContext, train_no: int, joins: Sequence[Join], capacity: int
) -> NetworkUnit:
    """The plant's interarea unit: one straight line per join, `capacity` lines to a sheet.

    The joins are those between two areas, in area order; the caller opens each destination
    line's source end, since the interarea line now ends at it.
    """
    # rule TOG33-INTERAREA: lines between areas run over an interarea sheet (Toghraei 2019 p.33)
    draft = TrimDraft(ctx, LineStyle(size=_HEADER_SIZE))
    roles: dict[str, str] = {}
    nodes_of_sheet = [
        _interarea_sheet(ctx, draft, joins[i : i + capacity], roles)
        for i in range(0, len(joins), capacity)
    ]
    plan = draft.finish()
    plan = plan.model_copy(update={"roles": {**plan.roles, **roles}})
    return _unit(ctx.unit_no, PLANT_INTERAREA_AREA, train_no, INTERAREA, plan, nodes_of_sheet)


def _interarea_sheet(
    ctx: TrimContext, draft: TrimDraft, joins: Sequence[Join], roles: dict[str, str]
) -> list[str]:
    """Draw the lines of one interarea sheet; returns its nodes and adds the limits' roles."""
    nodes: list[str] = []
    for join in joins:
        style = LineStyle(size=_HEADER_SIZE, service=join.fluid_code)
        limit = battery_limit(ctx, style, forced=True)
        line = draft.line(
            join.source, list(limit.run), join.destination, StreamKindV2.CROSS_UNIT, style
        )
        nodes += [part.node_id for part in line.items]
        roles.update(limit.roles)
    return nodes


def joins_between_trains(
    instances: Sequence[PatternInstance], train_nos: Sequence[int]
) -> list[Join]:
    """Every in-port line fed by a line of another train, in source-train order."""
    train_of: dict[str, int] = {}
    for instance, train_no in zip(instances, train_nos, strict=True):
        train_of.update(_node_ids(instance, train_no))
    joins: list[Join] = []
    for instance, train_no in zip(instances, train_nos, strict=True):
        for port in instance.ports:
            line = _line_of(instance, port.line_number)
            source_train = train_of.get(line.src_id or "")
            if port.direction.value == "in" and source_train not in (None, train_no):
                assert line.src_id is not None and source_train is not None
                joins.append(Join(
                    source_train=source_train, destination_train=train_no, source=line.src_id,
                    destination=port.node_id, fluid_code=line.fluid_code,
                ))  # fmt: skip
    return sorted(joins, key=lambda join: join.source_train)  # stable: ties keep plan order


def _node_ids(instance: PatternInstance, train_no: int) -> dict[str, int]:
    plan = instance.plan
    ids = [e.node_id for e in plan.equipment]
    ids += [item.node_id for line in plan.lines for item in line.items]
    return dict.fromkeys(ids, train_no)


def _line_of(instance: PatternInstance, number: str) -> LineSpec:
    return next(line for line in instance.plan.lines if line.line_number == number)
