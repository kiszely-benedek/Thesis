"""The one place that tells the v1 generator from the v2 one (design generator-v2-realism 2).

Every corpus ever stored (`ingest.json`) records its generator config. v1 configs have no
`generator_version` key, v2 configs say `"v2"`; so a stored config is read back as v2 only when it
says so, and every existing file keeps meaning v1. Callers never branch on the version themselves:
they read a config with `generator_config_from_json` and build a plant with
`generate_plant_graph_any`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any

import networkx as nx
from pydantic import Discriminator, Tag

from plantgraph.adapters.pydexpi_adapter import (
    abstract_conceptual_graph,
    load_complete_graph,
    map_conceptual_graph,
)
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import generate_plant_v2

_V2 = "v2"


def _version_of(config: object) -> str:
    """`"v2"` iff the config (a dict from JSON, or a model) says so; every other value is v1."""
    if isinstance(config, Mapping):
        version = config.get("generator_version")
    else:
        version = getattr(config, "generator_version", None)
    return _V2 if version == _V2 else "v1"


#: A v1 or v2 config as a Pydantic field type: the callable discriminator picks the class, so a v1
#: dict without the key can never validate as v2 through v2's default `generator_version`.
AnyGeneratorConfig = Annotated[
    Annotated[GeneratorConfig, Tag("v1")] | Annotated[GeneratorConfigV2, Tag("v2")],
    Discriminator(_version_of),
]


def generator_config_from_json(data: Mapping[str, Any]) -> GeneratorConfig | GeneratorConfigV2:
    """Read a stored generator config: v2 iff `generator_version == "v2"`, else v1."""
    if _version_of(data) == _V2:
        return GeneratorConfigV2.model_validate(data)
    return GeneratorConfig.model_validate(data)


def generate_plant_graph_any(config: GeneratorConfig | GeneratorConfigV2) -> nx.DiGraph[str]:
    """The ground-truth plant graph of either generator's config."""
    if isinstance(config, GeneratorConfigV2):
        graph, _conversion = generate_plant_v2(config).graph()
        return graph
    return _generate_plant_graph_v1(config)


def _generate_plant_graph_v1(config: GeneratorConfig) -> nx.DiGraph[str]:
    """v1's round trip (build -> load -> abstract -> map); unchanged since before v2 existed."""
    generated = generate_plant(config)
    complete = load_complete_graph(generated.model)
    conceptual = abstract_conceptual_graph(complete)
    plant, _conversion = map_conceptual_graph(
        conceptual, generated.record.plant_id, generated.record.stream_kind
    )
    return plant
