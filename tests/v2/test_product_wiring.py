"""Generator v2.1 flowsheet wiring: a column's products end in a tank farm; the sheet cap holds.

v2 left every column distillate and side draw as an open stub (0 of 61 and 0 of 10 on seed 1,
300 units). A product farm now takes the liquid streams its train left open, through extra receipt
lines; the combined-column layout reads the plant's own equipment cap per sheet.
"""

from __future__ import annotations

from dataclasses import replace
from functools import cache

import pytest
from pattern_harness import PatternHarness
from trim_harness import ids_with_role

from plantgraph.benchmark.v2.config import GeneratorConfigV2, SheetKnobs
from plantgraph.benchmark.v2.flowsheet import OpenOut, wire
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.benchmark.v2.patterns.storage import build_tank_farm
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.symbols import SymbolKind, plan_node_classes, symbol_kind

_PRODUCT_PORTS = ("distillate", "side_draw")


@cache
def _plan(seed: int, n_units: int, cap: int = 16) -> PlantPlanV2:
    sheets = SheetKnobs(max_equipment_per_sheet=cap)
    return plan_plant(GeneratorConfigV2(seed=seed, n_units=n_units, sheets=sheets))


def _consumed_sources(plan: PlantPlanV2) -> set[str]:
    return {line.src_id for unit in plan.units for line in unit.instance.plan.lines if line.src_id}


def _wired_counts(plan: PlantPlanV2, port_name: str) -> tuple[int, int]:
    """(ports with a consumer, all ports) of the given name over the whole plant."""
    sources = _consumed_sources(plan)
    nodes = [p.node_id for u in plan.units for p in u.instance.ports if p.name == port_name]
    return sum(node in sources for node in nodes), len(nodes)


# ---- the seeded plant ----------------------------------------------------------------------------


def test_every_distillate_and_side_draw_has_a_consumer_on_the_dev_seed_plant() -> None:
    plan = _plan(1, 300)
    assert _wired_counts(plan, "distillate") == (61, 61)
    assert _wired_counts(plan, "side_draw") == (10, 10)


def test_the_wired_products_leave_fewer_open_stubs_and_only_gas_stays_open() -> None:
    plan = _plan(1, 300)
    assert plan.open_stub_count == 147  # v2 had 218: the 71 products were open
    sources = _consumed_sources(plan)
    open_liquid = [
        (u.slot.pattern_id, p.name)
        for u in plan.units
        for p in u.instance.ports
        if p.direction is PortDirection.OUT and p.phase is Phase.LIQUID and p.node_id not in sources
    ]
    assert open_liquid == [("U4", "transfer")]  # the last farm's transfer line: nothing follows it


def test_a_farm_has_a_receipt_line_for_every_product_stream_of_its_train() -> None:
    plan = _plan(1, 300)
    most = max(sum(p.name.startswith("receipt") for p in u.instance.ports) for u in plan.units)
    assert most > 2  # v2 farms had at most 2 receipt lines


def test_the_plant_cap_on_equipment_per_sheet_holds_for_combined_columns() -> None:
    """Cap 8: v2 judged 'fits' against the default 16, so combined columns of 9-16 items stayed."""
    plan = _plan(1, 300, cap=8)
    per_sheet: dict[str, int] = {}
    for unit in plan.units:
        classes = plan_node_classes(unit.instance.plan)
        for node_id, sheet in unit.sheets.sheet_of.items():
            if symbol_kind(classes[node_id]) is SymbolKind.EQUIPMENT:
                per_sheet[sheet] = per_sheet.get(sheet, 0) + 1
    assert [name for name, count in per_sheet.items() if count > 8] == []


# ---- the join rule -------------------------------------------------------------------------------


def _farm(waiting: int) -> PatternInstance:
    h = PatternHarness(0)
    return build_tank_farm(replace(h.pctx, waiting_streams=waiting))


def _open_out(unit_no: int, train_no: int, name: str, instance: PatternInstance) -> OpenOut:
    return OpenOut(unit_no=unit_no, train_no=train_no, port=instance.port(name))


def _source_of(instance: PatternInstance, in_port_name: str) -> str | None:
    number = instance.port(in_port_name).line_number
    return next(line.src_id for line in instance.plan.lines if line.line_number == number)


def test_a_farm_with_streams_waiting_gets_that_many_receipts_and_merge_tees() -> None:
    farm = _farm(waiting=4)
    names = [p.name for p in farm.ports if p.direction is PortDirection.IN]
    assert names == ["receipt1", "receipt2", "receipt3", "receipt4"]
    assert len(ids_with_role(farm.plan, "receipt_merge_tee")) == 3
    assert all(p.collects for p in farm.ports if p.direction is PortDirection.IN)


def test_a_farm_with_nothing_waiting_keeps_its_drawn_one_or_two_receipts() -> None:
    receipts = {sum(p.name.startswith("receipt") for p in _farm(0).ports)}
    assert receipts <= {1, 2}


def test_a_collecting_receipt_takes_only_open_liquid_streams_of_its_own_train() -> None:
    farm = _farm(waiting=3)
    donor = _farm(waiting=0)  # any pattern with a liquid out-port will do
    outs = (
        _open_out(1, 1, "transfer", donor),  # an earlier train: out of reach for receipt2
        _open_out(2, 2, "transfer", donor),
        _open_out(3, 2, "transfer", donor),
    )
    wired, remaining = wire(farm, 4, outs, train_no=2)
    assert _source_of(wired, "receipt1") == outs[2].port.node_id  # the latest, as always
    assert _source_of(wired, "receipt2") == outs[1].port.node_id  # same train
    assert _source_of(wired, "receipt3") is None  # the only other stream is a train away
    assert [out.unit_no for out in remaining if out.train_no == 1] == [1]


@pytest.mark.parametrize("seed", [2, 3])
def test_other_seeds_wire_every_product_before_the_last_farm(seed: int) -> None:
    plan = _plan(seed, 120)
    last_farm = max(u.slot.unit_no for u in plan.units if u.slot.pattern_id == "U4")
    sources = _consumed_sources(plan)
    unwired = [
        (u.slot.unit_no, p.name)
        for u in plan.units
        if u.slot.unit_no < last_farm
        for p in u.instance.ports
        if p.name in _PRODUCT_PORTS and p.node_id not in sources
    ]
    assert unwired == []
