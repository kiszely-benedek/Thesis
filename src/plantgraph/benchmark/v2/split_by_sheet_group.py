"""The v2 splitter strategy: cut a plant into the sheets its own planner drew (design v2 §9).

A **sheet** is one drawing page. In real life the drafter decides which equipment goes on which
page, so the v2 planner decides it too: it writes the hidden answer-key property `sheet_group` on
every node (`"3:2"` = unit 3, its second sheet), and this strategy only honours it. It adds no
sheet-size logic of its own, so `SplitConfig.sheet_equipment_budget` is ignored here.

Because the splitter cuts whatever crosses a sheet edge, the strategy first checks the two promises
the planner makes about where the cuts may fall, and refuses a plant that breaks them:

- **one unit per sheet** (ADR-0025): a sheet never mixes two process areas;
- **S20**: the motor wiring of a machine (the `control` edge from its start/stop function) and the
  `has_agitator` link between a vessel and its stirrer are never cut. A real drawing keeps a
  machine, its motor switch and its stirrer together; only process pipes and control-valve
  signals run off the page.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable

import networkx as nx

from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.graph.schema import NodeClass, Relation


def by_sheet_group(
    plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random
) -> dict[str, str]:
    """Map every node to the sheet its `sheet_group` names; sheets are numbered 0.. in order.

    Raises:
        ValueError: a node has no `sheet_group` (not a v2 plant), a sheet mixes units, or a
            `has_agitator` / motor `control` edge crosses sheets (S20).
    """
    group_of = {node_id: _sheet_group(plant, node_id) for node_id in plant.nodes}
    ordered_groups = sorted(set(group_of.values()), key=_drawing_order)
    sheet_id = {group: str(index) for index, group in enumerate(ordered_groups)}
    node_sheet = {node_id: sheet_id[group] for node_id, group in group_of.items()}
    _require_one_unit_per_sheet(plant, node_sheet)
    _require_machine_wiring_uncut(plant, node_sheet)
    return node_sheet


def _sheet_group(plant: nx.DiGraph[str], node_id: str) -> str:
    group = plant.nodes[node_id].get("sheet_group")
    if not isinstance(group, str) or not group:
        raise ValueError(
            f"expected a sheet_group like '3:2' on node {node_id!r} (by_sheet_group needs a v2 "
            f"plant), found {group!r}"
        )
    return group


def _drawing_order(group: str) -> tuple[int, int]:
    """`"10:2"` -> (10, 2): numeric, so unit 10 comes after unit 2 and not after unit 1."""
    unit, _, sheet = group.partition(":")
    return int(unit), int(sheet)


def _require_one_unit_per_sheet(plant: nx.DiGraph[str], node_sheet: dict[str, str]) -> None:
    units_on_sheet: dict[str, set[str]] = defaultdict(set)
    for node_id, sheet_id in node_sheet.items():
        unit_id = plant.nodes[node_id].get("unit_id")
        if unit_id is not None:  # a node without a unit (a structural helper) does not count
            units_on_sheet[sheet_id].add(str(unit_id))
    for sheet_id, units in sorted(units_on_sheet.items()):
        if len(units) > 1:
            raise ValueError(
                f"expected one unit per sheet, found sheet {sheet_id} with units {sorted(units)}: "
                "the planner's sheet groups must not span units"
            )


def _require_machine_wiring_uncut(plant: nx.DiGraph[str], node_sheet: dict[str, str]) -> None:
    """S20: no `has_agitator` and no motor `control` edge may join two sheets."""
    for source, target, attrs in plant.edges(data=True):
        if node_sheet[source] == node_sheet[target] or not _is_machine_wiring(plant, source, attrs):
            continue
        raise ValueError(
            f"expected the {attrs['relation']!r} edge {source!r} -> {target!r} to stay on one "
            f"sheet (S20), found sheets {node_sheet[source]} and {node_sheet[target]}"
        )


def _is_machine_wiring(plant: nx.DiGraph[str], source: str, edge_attrs: dict[str, str]) -> bool:
    relation = edge_attrs.get("relation")
    if relation == Relation.HAS_AGITATOR.value:
        return True
    is_motor_function = (
        plant.nodes[source].get("node_class") == NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value
    )
    return relation == Relation.CONTROL.value and is_motor_function


#: the strategies only a v2 plant can use, by the name `SplitConfig.strategy` carries
V2_STRATEGIES: dict[
    str, Callable[[nx.DiGraph[str], SplitConfig, random.Random], dict[str, str]]
] = {
    "by_sheet_group": by_sheet_group,
}
