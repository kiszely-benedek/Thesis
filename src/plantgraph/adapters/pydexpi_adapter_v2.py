"""The v2 entry point of the pyDEXPI -> schema `DiGraph` adapter.

`plant_graph` (v1) reads a `GeneratedPlant`; a v2 plant comes with a `GenerationRecordV2` and needs
three different choices in `map_conceptual_graph`: the grown class vocabulary, units read from each
line's `PipingNetworkSystem`, and the gold node properties of the answer key.
"""

from __future__ import annotations

import networkx as nx
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from plantgraph.adapters.pydexpi_adapter import (
    ConversionReport,
    abstract_conceptual_graph,
    load_complete_graph,
    map_conceptual_graph,
)
from plantgraph.adapters.pydexpi_units import read_piping_units
from plantgraph.benchmark.v2.plan_models import GenerationRecordV2
from plantgraph.graph import schema


def plant_graph_v2(
    model: DexpiModel, record: GenerationRecordV2
) -> tuple[nx.DiGraph[str], ConversionReport]:
    """The schema's `DiGraph` of a v2 plant, and the coverage report."""
    conceptual = abstract_conceptual_graph(load_complete_graph(model))
    return map_conceptual_graph(
        conceptual,
        record.plant_id,
        record.stream_kind,
        vocabulary=schema.V2_IMPORTABLE_CLASSES,
        piping_units=read_piping_units(model),
        node_gold={node_id: gold.model_dump() for node_id, gold in record.node_gold.items()},
    )
