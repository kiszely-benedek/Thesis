"""Tag-blind structural digest of a generated plant, for the CV-T2 invariance test.

ADR-0044 renames tags only, so node ids, edges and sheet membership must not move.
"""

from __future__ import annotations

import hashlib
import json

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.ingest.headline import HeadlinePreset


def topology_digest(config: GeneratorConfig, split_config: SplitConfig) -> str:
    """Hash node ids, edges with relations and per-sheet node-id sets (no tags)."""
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    plant = builder.graph
    sheets, _ = split(plant, split_config)
    structure = {
        "nodes": sorted(plant.nodes),
        "edges": sorted([u, v, data["relation"]] for u, v, data in plant.edges(data=True)),
        "sheets": sorted(sorted(sheet.graph.nodes) for sheet in sheets),
    }
    return hashlib.sha256(json.dumps(structure).encode()).hexdigest()


def small_seed_digest(seed: int) -> str:
    """Digest of the default small plant for `seed`, split into sheets of 3 equipment."""
    split_config = SplitConfig(strategy="flow_greedy", sheet_equipment_budget=3, seed=0)
    return topology_digest(GeneratorConfig(seed=seed), split_config)


def headline_digest(n_units: int, seed: int) -> str:
    """Digest of the headline-preset plant with `n_units` units."""
    preset = HeadlinePreset()
    return topology_digest(preset.generator_config(n_units, seed), preset.split_config(seed))
