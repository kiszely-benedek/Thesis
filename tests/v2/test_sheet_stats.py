"""Per-sheet composition: the stub rule (Q7 A), the counting rule and the sheet bands."""

from __future__ import annotations

from plant_v2 import generated

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.sheet_stats import (
    CLOSED_END_CLASSES,
    SheetStats,
    share_at_most,
    sheet_stats,
    spread,
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
