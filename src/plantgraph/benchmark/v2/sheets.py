"""Sheet composition: which drawn sheet each node of a unit lands on (design realism 9).

In practice a drafter decides which equipment goes on which drawing, so the planner decides and
the splitter later only honours it. Three steps, per process unit (a sheet never shows two units):

1. **Pattern groups.** The pattern says which equipment belongs together (`drawing_group_of`).
2. **Rider rule.** Everything else rides along: a line's inline parts take the group of the line's
   source (or its destination when the source is open or in another unit), and a control loop
   takes the group of the item its sensor is located on. The cut therefore falls at a nozzle or
   between trims, never inside a control-valve station.
3. **Merge.** Consecutive groups of the unit, in flow order, share a sheet while they stay within
   `max_equipment_per_sheet` and `max_symbols_before_stubs`. A pinned group is never merged. A
   pattern group is never split, so a single group may exceed the symbol cap.

`min_equipment_per_sheet` is a band to report, not a rule to enforce: merging forward is already
done wherever the caps allow, and a sheet shows one unit, so a small unit cannot be topped up.
The result per node is the gold `sheet_group` `"{unit}:{k}"`, k counted from 1 in flow order.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.config import SheetKnobs
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.symbols import SymbolKind, is_symbol, plan_node_classes, symbol_kind
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.graph.schema import Relation


class GroupSize(BaseModel):
    """What a pattern group holds before the merge: its equipment and its drawn symbols."""

    model_config = ConfigDict(frozen=True)

    equipment: int
    symbols: int


class UnitSheets(BaseModel):
    """The result for one unit: the pattern group and the sheet of every node."""

    model_config = ConfigDict(frozen=True)

    group_of: dict[str, str]  # node id -> pattern group (`G1`)
    sheet_of: dict[str, str]  # node id -> sheet group (`3:1`)
    sheet_count: int


def assign_unit_sheets(unit_no: int, instance: PatternInstance, knobs: SheetKnobs) -> UnitSheets:
    """Give every node of the unit's plan a pattern group and a sheet."""
    group_of = rider_groups(instance.plan, instance.drawing_group_of)
    sizes = group_sizes(instance.plan, group_of)
    sheets = merge_groups(sizes, instance.pinned_groups, knobs)
    sheet_of_group = {
        name: f"{unit_no}:{number}"
        for number, names in enumerate(sheets, start=1)
        for name in names
    }
    return UnitSheets(
        group_of=group_of,
        sheet_of={node_id: sheet_of_group[name] for node_id, name in group_of.items()},
        sheet_count=len(sheets),
    )


# ---- step 2: the rider rule ----------------------------------------------------------------------


def rider_groups(plan: TrimPlan, equipment_group: Mapping[str, str]) -> dict[str, str]:
    """The group of every equipment, inline part and instrument of the plan."""
    group = dict(equipment_group)
    for line in plan.lines:  # in plan order: a branch's tee is on an earlier line
        line_group = _line_group(line, group)
        for item in line.items:
            group[item.node_id] = line_group
    group.update(_loop_groups(plan, group))
    return group


def _line_group(line: LineSpec, group: Mapping[str, str]) -> str:
    """The group of the line's source; its destination when the source is open or another unit's."""
    for end in (line.src_id, line.dst_id):
        if end is not None and end in group:
            return group[end]
    raise ValueError(
        f"line {line.line_number!r} has neither end in a known group "
        f"(src_id={line.src_id!r}, dst_id={line.dst_id!r}); expected a line that starts at, or "
        "ends at, equipment or a part of an earlier line of its unit"
    )


def _loop_groups(plan: TrimPlan, group: Mapping[str, str]) -> dict[str, str]:
    """Each instrument takes the group of its loop's anchor: where the loop's sensor is located.

    A loop without a sensor (a hand switch starting a machine) is anchored at the machine it acts
    on. Loop members share a loop tag.
    """
    anchor: dict[str, str] = {}
    loop_of = {instrument.node_id: instrument.loop_tag for instrument in plan.instruments}
    for link in plan.links:
        if link.relation is Relation.MEASURED_BY:  # source: the sensed item, target: the sensor
            anchor.setdefault(loop_of[link.target_id], group[link.source_id])
    for link in plan.links:
        if link.relation is Relation.CONTROL:  # source: the actuator, target: valve or machine
            anchor.setdefault(loop_of[link.source_id], group[link.target_id])
    unanchored = sorted(set(loop_of.values()) - set(anchor))
    if unanchored:
        raise ValueError(
            f"loops {unanchored} have no sensing location and control nothing; every loop needs "
            "a measured_by or a control link to be placed on a sheet"
        )
    return {node_id: anchor[loop_tag] for node_id, loop_tag in loop_of.items()}


# ---- step 3: the merge ---------------------------------------------------------------------------


def group_sizes(plan: TrimPlan, group_of: Mapping[str, str]) -> dict[str, GroupSize]:
    """Equipment and drawn symbols per pattern group, before any merge."""
    classes = plan_node_classes(plan)
    equipment: dict[str, int] = {}
    symbols: dict[str, int] = {}
    for node_id, name in group_of.items():
        node_class = classes[node_id]
        equipment[name] = equipment.get(name, 0) + (symbol_kind(node_class) is SymbolKind.EQUIPMENT)
        symbols[name] = symbols.get(name, 0) + is_symbol(node_class)
    return {name: GroupSize(equipment=equipment[name], symbols=symbols[name]) for name in symbols}


def merge_groups(
    sizes: Mapping[str, GroupSize], pinned: frozenset[str], knobs: SheetKnobs
) -> list[list[str]]:
    """The sheets of a unit: runs of consecutive groups that fit the caps together."""
    sheets: list[list[str]] = []
    for name in sorted(sizes, key=_group_order):
        if sheets and _fits(sheets[-1], name, sizes, pinned, knobs):
            sheets[-1].append(name)
        else:
            sheets.append([name])
    return sheets


def _group_order(name: str) -> int:
    """`G2` sorts before `G10`: the groups are numbered in flow order."""
    if not (name.startswith("G") and name[1:].isdigit()):
        raise ValueError(f"expected a drawing group named G<number>, got {name!r}")
    return int(name[1:])


def _fits(
    sheet: list[str],
    name: str,
    sizes: Mapping[str, GroupSize],
    pinned: frozenset[str],
    knobs: SheetKnobs,
) -> bool:
    if name in pinned or any(member in pinned for member in sheet):
        return False
    members = [*sheet, name]
    equipment = sum(sizes[member].equipment for member in members)
    symbols = sum(sizes[member].symbols for member in members)
    return equipment <= knobs.max_equipment_per_sheet and symbols <= knobs.max_symbols_before_stubs
