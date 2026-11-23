"""Per-sheet composition: the stub rule (Q7 A), the counting rule and the sheet bands."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from plant_v2 import generated

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.sheet_stats import (
    CLOSED_END_CLASSES,
    SheetStats,
    open_end_stubs,
    share_at_most,
    sheet_stats,
    spread,
    wired_out_ends,
)
from plantgraph.benchmark.v2.symbols import SymbolKind, is_symbol, symbol_kind
from plantgraph.graph.schema import EQUIPMENT_CLASSES

SEEDS = range(1, 9)
UNITS = 40


def _all_stats() -> list[SheetStats]:
    return [
        s
        for seed in SEEDS
        for s in sheet_stats(plan_plant(GeneratorConfigV2(seed=seed, n_units=UNITS)))
    ]


def test_the_counting_rule_excludes_tees_breaks_and_actuators() -> None:
    assert symbol_kind("PipeTee") is SymbolKind.JUNCTION and not is_symbol("PipeTee")
    assert not is_symbol("PropertyBreak") and not is_symbol("ActuatingFunction")
    assert is_symbol("GateValve") and is_symbol("CentrifugalPump")
    assert is_symbol("ProcessSignalGeneratingFunction")
    assert is_symbol("FlowMeasuringElement")  # a primary element is drawn


def test_the_sheet_equipment_adds_up_to_the_plants_equipment() -> None:
    plan = generated(3, 20).plan
    stats = sheet_stats(plan)
    graph, _ = generated(3, 20).graph()
    assert sum(s.equipment for s in stats) == sum(
        d["node_class"] in EQUIPMENT_CLASSES for _, d in graph.nodes(data=True)
    )
    assert len(stats) == plan.sheet_count
    assert all(
        s.symbols == s.equipment + s.valves + s.fittings + s.instruments + s.stubs for s in stats
    )


def test_stubs_cover_the_open_ends_that_are_not_closed_and_skip_the_closed_ones() -> None:
    """Total stubs are at least the open ends not closed by a flange, funnel or vent (Q7 A)."""
    plan = generated(3, 20).plan
    open_ends = 0
    for unit in plan.units:
        classes = {i.node_id: i.node_class for line in unit.instance.plan.lines for i in line.items}
        for line in unit.instance.plan.lines:
            if line.src_id is None:
                open_ends += classes[line.items[0].node_id] not in CLOSED_END_CLASSES
            if line.dst_id is None:
                open_ends += classes[line.items[-1].node_id] not in CLOSED_END_CLASSES
    total = sum(s.stubs for s in sheet_stats(plan))
    assert total >= open_ends  # crossings come on top
    closed = sum(
        1
        for unit in plan.units
        for line in unit.instance.plan.lines
        if line.dst_id is None and line.items and line.items[-1].node_class in CLOSED_END_CLASSES
    )
    assert closed > 0  # the fixture does contain closed vent/drain ends the rule must skip


def test_equipment_per_sheet_is_within_1_to_16_and_at_least_90_percent_within_10() -> None:
    equipment = [s.equipment for s in _all_stats()]
    assert min(equipment) >= 1 and max(equipment) <= 16
    assert share_at_most(equipment, 10) >= 0.9


def test_every_sheet_shows_one_unit() -> None:
    for seed in SEEDS:
        plan = plan_plant(GeneratorConfigV2(seed=seed, n_units=UNITS))
        for unit in plan.units:
            assert {s.split(":")[0] for s in unit.sheets.sheet_of.values()} == {
                str(unit.slot.unit_no)
            }


def test_the_mean_symbols_per_sheet_is_inside_the_design_band() -> None:
    mean = spread([s.symbols for s in _all_stats()]).mean
    assert 56 <= mean <= 109


def test_a_controller_bubble_is_an_instrument_symbol() -> None:
    """`ProcessControlFunction` (pyDEXPI: a subclass of the instrumentation function) is drawn."""
    assert symbol_kind("ProcessControlFunction") is SymbolKind.INSTRUMENT
    assert is_symbol("ProcessControlFunction")


def test_a_wired_out_port_counts_one_stub_not_an_open_end_plus_a_crossing() -> None:
    """Seed 1, 60 units: 80 out-ports are wired; v2 counted 697 stubs, v2.1 counts 617.

    612 after F8c, which changed the plant itself (new draw order in U5, new tees in U3). After
    review R2 (an end counts as wired only when a line of another unit starts from it, farm
    receipts without a merge header, tap services): 76 wired ends, 611 stubs.
    """
    plan = plan_plant(GeneratorConfigV2(seed=1, n_units=60))
    assert len(wired_out_ends(plan)) == 76
    assert sum(s.stubs for s in sheet_stats(plan)) == 611


def _fake_plan(units: dict[int, list[LineSpec]]) -> Any:
    """The part of a plant plan `wired_out_ends` reads: units with a number and their lines."""
    return SimpleNamespace(
        units=[
            SimpleNamespace(slot=SimpleNamespace(unit_no=no), instance=SimpleNamespace(plan=plan))
            for no, plan in (
                (no, SimpleNamespace(lines=lines, roles={})) for no, lines in units.items()
            )
        ],
        network_units=[],
    )


def _open_line(unit: int, number: int, src: str | None, last: str, dst: str | None) -> LineSpec:
    return LineSpec(
        line_number=f"4-P-{unit}{number:04d}-A1A-N",
        fluid_code="P",
        unit_no=unit,
        src_id=src,
        dst_id=dst,
        items=(LineItemSpec(node_id=last, node_class="GateValve"),),
    )


def test_an_end_is_wired_only_when_a_line_of_another_unit_starts_from_it() -> None:
    """R2: a branch of the same unit starting at a line's last part does not wire that end."""
    own_branch = _open_line(1, 2, "end1", "tap", None)
    other_unit = _open_line(2, 1, "end2", "far", None)
    plan = _fake_plan(
        {
            1: [_open_line(1, 1, "tank", "end1", None), own_branch],
            2: [_open_line(2, 2, "pump", "end2", None)],
            3: [other_unit],
        }
    )
    assert wired_out_ends(plan) == frozenset({"end2"})  # end1's only starter is its own unit


def test_seed_1_300_units_counts_370_wired_ends_not_386() -> None:
    """The old rule counted 16 ends as wired that only a line of their own unit starts from."""
    assert len(wired_out_ends(plan_plant(GeneratorConfigV2(seed=1, n_units=300)))) == 370


def test_an_open_line_end_is_a_stub_unless_a_later_line_starts_from_it() -> None:
    line = LineSpec(
        line_number="6-P-10001-A1A-N",
        fluid_code="P",
        unit_no=1,
        src_id="tank",
        dst_id=None,
        items=(LineItemSpec(node_id="valve", node_class="GateValve"),),
    )
    sheet_of = {"tank": "1:1", "valve": "1:1"}
    classes = {"tank": "Tank", "valve": "GateValve"}
    assert open_end_stubs(line, sheet_of, classes, frozenset()) == ["1:1"]
    assert open_end_stubs(line, sheet_of, classes, frozenset({"valve"})) == []
