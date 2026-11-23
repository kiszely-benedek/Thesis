"""The answer key of a planned plant, `GenerationRecordV2` (gold).

Built from the plan alone: the stream kind of every line, the item kind of every tagged item, and
for every node its role and where it is drawn.
"""

from __future__ import annotations

from typing import Any

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.hidden_state import HiddenDesignState, PumpPowerBand, RefluxClass
from plantgraph.benchmark.v2.network_models import NetworkUnit
from plantgraph.benchmark.v2.plan_models import (
    GenerationRecordV2,
    NodeGold,
    SpareSetRecord,
    StreamKindV2,
    UnitRecord,
)
from plantgraph.benchmark.v2.planner import PlannedUnit, PlantPlanV2
from plantgraph.benchmark.v2.pressure_levels import assign_pressure_levels
from plantgraph.benchmark.v2.record_v22 import GenerationRecordV22
from plantgraph.benchmark.v2.symbols import plan_node_classes
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind


def build_record(plan: PlantPlanV2, pydexpi_version: str) -> GenerationRecordV2:
    """The record of `plan`; `pydexpi_version` is the backend's `backend_version`.

    A v2.2 config gets the `GenerationRecordV22` subclass, with the hidden state the units drew.
    """
    common = _common_fields(plan, pydexpi_version)
    if isinstance(plan.config, GeneratorConfigV22):
        return GenerationRecordV22(
            **common, documents=plan.documents, hidden_state=_hidden_state(plan, plan.config)
        )
    return GenerationRecordV2(**common)


def _hidden_state(plan: PlantPlanV2, config: GeneratorConfigV22) -> HiddenDesignState:
    """The design quantities no drawing shows (design 6.1): drawn by units, or derived (levels)."""
    pump_power: dict[str, PumpPowerBand] = {}
    reflux: dict[str, RefluxClass] = {}
    for unit in plan.units:
        pump_power.update(unit.instance.plan.pump_power)
        reflux.update(unit.instance.plan.reflux)
    levels = assign_pressure_levels(plan) if config.handbook.enabled else {}
    return HiddenDesignState(pump_power=pump_power, reflux=reflux, segment_level=levels)


def _common_fields(plan: PlantPlanV2, pydexpi_version: str) -> dict[str, Any]:
    return dict(
        plant_id=plan.config.plant_id,
        seed=plan.config.seed,
        generator_config=plan.config.model_dump_json(),
        pydexpi_version=pydexpi_version,
        trains=plan.trains,
        units=(
            *(_unit_record(unit) for unit in plan.units),
            *(_network_record(unit) for unit in plan.network_units),
        ),
        stream_kind=_stream_kinds(plan),
        item_kind=_item_kinds(plan),
        node_gold=_node_gold(plan),
        spare_sets=_spare_sets(plan),
        open_stub_count=plan.open_stub_count,
        feed_farm_fill_count=0,  # every unit's first in-port finds a taker (see flowsheet.wire)
    )


def _unit_record(unit: PlannedUnit) -> UnitRecord:
    return UnitRecord(
        unit_no=unit.slot.unit_no,
        train_no=unit.slot.train_no,
        pattern=unit.instance.pattern,
        variant=unit.instance.variant,
    )


def _network_record(unit: NetworkUnit) -> UnitRecord:
    """A network or interarea unit; its `pattern` is `NET-<service>` (`NET-INTERAREA`)."""
    return UnitRecord(
        unit_no=unit.unit_no, train_no=unit.train_no, pattern=f"NET-{unit.service}", variant=""
    )


def _stream_kinds(plan: PlantPlanV2) -> dict[str, StreamKindV2]:
    kinds: dict[str, StreamKindV2] = {}
    for unit_plan in plan.unit_plans:
        clash = sorted(set(kinds) & set(unit_plan.stream_kinds))
        if clash:
            raise ValueError(f"line numbers {clash} occur in two units; expected one per plant")
        kinds.update(unit_plan.stream_kinds)
    return kinds


def _item_kinds(plan: PlantPlanV2) -> dict[str, ItemKind]:
    kinds: dict[str, ItemKind] = {}
    for unit_plan in plan.unit_plans:
        kinds.update(_unit_item_kinds(unit_plan))
    return kinds


def _unit_item_kinds(plan: TrimPlan) -> dict[str, ItemKind]:
    """Item kind by tag, for every node that prints a tag."""
    tagged: list[tuple[str, str | None]] = [(item.node_id, item.tag) for item in plan.equipment]
    tagged += [(item.node_id, item.tag) for line in plan.lines for item in line.items]
    tagged += [(item.node_id, item.tag) for item in plan.instruments]
    classes = plan_node_classes(plan)
    return {
        tag: _kind_of(node_id, classes[node_id], tag) for node_id, tag in tagged if tag is not None
    }


def _kind_of(node_id: str, node_class: str, tag: str) -> ItemKind:
    parsed = parse_tag(tag)
    if parsed is None:
        raise ValueError(f"expected a tag of the v2 grammar on {node_id!r}, got {tag!r}")
    return item_kind(node_class, parsed.letters)


def _node_gold(plan: PlantPlanV2) -> dict[str, NodeGold]:
    gold: dict[str, NodeGold] = {}
    for unit in plan.units:
        roles = unit.instance.plan.roles
        unit_no = unit.slot.unit_no
        for node_id, group in unit.sheets.group_of.items():
            if node_id not in roles:
                raise ValueError(f"node {node_id!r} of unit {unit_no} has no role; expected one")
            gold[node_id] = NodeGold(
                role=roles[node_id],
                drawing_group=f"{unit_no}:{group}",
                sheet_group=unit.sheets.sheet_of[node_id],
            )
    for network in plan.network_units:
        for node_id, group in network.sheets.group_of.items():
            gold[node_id] = NodeGold(
                role=network.plan.roles[node_id],
                drawing_group=f"{network.unit_no}:{group}",
                sheet_group=network.sheets.sheet_of[node_id],
            )
    return gold


def _spare_sets(plan: PlantPlanV2) -> tuple[SpareSetRecord, ...]:
    """Every installed A/B(/C) set of the plant, taken from the units' plans."""
    return tuple(
        SpareSetRecord(
            unit_no=unit.slot.unit_no,
            role=unit.instance.plan.roles[node_ids[0]],
            node_ids=node_ids,
        )
        for unit in plan.units
        for node_ids in unit.instance.plan.spare_sets
    )
