"""Sheet composition: pattern groups, the rider rule and the merge (design realism 9)."""

from __future__ import annotations

import pytest
from pattern_harness import PatternHarness, config_with

from plantgraph.benchmark.v2.config import SheetKnobs
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.separation import build_flash_drum
from plantgraph.benchmark.v2.patterns.storage import build_tank_farm
from plantgraph.benchmark.v2.plan_models import InstrumentSpec
from plantgraph.benchmark.v2.sheets import (
    GroupSize,
    assign_unit_sheets,
    merge_groups,
    rider_groups,
)
from plantgraph.benchmark.v2.symbols import plan_node_classes
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.graph.schema import Relation

NO_PIN: frozenset[str] = frozenset()


def _sizes(**by_group: tuple[int, int]) -> dict[str, GroupSize]:
    return {name: GroupSize(equipment=e, symbols=s) for name, (e, s) in by_group.items()}


# ---- the merge -----------------------------------------------------------------------------------


def test_groups_that_fit_the_caps_share_a_sheet_in_flow_order() -> None:
    sizes = _sizes(G1=(2, 30), G2=(3, 30), G10=(1, 20))
    assert merge_groups(sizes, NO_PIN, SheetKnobs()) == [["G1", "G2", "G10"]]  # G10 sorts last


def test_the_symbol_cap_starts_a_new_sheet() -> None:
    sizes = _sizes(G1=(2, 60), G2=(2, 50), G3=(2, 20))
    assert merge_groups(sizes, NO_PIN, SheetKnobs(max_symbols_before_stubs=100)) == [
        ["G1"],
        ["G2", "G3"],
    ]


def test_the_equipment_cap_starts_a_new_sheet() -> None:
    sizes = _sizes(G1=(6, 10), G2=(5, 10), G3=(5, 10))
    knobs = SheetKnobs(max_equipment_per_sheet=10)
    assert merge_groups(sizes, NO_PIN, knobs) == [["G1"], ["G2", "G3"]]


def test_a_pinned_group_is_never_merged_in_either_direction() -> None:
    sizes = _sizes(G1=(1, 5), G2=(1, 5), G3=(1, 5))
    assert merge_groups(sizes, frozenset({"G2"}), SheetKnobs()) == [["G1"], ["G2"], ["G3"]]


def test_a_group_over_the_caps_is_kept_whole_on_a_sheet_of_its_own() -> None:
    sizes = _sizes(G1=(3, 150), G2=(1, 5))
    assert merge_groups(sizes, NO_PIN, SheetKnobs()) == [["G1"], ["G2"]]


def test_a_group_name_that_is_not_g_number_is_refused() -> None:
    with pytest.raises(ValueError, match="expected a drawing group named G<number>, got 'left'"):
        merge_groups(_sizes(left=(1, 1)), NO_PIN, SheetKnobs())


# ---- the rider rule on real patterns -------------------------------------------------------------


def _drum(**pump_deck: tuple[str, ...]) -> PatternInstance:
    h = PatternHarness(deck_cards=dict(pump_deck) or None)
    return build_flash_drum(h.pctx)


def test_every_node_of_a_unit_gets_a_group_and_equipment_keeps_the_patterns_group() -> None:
    drum = _drum()
    groups = rider_groups(drum.plan, drum.drawing_group_of)
    assert set(groups) == set(plan_node_classes(drum.plan))
    assert all(groups[node] == group for node, group in drum.drawing_group_of.items())


def test_a_lines_parts_take_the_group_of_its_source_even_when_the_pump_is_elsewhere() -> None:
    """Own-sheet pumps: the suction trim stays on the drum's sheet, the discharge trim moves."""
    drum = _drum(**{"pump_set.group": ("own_sheet",)})
    assert drum.pinned_groups == frozenset({"G2"})
    groups = rider_groups(drum.plan, drum.drawing_group_of)
    pump = next(e.node_id for e in drum.plan.equipment if e.node_class == "CentrifugalPump")
    suction = next(
        line
        for line in drum.plan.lines
        if line.dst_id == pump and line.items  # vessel -> pump
    )
    discharge = next(line for line in drum.plan.lines if line.src_id == pump and line.items)
    assert {groups[item.node_id] for item in suction.items} == {"G1"}
    assert {groups[item.node_id] for item in discharge.items} == {"G2"}


