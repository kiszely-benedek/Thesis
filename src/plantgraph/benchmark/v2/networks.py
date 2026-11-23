"""The network pass of the planner (v2.2, handbook on): ties, headers, interarea sheets (design 7).

Runs once, after the plant boundary is closed and before sheets are assigned. It adds lines to the
process units (tie-ins and sub-headers, `network_ties.py`), builds one header unit per (area,
service) (`network_units.py`) and one interarea unit for the plant, which carries only the lines
that cross an area border (design 17.14 N2). Only an interarea line changes an existing line: the
in-port line it feeds opens its source end, since the interarea line now ends at it. A join between
two trains of the same area stays as v2.1 drew it.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.documents import DocumentRecord
from plantgraph.benchmark.v2.flowsheet import UnitSlot
from plantgraph.benchmark.v2.network_models import (
    INTERAREA,
    PLANT_INTERAREA_AREA,
    NetworkUnit,
    area_of_train,
    network_unit_no,
)
from plantgraph.benchmark.v2.network_ties import add_network_ties
from plantgraph.benchmark.v2.network_units import (
    build_network_units,
    interarea_unit,
    joins_between_trains,
    network_context,
)
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import TrainRecord
from plantgraph.benchmark.v2.relief_ends import assert_no_open_relief
from plantgraph.benchmark.v2.trim_context import TrimContext


def add_networks(
    config: GeneratorConfigV22,
    slots: Sequence[UnitSlot],
    instances: Sequence[PatternInstance],
    trims: Sequence[TrimContext],
    trains: Sequence[TrainRecord],
    documents: Sequence[DocumentRecord],
    decks: VariantDecks,
) -> tuple[list[PatternInstance], list[NetworkUnit]]:
    """The instances with their tie-ins, and the network and interarea units, by unit number."""
    train_nos = [slot.train_no for slot in slots]
    tied, crossings = add_network_ties(
        instances, trims, train_nos, config.handbook.network_services, config.sheets
    )
    headers = build_network_units(config, trains, documents, decks, crossings)
    if "FL" in config.handbook.network_services:
        every_plan = [*(instance.plan for instance in tied), *(unit.plan for unit in headers)]
        assert_no_open_relief(every_plan)
    opened, interarea = _add_interarea(config, tied, train_nos, trains, documents, decks)
    return opened, sorted([*headers, *interarea], key=lambda unit: unit.unit_no)


def _add_interarea(
    config: GeneratorConfigV22,
    instances: Sequence[PatternInstance],
    train_nos: Sequence[int],
    trains: Sequence[TrainRecord],
    documents: Sequence[DocumentRecord],
    decks: VariantDecks,
) -> tuple[list[PatternInstance], list[NetworkUnit]]:
    per_area = config.handbook.trains_per_area
    joins = [
        join
        for join in joins_between_trains(instances, train_nos)
        if area_of_train(join.source_train, per_area)
        != area_of_train(join.destination_train, per_area)
    ]
    if not joins:  # one area (a ~100-sheet plant): no border, no interarea sheet
        return list(instances), []
    ctx = network_context(
        config, trains, documents, decks, 1, network_unit_no(PLANT_INTERAREA_AREA, INTERAREA)
    )
    capacity = config.handbook.max_tie_ins_per_network_sheet
    unit = interarea_unit(ctx, 1, joins, capacity)
    ends = {join.destination for join in joins}
    return [_with_sources_opened(instance, ends) for instance in instances], [unit]


def _with_sources_opened(instance: PatternInstance, ends: set[str]) -> PatternInstance:
    """Open the source end of every in-port line whose first part the interarea line now feeds."""
    numbers = {port.line_number for port in instance.ports if port.node_id in ends}
    if not numbers:
        return instance
    lines = tuple(
        line.model_copy(update={"src_id": None}) if line.line_number in numbers else line
        for line in instance.plan.lines
    )
    return instance.model_copy(update={"plan": instance.plan.model_copy(update={"lines": lines})})
