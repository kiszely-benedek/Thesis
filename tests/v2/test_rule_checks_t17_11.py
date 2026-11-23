"""The two check fixes of design 17.11: TOG316 ignores hand block valves, TOG295 floats on any item.

The discharge KO drum only appears on a plant of about 100 sheets (seed 7), so these tests build
that plant once; seeds 1-5 at 30 sheets have none.
"""

from __future__ import annotations

from dataclasses import replace
from functools import cache

from test_rule_checks_t3 import _a_pd_stage_valve, _insert_after

from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.rules.checks_compressors import check_pd_compressor_capacity
from plantgraph.benchmark.v2.rules.checks_inventory import check_inventory_once
from plantgraph.benchmark.v2.rules.control_graph import PRESSURE, sensors_on
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.ingest.headline_v2 import smallest_n_units_v2
from plantgraph.ingest.headline_v22 import HeadlinePresetV22


@cache
def _view_100_sheets() -> RuleView:
    preset = HeadlinePresetV22()
    n_units = smallest_n_units_v2(100, preset, 7).n_units
    return build_rule_view(generate_plant_v2(preset.generator_config(n_units, 7)))


def _discharge_drum(view: RuleView) -> str:
    return next(n for n, role in sorted(view.roles.items()) if role == "discharge_ko_drum")


def _violators(view: RuleView) -> set[str]:
    return {v.node_id for v in check_inventory_once(view).violations}


# ---- TOG316 -------------------------------------------------------------------------------------


def test_a_hand_block_valve_after_a_pd_compressor_is_not_a_throttle() -> None:
    view = _view_100_sheets()
    machine, _ = _a_pd_stage_valve(view)
    with_block = _insert_after(view, machine, "mutant-block", "ButterflyValve", "BFV-99999")
    assert check_pd_compressor_capacity(with_block).violations == ()


def test_a_hand_control_valve_after_a_pd_compressor_is_a_throttle() -> None:
    view = _view_100_sheets()
    machine, _ = _a_pd_stage_valve(view)
    throttled = _insert_after(view, machine, "mutant-hcv", "ButterflyValve", "HCV-99999")
    assert [v.node_id for v in check_pd_compressor_capacity(throttled).violations]


# ---- TOG295 -------------------------------------------------------------------------------------


def test_the_discharge_drum_floats_on_an_exchanger_that_holds_the_pressure() -> None:
    view = _view_100_sheets()
    drum = _discharge_drum(view)
    result = check_inventory_once(view)
    assert drum not in _violators(view)
    partners = [c.split(":")[1] for c in result.exceptions if c.startswith("pressure_floating_on:")]
    assert any(view.graph.nodes[p]["node_class"] in EQUIPMENT_CLASSES for p in partners)


def test_the_discharge_drum_is_a_violation_when_its_partner_loses_the_pressure_loop() -> None:
    view = _view_100_sheets()
    drum = _discharge_drum(view)
    partners = [c.split(":")[1] for c in check_inventory_once(view).exceptions if ":" in c]
    broken_for = [
        p for p in sorted(partners) if drum in _violators(_without_pressure_loop(view, p))
    ]
    assert len(broken_for) == 1, f"expected one partner holding {drum}, found {broken_for}"


def _without_pressure_loop(view: RuleView, item: str) -> RuleView:
    # drop the pressure transmitter, not the controller: the controller still drives the spillback
    # valve, which must stay a control valve or the drum would find another way to a partner
    graph = view.graph.copy()
    graph.remove_nodes_from(sensors_on(graph, item, PRESSURE))
    return replace(view, graph=graph)
