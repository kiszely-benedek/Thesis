"""The hidden pressure levels (design 6.2) and the spec break behind a pump or compressor.

The levels are a pure function of the plan, so each rule is read back from a generated plant: a
pump lifts by one level, a compressor by two, a letdown lowers by one, a vessel stands one level
below its feed (never under atmospheric), and what a vacuum machine pulls on is at vacuum.
"""

from __future__ import annotations

import pytest
from plant_invariants import plant_view_v22

from plantgraph.benchmark.v2.hidden_state import PressureLevel
from plantgraph.benchmark.v2.pressure_levels import (
    COMPRESSOR_CLASSES,
    PROCESS_SERVICES,
    PUMP_CLASSES,
    UTILITY_LEVEL,
    VESSEL_CLASSES,
    assign_pressure_levels,
    is_vacuum_machine,
)
from plantgraph.benchmark.v2.rules.checks_pressure import edge_level
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.benchmark.v2.trim_context import LineStyle
from plantgraph.benchmark.v2.trims_machine import DISCHARGE_BREAK_ROLE, heavier_spec
from plantgraph.benchmark.v2.vocabulary import LINE_SPECS
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]


def _view(seed: int) -> RuleView:
    return plant_view_v22(seed, smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units)


def _class(view: RuleView, node: str) -> str:
    return str(view.graph.nodes[node]["node_class"])


def _discharge_breaks(view: RuleView, machine: str) -> list[str]:
    """The spec breaks right behind a machine (past its nozzle parts, before any equipment)."""
    found = []
    for node in view.piping.successors(machine):
        while view.roles.get(node) != DISCHARGE_BREAK_ROLE:
            following = list(view.piping.successors(node))
            if len(following) != 1 or _class(view, node) in EQUIPMENT_CLASSES:
                break
            node = following[0]
        else:
            found.append(node)
    return found


def _breaks_behind_machines(view: RuleView, classes: frozenset[str]) -> list[tuple[str, str, str]]:
    """(machine, its first suction part, its discharge break) for every machine of `classes`."""
    machines = sorted(n for n in view.piping if _class(view, n) in classes)
    return [
        (machine, next(iter(view.piping.predecessors(machine))), spec_break)
        for machine in machines
        if view.roles.get(machine) != "liquid_ring_pump"
        for spec_break in _discharge_breaks(view, machine)
    ]


def _break_levels(view: RuleView, spec_break: str) -> tuple[PressureLevel, PressureLevel]:
    (before,), (after,) = (
        list(view.piping.predecessors(spec_break)),
        list(view.piping.successors(spec_break)),
    )
    return edge_level(view, before, spec_break), edge_level(view, spec_break, after)


# ---- the levels of a whole plant ----------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_every_run_and_every_vessel_has_a_level(seed: int) -> None:
    view = _view(seed)
    levels = view.hidden.segment_level
    numbers = {
        n
        for unit_plan in view.plan.unit_plans
        for line in unit_plan.lines
        for n in line.line_numbers
    }
    vessels = {n for n in view.graph if _class(view, n) in VESSEL_CLASSES}
    assert set(levels) == numbers | vessels


def test_the_levels_are_the_same_every_time_they_are_assigned() -> None:
    view = _view(1)
    assert assign_pressure_levels(view.plan) == view.hidden.segment_level


@pytest.mark.parametrize("seed", SEEDS)
def test_a_utility_line_is_at_its_declared_level(seed: int) -> None:
    view = _view(seed)
    declared = 0
    for unit in view.plan.units:
        for line in unit.instance.plan.lines:
            if line.fluid_code in UTILITY_LEVEL:
                assert view.hidden.segment_level[line.line_number] == UTILITY_LEVEL[line.fluid_code]
                declared += 1
    assert declared > 0


