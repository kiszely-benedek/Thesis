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

#: seed -> sha256 of the plan without sheet assignments. Re-recorded for generator v2.1 (ADR-0065):
#: the product farms take the column distillate and side draw, so lines and receipts were added.
#: Re-recorded again for F8c: reactor code R, fuel-gas and exchanger-outlet sensors on their lines,
#: liquid and flare codes on drains, UC input variables, lighter class after a spec break.
RECORDED_DIGESTS = {
    1: "068c22fa74cc9c31b0320f5f242df9e8b88ffd5507db54ddbf38482a2eb72039",
    2: "eb4000d7ec3155bf8cee7be6dd33951827c0714d30cad910f8d321afd0c05439",
    3: "c397b03f109d475439c6171306173710951a57a5bff2a577f4ccad7957cb0c68",
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
