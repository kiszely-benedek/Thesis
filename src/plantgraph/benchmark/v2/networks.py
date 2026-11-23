"""The network pass of the planner (v2.2, handbook on): ties, headers, interarea sheets (design 7).

Runs once, after the plant boundary is closed and before sheets are assigned. It adds lines to the
process units (tie-ins and sub-headers, `network_ties.py`), builds one header unit per (train,
service) (`network_units.py`) and one interarea unit per train that feeds the next. Only the
interarea join changes an existing line: the next train's in-port line opens its source end, since
the interarea line now ends at it.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.flowsheet import UnitSlot
from plantgraph.benchmark.v2.network_models import INTERAREA, NetworkUnit, network_unit_no
from plantgraph.benchmark.v2.network_ties import add_network_ties
from plantgraph.benchmark.v2.network_units import (
    build_network_units,
    first_in_port_joins,
    interarea_unit,
    network_context,
)
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import TrainRecord
from plantgraph.benchmark.v2.trim_context import TrimContext


def add_networks(
    config: GeneratorConfigV22,
    slots: Sequence[UnitSlot],
    instances: Sequence[PatternInstance],
    trims: Sequence[TrimContext],
    trains: Sequence[TrainRecord],
    decks: VariantDecks,
) -> tuple[list[PatternInstance], list[NetworkUnit]]:
    """The instances with their tie-ins, and the network and interarea units, by unit number."""
    train_nos = [slot.train_no for slot in slots]
    tied, crossings = add_network_ties(
        instances, trims, train_nos, config.handbook.network_services, config.sheets
    )
    headers = build_network_units(config, trains, decks, crossings)
    opened, interarea = _add_interarea(config, tied, train_nos, trains, decks)
    return opened, sorted([*headers, *interarea], key=lambda unit: unit.unit_no)


def _add_interarea(
    config: GeneratorConfigV22,
    instances: Sequence[PatternInstance],
    train_nos: Sequence[int],
    trains: Sequence[TrainRecord],
    decks: VariantDecks,
) -> tuple[list[PatternInstance], list[NetworkUnit]]:
    joins = first_in_port_joins(instances, train_nos)
    units = []
    for train_no, train_joins in sorted(joins.items()):
        ctx = network_context(config, trains, decks, train_no, network_unit_no(train_no, INTERAREA))
        units.append(interarea_unit(ctx, train_no, train_joins))
    ends = {destination for group in joins.values() for _, destination, _ in group}
    return [_with_sources_opened(instance, ends) for instance in instances], units


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