@pytest.mark.parametrize("seed", SEEDS)
def test_a_tank_is_atmospheric_and_a_vessel_stands_below_every_process_feed(seed: int) -> None:
    view = _view(seed)
    levels = view.hidden.segment_level
    for node in (n for n in view.graph if _class(view, n) in VESSEL_CLASSES):
        if _class(view, node) == "Tank":
            assert levels[node] is PressureLevel.ATM
            continue
        feeds = [
            edge_level(view, s, node)
            for s in view.piping.predecessors(node)
            if view.graph.edges[s, node]["fluid_code"] in PROCESS_SERVICES
        ]
        assert all(levels[node] <= feed for feed in feeds), node


# ---- a machine lifts the level behind a spec break ---------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_a_pump_lifts_the_level_by_one_and_the_stub_before_the_break_stays_low(seed: int) -> None:
    view = _view(seed)
    pumps = _breaks_behind_machines(view, PUMP_CLASSES)
    assert pumps
    for pump, suction, spec_break in pumps:
        low, high = _break_levels(view, spec_break)
        assert low == edge_level(view, suction, pump), pump
        assert high == min(low + 1, PressureLevel.HP), pump


def test_a_compressor_lifts_the_level_by_two_across_the_five_seeds() -> None:
    lifts = []
    for seed in SEEDS:
        view = _view(seed)
        for _, _, spec_break in _breaks_behind_machines(view, COMPRESSOR_CLASSES):
            low, high = _break_levels(view, spec_break)
            lifts.append(high - low)
    assert lifts and set(lifts) == {2}


def test_a_vacuum_machine_pulls_a_vacuum_and_discharges_at_atmospheric() -> None:
    pulled = 0
    for seed in SEEDS:
        view = _view(seed)
        for machine in (
            n for n in view.piping if is_vacuum_machine(_class(view, n), view.roles.get(n))
        ):
            process = [
                s
                for s in view.piping.predecessors(machine)
                if view.graph.edges[s, machine]["fluid_code"] in PROCESS_SERVICES
            ]
            assert {edge_level(view, s, machine) for s in process} == {PressureLevel.VAC}
            pulled += 1
    assert pulled > 0


def test_a_letdown_lowers_the_level_by_one() -> None:
    drops = []
    for seed in SEEDS:
        view = _view(seed)
        for node in (n for n, r in view.roles.items() if r == "spec_break"):
            low, high = _break_levels(view, node)
            drops.append(low - high)
    assert drops and set(drops) == {1}


# ---- the spec break the generator draws behind a machine ----------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_the_line_behind_a_pump_break_is_the_next_heavier_class(seed: int) -> None:
    view = _view(seed)
    for _pump, _suction, spec_break in _breaks_behind_machines(view, PUMP_CLASSES):
        (before,), (after,) = (
            list(view.piping.predecessors(spec_break)),
            list(view.piping.successors(spec_break)),
        )
        rank_before = _rank(view.graph.edges[before, spec_break]["line_number"])
        rank_after = _rank(view.graph.edges[spec_break, after]["line_number"])
        assert rank_after == rank_before + 1


def _rank(number: str) -> int:
    parsed = parse_line_number(number)
    assert parsed is not None
    return LINE_SPECS.index(parsed.spec)


def test_heavier_spec_steps_one_class_up_and_refuses_the_heaviest() -> None:
    assert heavier_spec(LineStyle(size=6)).spec == "B1A"
    with pytest.raises(ValueError, match="expected a piping class below D1A"):
        heavier_spec(LineStyle(size=6, spec="D1A"))


def test_a_line_with_a_service_no_rule_knows_is_refused() -> None:
    view = _view(1)
    unit = view.plan.units[0]
    line = unit.instance.plan.lines[0].model_copy(update={"fluid_code": "ZZ"})
    plan = unit.instance.plan.model_copy(update={"lines": (line, *unit.instance.plan.lines[1:])})
    broken = unit.model_copy(update={"instance": unit.instance.model_copy(update={"plan": plan})})
    with pytest.raises(ValueError, match="expected a process or utility service, got 'ZZ'"):
        assign_pressure_levels(
            view.plan.model_copy(update={"units": (broken, *view.plan.units[1:])})
        )
