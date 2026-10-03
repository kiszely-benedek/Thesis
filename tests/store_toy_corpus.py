"""Small generated corpora for the store tests: split, localized and resolved (no database)."""

from __future__ import annotations

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.resolution.localize import localize
from plantgraph.resolution.models import Resolution
from plantgraph.resolution.resolver import resolve


def toy_corpus(duplication_rate: float, seed: int = 7) -> tuple[list[SheetGraph], Resolution]:
    """A 4-unit generated plant on small sheets; `duplication_rate` creates identity groups."""
    generator_config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    split_config = SplitConfig(
        sheet_equipment_budget=2, seed=seed, duplication_rate=duplication_rate
    )
    sheets, _manifest = split(builder.graph, split_config)
    localized, _occurrence_map = localize(sheets)
    return localized, resolve(localized)
