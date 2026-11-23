"""Task T7a: battery limits close the plant boundary, and unpaired reactor gas is make-up gas.

Design 17.4. The plants are the 30-sheet plants of seeds 1-5. Before T7a the closure check found 127
open ends there (28, 26, 27, 22, 24); 69 were plant-boundary ends and 58 relief outlets and
fuel-gas bleeds. The 69 are closed here; T7 closed the 58 (`test_network_t7.py`).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import cast

import pytest
from t9_support import SEEDS, units_for_30_sheets, view_v21, view_v22

from plantgraph.benchmark.v2 import planner
from plantgraph.benchmark.v2.boundary import END_FITTINGS, close_plant_boundary
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.patterns.ports import PortKind
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.rules.checks_closure import check_stream_closure
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trims_valves import BATTERY_LIMIT_ROLES

#: what T7a left to T7: relief outlets and fuel-gas bleeds (10, 13, 12, 9, 14 open ends, 58 in all)
_T7_ROLES = {"psv_outlet_block", "dbb_bleed_valve"}


def _plan(seed: int) -> PlantPlanV2:
    return plan_plant(GeneratorConfigV22(seed=seed, n_units=units_for_30_sheets(seed)))


@contextmanager
def _networks_off() -> Iterator[None]:
    """The planner without the network pass: the plan the boundary pass left (T7a's state)."""
    original = planner.add_networks
    planner.add_networks = lambda config, slots, instances, trims, trains, decks: (instances, [])
    try:
        yield
    finally:
        planner.add_networks = original


@contextmanager
def _boundary_off() -> Iterator[None]:
    """The planner without the boundary pass: what T9c left, the baseline of the 'before' counts."""
    original = planner.close_plant_boundary
    planner.close_plant_boundary = lambda instances, trims, style: list(instances)
    try:
        yield
    finally:
        planner.close_plant_boundary = original


# ---- positive: what the check still reports -----------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_no_open_end_is_left_but_if_one_were_it_is_a_relief_outlet_or_bleed(seed: int) -> None:
    view = view_v22(seed)
    roles = {view.roles.get(v.node_id) for v in check_stream_closure(view).violations}
    assert roles <= _T7_ROLES


def test_t7_closed_the_58_open_ends_t7a_left() -> None:
    """The 58 relief outlets and bleeds now tie into network headers: the check finds none."""
    found = [len(check_stream_closure(view_v22(seed)).violations) for seed in SEEDS]
    assert found == [0, 0, 0, 0, 0]


def test_every_process_line_end_is_a_battery_limit_a_vent_or_joined() -> None:
    for seed in SEEDS:
        plan = _plan(seed)
        for unit in plan.units:
            kinds = unit.instance.plan.stream_kinds
            for line in unit.instance.plan.lines:
                if kinds.get(line.line_number) is StreamKindV2.PROCESS and line.src_id is None:
                    roles = [unit.instance.plan.roles.get(i.node_id) for i in line.items[:2]]
                    assert set(roles) & BATTERY_LIMIT_ROLES, (seed, line.line_number)


# ---- positive: make-up gas ----------------------------------------------------------------------


def test_an_unpaired_reactor_recycle_port_is_make_up_gas_over_a_battery_limit() -> None:
    found = 0
    for seed in SEEDS:
        view = view_v22(seed)
        for unit in view.plan.units:
            roles = unit.instance.plan.roles
            if "makeup_gas_block" not in roles.values():
                continue
            found += 1
            port = unit.instance.port("recycle_gas")
            line = next(x for x in unit.instance.plan.lines if x.line_number == port.line_number)
            assert unit.instance.plan.stream_kinds[line.line_number] is StreamKindV2.PROCESS
            assert port.kind is PortKind.PROCESS
            assert roles[line.items[0].node_id] in BATTERY_LIMIT_ROLES
            assert "makeup_gas_check" in {roles.get(i.node_id) for i in line.items}
            assert "recycle_gas_block" not in roles.values()
    assert found == 6  # design 17.4: 8 open recycle ports, 2 closed by T9c


def test_a_paired_recycle_port_keeps_its_recycle_roles_and_kind() -> None:
    for seed in SEEDS:
        for unit in view_v22(seed).plan.units:
            if "recycle_gas_block" in unit.instance.plan.roles.values():
                assert unit.instance.port("recycle_gas").kind is PortKind.RECYCLE


# ---- the draws and the parts that existed -------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 3])
def test_the_pass_only_adds_parts_so_every_existing_part_keeps_its_id_tag_and_order(
    seed: int,
) -> None:
    with _networks_off():
        with _boundary_off():
            before = _plan(seed)
        after = _plan(seed)
    for old, new in zip(before.units, after.units, strict=True):
        assert [e.node_id for e in old.instance.plan.equipment] == [
            e.node_id for e in new.instance.plan.equipment
        ]
        for old_line, new_line in zip(
            old.instance.plan.lines, new.instance.plan.lines, strict=True
        ):
            kept = [i for i in new_line.items if i in old_line.items]
            assert kept == list(old_line.items), old_line.line_number


@pytest.mark.parametrize("seed", [1, 4, 5])
def test_a_line_that_ends_at_a_vent_fitting_gets_no_battery_limit(seed: int) -> None:
    with _boundary_off():
        before = _plan(seed)
    after = _plan(seed)
    vents = 0
    for old, new in zip(before.units, after.units, strict=True):
        for old_line, new_line in zip(
            old.instance.plan.lines, new.instance.plan.lines, strict=True
        ):
            if old_line.dst_id is None and old_line.items[-1].node_class in END_FITTINGS:
                vents += 1
                assert new_line.items[-1] == old_line.items[-1]
    assert vents > 0


def test_the_part_ids_of_a_unit_stay_unique_after_the_pass() -> None:
    for unit in _plan(2).units:
        ids = [i.node_id for line in unit.instance.plan.lines for i in line.items]
        ids += [e.node_id for e in unit.instance.plan.equipment]
        assert len(ids) == len(set(ids))


def test_the_plan_is_deterministic() -> None:
    first = _plan(3).model_dump(mode="json", exclude={"config"})
    assert first == _plan(3).model_dump(mode="json", exclude={"config"})


def test_the_new_parts_are_on_sheets() -> None:
    plan = _plan(2)
    for unit in plan.units:
        nodes = {i.node_id for line in unit.instance.plan.lines for i in line.items}
        assert nodes <= set(unit.sheets.sheet_of)


# ---- mutations: the pass and the check must notice a missing closure -----------------------------


def test_closing_an_already_closed_plant_adds_nothing() -> None:
    """The second pass sees a limit at every end and draws nothing (a None trim would crash)."""
    with _networks_off():
        instances = [unit.instance for unit in _plan(1).units]
    nothing = cast(list[TrimContext], [None] * len(instances))
    again = close_plant_boundary(instances, nothing, LineStyle(size=6))
    assert again == instances


def test_without_the_pass_some_process_source_ends_have_no_battery_limit() -> None:
    """The baseline the pass starts from: the unmodified plan has bare entries."""
    with _boundary_off():
        plan = _plan(1)
    bare = 0
    for unit in plan.units:
        for line in unit.instance.plan.lines:
            if unit.instance.plan.stream_kinds.get(line.line_number) is not StreamKindV2.PROCESS:
                continue
            roles = {unit.instance.plan.roles.get(i.node_id) for i in line.items[:2]}
            bare += line.src_id is None and not roles & BATTERY_LIMIT_ROLES
    assert bare > 0


def test_cutting_the_make_up_gas_battery_limit_reopens_the_end() -> None:
    view = next(v for v in map(view_v22, SEEDS) if "makeup_gas_block" in v.roles.values())
    graph = view.graph.copy()
    graph.remove_nodes_from([n for n, role in view.roles.items() if role in BATTERY_LIMIT_ROLES])
    ends = {v.node_id for v in check_stream_closure(replace(view, graph=graph)).violations}
    block = next(n for n, role in view.roles.items() if role == "makeup_gas_block")
    assert block in ends


# ---- version gates ------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_a_v21_plant_has_no_make_up_gas_and_keeps_its_recycle_ports(seed: int) -> None:
    view = view_v21(seed)
    assert "makeup_gas_block" not in view.roles.values()
    for unit in view.plan.units:
        if unit.instance.pattern == "U3":
            assert unit.instance.port("recycle_gas").kind is PortKind.RECYCLE


def test_a_v21_plant_has_only_the_battery_limits_its_coin_drew() -> None:
    """v2.1 draws p_battery_limit per end; the forced pass would show as more limits than ends."""
    view = view_v21(1)
    counts = Counter(role for role in view.roles.values() if role in BATTERY_LIMIT_ROLES)
    assert counts["battery_limit_block"] == counts["battery_limit_blind"]
    ends = check_stream_closure(view)
    assert ends.violations  # v2.1 still has open ends: the pass never ran there
