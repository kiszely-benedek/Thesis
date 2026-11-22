"""`RuleView`: the one object every rule check reads (design 3.3).

It is built from a generated plant alone, so a check needs no test helper. The graph is the plan
written straight into a schema graph (the oracle, `oracle_graph.py`), not the graph read back from
the DEXPI model: it still carries each part's role, which the system under test never sees.
`HiddenDesignState` (design 6.1) is added by task T2; until then a view has no `hidden` field.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from plantgraph.benchmark.v2.generate import GeneratedPlantV2
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.rules.oracle_graph import GraphPlantBuilderV2


@dataclass(frozen=True)
class RuleView:
    """One generated plant: the plan, the oracle graph, the DEXPI model and every node's role."""

    generated: GeneratedPlantV2
    graph: nx.DiGraph[str]
    roles: dict[str, str]

    @property
    def plan(self) -> PlantPlanV2:
        """The plan the plant was built from."""
        return self.generated.plan

    @property
    def model(self) -> DexpiModel:
        """The pyDEXPI model the plan was written to."""
        return self.generated.model


def build_rule_view(generated: GeneratedPlantV2) -> RuleView:
    """Write the plan to the oracle graph and collect the role of every node."""
    oracle = GraphPlantBuilderV2(generated.plan.config.plant_id)
    generated.plan.write(oracle)
    roles: dict[str, str] = {}
    for unit in generated.plan.units:
        roles.update(unit.instance.plan.roles)
    return RuleView(generated=generated, graph=oracle.graph, roles=roles)
