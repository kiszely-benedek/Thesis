"""The first v2 plant end to end: config -> plan -> DEXPI model -> schema graph.

`generate_plant_v2` is the entry the dispatch (a later task) wraps. It mirrors v1's
`GeneratedPlant`: the pyDEXPI model plus the answer key; `plant_graph_v2` (in the adapter) then
turns the pair into the schema's `DiGraph`.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from plantgraph.adapters.pydexpi_adapter import ConversionReport
from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.plan_models import GenerationRecordV2
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.record import build_record


@dataclass(frozen=True)
class GeneratedPlantV2:
    """A generated v2 plant: the model, its answer key and the plan they came from."""

    model: DexpiModel
    record: GenerationRecordV2
    plan: PlantPlanV2

    def graph(self) -> tuple[nx.DiGraph[str], ConversionReport]:
        """The schema graph read back from the model, and the conversion report."""
        return plant_graph_v2(self.model, self.record)


def generate_plant_v2(config: GeneratorConfigV2) -> GeneratedPlantV2:
    """Plan a plant, build it with the DEXPI backend and key it; same config, same bytes."""
    plan = plan_plant(config)
    builder = DexpiPlantBuilderV2(config.plant_id)
    plan.write(builder)
    model = builder.build()
    return GeneratedPlantV2(
        model=model, record=build_record(plan, builder.backend_version), plan=plan
    )
