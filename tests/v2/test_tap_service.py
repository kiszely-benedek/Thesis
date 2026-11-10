"""Review R2: a tap branch (differential pressure, `TI`/`PI` flanges) has its parent line's service.

A tap taken off a gas line (`PG`) carries the gas service code, not the unit's liquid `P`. Relief
lines to the flare are a different thing: they are `FL` on purpose and are not checked here.
"""

from __future__ import annotations

from collections import Counter

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant

_TAP_ROLES = ("_root", "_ti_flange", "_pi_flange", "_flange")


def _tap_services_off_other_services(plan: PlantPlanV2) -> Counter[str]:
    """Tap branches whose service differs from the line they start on, by `parent>tap` services."""
    bad: Counter[str] = Counter()
    for unit in plan.units:
        unit_plan = unit.instance.plan
        owner = {item.node_id: line for line in unit_plan.lines for item in line.items}
        for line in unit_plan.lines:
            parent = owner.get(line.src_id or "")
            if parent is None or parent is line or not line.items:
                continue
            role = unit_plan.roles.get(line.items[-1].node_id, "")
            if role.endswith(_TAP_ROLES) and parent.fluid_code != line.fluid_code:
                bad[f"{parent.fluid_code}>{line.fluid_code}"] += 1
    return bad


def test_seed_1_60_units_has_no_tap_with_another_service_than_its_line() -> None:
    """Before R2 (measured on the HEAD plant): 20 taps were `P` on a `PG` line: 13 dp roots, 4
    intercondenser TI, 1 inlet TI, 1 cooler outlet TI, 1 discharge PI root."""
    assert _tap_services_off_other_services(plan_plant(GeneratorConfigV2(seed=1, n_units=60))) == {}


def test_other_seeds_have_none_either() -> None:
    for seed, units in ((2, 120), (3, 150)):
        plan = plan_plant(GeneratorConfigV2(seed=seed, n_units=units))
        assert _tap_services_off_other_services(plan) == {}
