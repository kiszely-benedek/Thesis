"""The one place that tells the v1, v2.1 and v2.2 generators apart (design v2-realism 2, v2-2 9).

Every corpus ever stored (`ingest.json`) records its generator config. v1 configs have no
`generator_version` key; v2 configs say `"v2"` (the first measurement, refused now), `"v2.1"` or
`"v2.2"`. A stored config is read back as v2 only when it says so, and every existing file keeps
meaning v1.
Callers never branch on the version themselves: they read a config with
`generator_config_from_json` and build a plant with `generate_plant_graph_any`.
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
from plantgraph.benchmark.v2.config import SUPERSEDED_VERSION, GeneratorConfigV2
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.rules.registry import RuleReport

_V2 = "v2.1"  # the tag of `GeneratorConfigV2`; the superseded "v2" is routed there to be refused
_V22 = "v2.2"
#: version strings that reach `GeneratorConfigV2`: `"v2"` is refused by name in its validator
_V2_VERSIONS = frozenset({SUPERSEDED_VERSION, "v2.1"})

#: any config of the three generators
AnyConfig = GeneratorConfig | GeneratorConfigV2 | GeneratorConfigV22


def _version_of(config: object) -> str:
    """The tag `"v1"`, `"v2.1"` or `"v2.2"` of a config (a dict from JSON, or a model)."""
    if isinstance(config, Mapping):
        version = config.get("generator_version")
    else:
        version = getattr(config, "generator_version", None)
    if version == _V22:
        return _V22
    return _V2 if version in _V2_VERSIONS else "v1"


#: A v1, v2.1 or v2.2 config as a Pydantic field type: the callable discriminator picks the class,
#: so a v1 dict without the key can never validate as v2 through v2's default `generator_version`.
AnyGeneratorConfig = Annotated[
    Annotated[GeneratorConfig, Tag("v1")]
    | Annotated[GeneratorConfigV2, Tag("v2.1")]
    | Annotated[GeneratorConfigV22, Tag("v2.2")],
    Discriminator(_version_of),
]


def generator_config_from_json(data: Mapping[str, Any]) -> AnyConfig:
    """Read a stored generator config: v2.2 or v2.1 iff it says so, else v1.

    Raises:
        ValueError: the config says `"v2"` (the superseded generator).
    """
    version = _version_of(data)
    if version == _V22:
        return GeneratorConfigV22.model_validate(data)
    if version == _V2:
        return GeneratorConfigV2.model_validate(data)
    return GeneratorConfig.model_validate(data)


def generate_plant_graph_any(config: AnyConfig) -> nx.DiGraph[str]:
    """The ground-truth plant graph of any generator's config."""
    return generate_plant_graph_and_rules(config)[0]


def generate_plant_graph_and_rules(config: AnyConfig) -> tuple[nx.DiGraph[str], RuleReport | None]:
    """The plant graph and, for a v2.2 plant, its build-time rule report (else None)."""
    if isinstance(
        config, GeneratorConfigV2
    ):  # GeneratorConfigV22 is a subclass, built the same way
        generated = generate_plant_v2(config)
        graph, _conversion = generated.graph()
        return graph, generated.rules
    return _generate_plant_graph_v1(config), None


def _generate_plant_graph_v1(config: GeneratorConfig) -> nx.DiGraph[str]:
    """v1's round trip (build -> load -> abstract -> map); unchanged since before v2 existed."""
    generated = generate_plant(config)
    complete = load_complete_graph(generated.model)
    conceptual = abstract_conceptual_graph(complete)
    plant, _conversion = map_conceptual_graph(
        conceptual, generated.record.plant_id, generated.record.stream_kind
    )
    return plant
