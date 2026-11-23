"""`RuleView`: the one object every rule check reads (design 3.3).

It is built from a generated plant alone, so a check needs no test helper. The graph is the plan
written straight into a schema graph (the oracle, `oracle_graph.py`), not the graph read back from
the DEXPI model: it still carries each part's role, which the system under test never sees.
`HiddenDesignState` (design 6.1) is read from the plant's record: empty for a v2.1 plant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import GeneratedPlantV2
from plantgraph.benchmark.v2.hidden_state import HiddenDesignState
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.record_v22 import GenerationRecordV22
from plantgraph.benchmark.v2.rules.oracle_graph import GraphPlantBuilderV2


@dataclass(frozen=True)
class RuleView:
    """One generated plant: the plan, the oracle graph, the DEXPI model and every node's role."""

    generated: GeneratedPlantV2
    graph: nx.DiGraph[str]
    roles: dict[str, str]
    _kind_cache: dict[str, StreamKindV2] = field(default_factory=dict, repr=False, compare=False)

    @property
    def plan(self) -> PlantPlanV2:
        """The plan the plant was built from."""
        return self.generated.plan

    @property
    def handbook_enabled(self) -> bool:
        """True for a v2.2 plant drawn with the handbook rules on; v2.1 plants are always False."""
        config = self.plan.config
        return isinstance(config, GeneratorConfigV22) and config.handbook.enabled

    @property
    def hidden(self) -> HiddenDesignState:
        """The design quantities no drawing shows; empty on a v2.1 plant, which draws none."""
        record = self.generated.record
        return (
            record.hidden_state if isinstance(record, GenerationRecordV22) else HiddenDesignState()
        )

    def stream_kind_of(self, line_number: str) -> StreamKindV2 | None:
        """The kind of the line with this number, or None for a number the plan does not know.

        A line with a spec break has two numbers; both map to the kind the plan recorded for
        the first. The map is built on first use: a check asks once per pipe or per dead end.
        """
        if not self._kind_cache:
            recorded = self.generated.record.stream_kind
            for unit in self.plan.units:
                for line in unit.instance.plan.lines:
                    kind = recorded.get(line.line_number)
                    if kind is not None:
                        self._kind_cache.update({n: kind for n in line.line_numbers})
        return self._kind_cache.get(line_number)

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
