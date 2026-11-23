"""Task T7b, N1: a local sub-header continues an open end, so that end is not also a stub.

A sub-header (design 7) merges the tie-ins of one service on one process sheet into one pipe that
leaves the sheet through one connector. Counted by the T7 rules, its first (collection) or last
(distribution) tie-in showed up twice on the sheet: once as the connector and once as an open end.
These tests build the two small shapes by hand, then check a real v2.2 plant for the same defect.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, LineItemSpec, LineSpec
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.sheet_stats import fed_start_ends, sheet_stats, wired_out_ends
from plantgraph.benchmark.v2.symbols import plan_node_classes
from plantgraph.benchmark.v2.trim_plan import TrimPlan


def _item(node_id: str, node_class: str = "GateValve") -> LineItemSpec:
    return LineItemSpec(node_id=node_id, node_class=node_class)


def _line(number: int, src: str | None, items: list[str], dst: str | None) -> LineSpec:
    return LineSpec(
        line_number=f"4-FL-{number:05d}-A1A-N",
        fluid_code="FL",
        unit_no=1,
        src_id=src,
        dst_id=dst,
        items=tuple(_item(i, "PipeTee" if i.startswith("tee") else "GateValve") for i in items),
    )


def _vessel(node_id: str) -> EquipmentSpec:
    return EquipmentSpec(node_id=node_id, node_class="PressureVessel", unit_no=1, tag=node_id)


def _plant(process: list[LineSpec], network: list[LineSpec], header: list[str]) -> Any:
    """Just what `sheet_stats` reads: a process unit (`tee1` is a sub-header tee) and a header."""
    process_plan = TrimPlan(
        equipment=(_vessel("v1"), _vessel("v2")),
        lines=tuple(process),
        roles={"tee1": "sub_header_tee"},
    )
    network_plan = TrimPlan(lines=tuple(network), roles={})
    nodes = plan_node_classes(process_plan) | plan_node_classes(network_plan)
    sheet_of = {n: "9010:1" if n in header else "1:1" for n in nodes}
    process_unit = SimpleNamespace(
        slot=SimpleNamespace(unit_no=1), instance=SimpleNamespace(plan=process_plan)
    )
    return SimpleNamespace(
        units=[process_unit],
        network_units=[SimpleNamespace(unit_no=9010, plan=network_plan)],
        unit_plans=[process_plan, network_plan],
        sheet_of=sheet_of,
    )


def _collection() -> Any:
    """Two relief outlets `a` and `b` join a sub-header tee; the tee leaves for the flare header."""
    process = [
        _line(1, "v1", ["a"], None),
        _line(2, "v2", ["b"], None),
        _line(3, "a", ["tee1"], None),  # the sub-header: starts at the first tie-in
        _line(4, "b", [], "tee1"),  # the second tie-in runs into the tee
    ]
    network = [_line(5, None, ["htee", "hend"], None), _line(6, "tee1", [], "htee")]
    return _plant(process, network, ["htee", "hend"])


def _distribution() -> Any:
    """A header feeds a sub-header tee, which feeds two stubs `a` and `b`."""
    process = [
        _line(1, None, ["a"], "v1"),
        _line(2, None, ["b"], "v2"),
        _line(3, None, ["tee1"], "b"),  # the sub-header: ends at the last tie-in
        _line(4, "tee1", [], "a"),
    ]
    network = [_line(5, None, ["htee", "hend"], None), _line(6, "htee", ["root"], "tee1")]
    return _plant(process, network, ["htee", "hend", "root"])


def _process_sheet(plant: Any) -> Any:
    return next(s for s in sheet_stats(plant) if s.sheet_group == "1:1")


def test_a_collection_sub_header_with_two_tie_ins_is_one_connector_and_no_open_end() -> None:
    plant = _collection()
    assert wired_out_ends(plant) >= {"a", "b"}  # `a` is continued by the sub-header (the N1 fix)
    sheet = _process_sheet(plant)
    assert (sheet.crossings, sheet.stubs) == (1, 1)  # one connector, 0 open-end stubs


def test_a_distribution_sub_header_with_two_tie_ins_is_one_connector_and_no_open_end() -> None:
    plant = _distribution()
    assert fed_start_ends(plant) >= {"a", "b"}  # `b` is fed by the sub-header (the N1 fix)
    sheet = _process_sheet(plant)
    assert (sheet.crossings, sheet.stubs) == (1, 1)


def test_a_plain_open_end_is_still_a_stub() -> None:
    """Only a sub-header line continues an end: lone open relief outlets keep their stubs."""
    process = [_line(1, "v1", ["a"], None), _line(2, "v2", ["b"], None)]
    plant = _plant(process, [_line(5, None, ["htee", "hend"], None)], ["htee", "hend"])
    assert _process_sheet(plant).stubs == 2  # `a` and `b` end open, nothing continues them


def test_no_sub_header_end_of_a_real_v22_plant_is_counted_twice() -> None:
    """On a real plant a sub-header's tie-ins give one crossing per service, no extra open end."""
    plan = plan_plant(GeneratorConfigV22(seed=7, n_units=37))
    sub_headers = [
        line
        for unit in plan.units
        for line in unit.instance.plan.lines
        if line.items and unit.instance.plan.roles.get(line.items[0].node_id) == "sub_header_tee"
    ]
    assert sub_headers
    ends = wired_out_ends(plan) | fed_start_ends(plan)
    assert all((line.src_id or line.dst_id) in ends for line in sub_headers)
    stubs = [s.stubs for s in sheet_stats(plan) if s.sheet_group.split(":")[0] < "9000"]
    assert max(stubs) == 12  # architect's measurement, seed 7, 37 units (design 17.14 N1)
