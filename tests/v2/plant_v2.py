"""Shared v2 plants for the end-to-end tests (not a test module: no `test_` prefix).

`generated(seed, n_units)` builds a plant once per process; the tests only read it.
"""

from __future__ import annotations

from functools import cache

import networkx as nx

from plantgraph.adapters.pydexpi_adapter import ConversionReport
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import GeneratedPlantV2, generate_plant_v2


@cache
def generated(seed: int, n_units: int) -> GeneratedPlantV2:
    """The plant of `GeneratorConfigV2(seed, n_units)`."""
    return generate_plant_v2(GeneratorConfigV2(seed=seed, n_units=n_units))


@cache
def graph_of(seed: int, n_units: int) -> tuple[nx.DiGraph[str], ConversionReport]:
    """The schema graph and conversion report of `generated(seed, n_units)`."""
    return generated(seed, n_units).graph()
