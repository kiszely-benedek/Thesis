"""The plan minus its sheet assignments is frozen (tuning round 1, design 14.2).

Tuning round 1 changes only which drawing group a node belongs to. Every node id, class, tag, line,
link and port of a fixed plant must therefore stay the same; the digests below were recorded on the
code *before* the round-1 edit. A new tuning round that moves nodes only between sheets keeps them.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant

UNITS = 60

#: seed -> sha256 of the plan without sheet assignments, recorded before the round-1 edit
RECORDED_DIGESTS = {
    1: "f0f418750d1a281af4d4e2b728f0bad4dd7b3a2c2a026cc4e6dba35be5dc2237",
    2: "e56bdcee52264a31caeb0e2d18ad3c1ca221990832de04b337cd89d14d60a9ed",
    3: "23d39dbded097a1da67a52b622a0289c56f92bcca442c14cbbdd4686a78e4075",
}


def plan_digest_without_sheets(plan: PlantPlanV2) -> str:
    """Hash every unit's slot, plan and ports; leave out drawing groups and sheets."""
    parts = [
        {
            "slot": unit.slot.model_dump(mode="json"),
            "plan": unit.instance.plan.model_dump(mode="json"),
            "ports": [port.model_dump(mode="json") for port in unit.instance.ports],
        }
        for unit in plan.units
    ]
    parts.append({"trains": [t.model_dump(mode="json") for t in plan.trains]})
    parts.append({"open_stub_count": plan.open_stub_count})
    text = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize("seed", sorted(RECORDED_DIGESTS))
def test_the_plan_without_sheet_assignments_is_unchanged(seed: int) -> None:
    plan = plan_plant(GeneratorConfigV2(seed=seed, n_units=UNITS))
    assert plan_digest_without_sheets(plan) == RECORDED_DIGESTS[seed]