def test_a_loop_lands_where_its_sensor_is_located() -> None:
    drum = _drum(**{"pump_set.group": ("own_sheet",)})
    groups = rider_groups(drum.plan, drum.drawing_group_of)
    sensed = {
        link.target_id: link.source_id
        for link in drum.plan.links
        if link.relation is Relation.MEASURED_BY
    }
    assert sensed
    for sensor, location in sensed.items():
        assert groups[sensor] == groups[location]
    members = {i.node_id: i.loop_tag for i in drum.plan.instruments}
    by_loop: dict[str, set[str]] = {}
    for node_id, loop_tag in members.items():
        by_loop.setdefault(loop_tag, set()).add(groups[node_id])
    assert all(len(found) == 1 for found in by_loop.values())  # a loop is never split


def test_a_hand_switch_loop_is_anchored_at_its_machine() -> None:
    drum = _drum()
    groups = rider_groups(drum.plan, drum.drawing_group_of)
    machine_control = [
        link
        for link in drum.plan.links
        if link.relation is Relation.CONTROL
        and link.target_id in {e.node_id for e in drum.plan.equipment}
    ]
    assert machine_control
    for link in machine_control:
        assert groups[link.source_id] == groups[link.target_id]


def test_a_loop_with_no_sensor_and_no_control_cannot_be_placed() -> None:
    drum = _drum()
    stray = InstrumentSpec(
        node_id="stray",
        node_class="ProcessInstrumentationFunction",
        unit_no=1,
        tag="PIC-1999",
        loop_tag="PIC-1999",
        measured_variable="P",
    )
    plan = drum.plan.model_copy(update={"instruments": (*drum.plan.instruments, stray)})
    with pytest.raises(ValueError, match=r"loops \['PIC-1999'\] have no sensing location"):
        rider_groups(plan, drum.drawing_group_of)


def test_a_line_whose_ends_are_both_unknown_is_refused_with_its_ends() -> None:
    drum = _drum()
    line = drum.plan.lines[0].model_copy(update={"src_id": "ghost", "dst_id": "ghost2"})
    plan = TrimPlan(lines=(line,))
    with pytest.raises(ValueError, match="neither end in a known group.*'ghost'"):
        rider_groups(plan, {})


def test_a_line_fed_from_another_unit_takes_the_group_of_its_destination() -> None:
    drum = _drum()
    feed = drum.port("feed")
    joined_line = next(line for line in drum.plan.lines if line.line_number == feed.line_number)
    foreign = joined_line.model_copy(update={"src_id": "other-unit-node"})
    plan = drum.plan.model_copy(
        update={
            "lines": tuple(foreign if line is joined_line else line for line in drum.plan.lines)
        }
    )
    groups = rider_groups(plan, drum.drawing_group_of)
    assert groups[feed.node_id] == "G1"  # the drum's group, not a key error for the foreign node


# ---- assign_unit_sheets --------------------------------------------------------------------------


def test_sheet_labels_are_unit_then_number_and_cover_every_node() -> None:
    drum = _drum(**{"pump_set.group": ("own_sheet",)})
    result = assign_unit_sheets(7, drum, SheetKnobs())
    assert set(result.sheet_of) == set(plan_node_classes(drum.plan))
    assert set(result.sheet_of.values()) == {"7:1", "7:2"} and result.sheet_count == 2


def test_a_unit_with_room_for_everything_is_one_sheet_only_when_the_caps_allow() -> None:
    drum = _drum(**{"pump_set.group": ("with_suction_vessel",)})
    assert assign_unit_sheets(1, drum, SheetKnobs()).sheet_count == 1


def test_a_tank_farm_splits_two_tanks_per_group_and_merges_by_the_caps() -> None:
    config = config_with(patterns={"p_single_pump": 0.0})  # a spared set can have its own sheet
    h = PatternHarness(
        config=config, deck_cards={"U4.tank_count": ("4",), "pump_set.group": ("own_sheet",)}
    )
    farm = build_tank_farm(h.pctx)
    wide = assign_unit_sheets(1, farm, SheetKnobs(max_symbols_before_stubs=1000))
    assert wide.sheet_count == 2  # G1 and G2 merge, the pinned pump group stays apart
    narrow = assign_unit_sheets(1, farm, SheetKnobs(max_symbols_before_stubs=1))
    assert narrow.sheet_count == 3 and narrow.sheet_of != wide.sheet_of
