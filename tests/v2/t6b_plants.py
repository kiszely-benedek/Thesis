"""v2.2 plants for the T6b tests, built once per process (not a test module: no `test_` prefix).

`forced_untagged` / `forced_tagged` build a plant of about 30 sheets whose documents all print no
tag on their manual valves, or all do. The record is the generator's own answer key, which
`validate_plant_graph_v22` reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import networkx as nx

from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.record_v22 import GenerationRecordV22
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus
from plantgraph.qa.exp0009.dev_plants import forced_config

TARGET_SHEETS = 30


@dataclass(frozen=True)
class PlantWithRecord:
    """A generated plant graph and the generation record that answers for it."""

    plant: nx.DiGraph[str]
    record: GenerationRecordV22


@cache
def corpus(seed: int, *, untagged: bool) -> SyntheticCorpus:
    """The split and resolved plant of `seed`, every document forced one way."""
    config = forced_config(TARGET_SHEETS, seed, untagged=untagged)
    return build_synthetic_corpus(config, HeadlinePresetV22().split_config(seed))


@cache
def plant_and_record(seed: int, *, untagged: bool) -> PlantWithRecord:
    """The plant graph and record of the same forced config."""
    generated = generate_plant_v2(forced_config(TARGET_SHEETS, seed, untagged=untagged))
    assert isinstance(generated.record, GenerationRecordV22)
    return PlantWithRecord(generated.graph()[0], generated.record)
