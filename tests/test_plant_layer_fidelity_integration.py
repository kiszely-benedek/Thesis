"""Opt-in: PLANT-01 against a real Neo4j holding a toy corpus loaded with profile `both`.

Skipped unless Neo4j credentials are set and the database answers
(`conftest.neo4j_skip_reason`). Loads a disposable `pytest-plant-fidelity`
corpus and wipes it in a `finally`.
"""

from __future__ import annotations

import pytest

from conftest import neo4j_skip_reason
from plant_layer_toy import Toy
from plantgraph.qa.harness.plant_layer_fidelity import check_plant_layer
from plantgraph.store.neo4j_loader import load_corpus, wipe_corpus
from plantgraph.store.neo4j_plan import build_load_plan
from plantgraph.store.neo4j_settings import from_env
from plantgraph.store.plant_readback import Neo4jSource, read_plant_layer

_skip_reason = neo4j_skip_reason()
pytestmark = pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")

_CORPUS_ID = "pytest-plant-fidelity"


def test_a_loaded_toy_corpus_passes_plant_01() -> None:
    settings = from_env()
    assert settings is not None  # pytestmark skips the module otherwise
    toy = Toy(duplication_rate=0.5)
    plan = build_load_plan(_CORPUS_ID, toy.sheets, toy.resolution, profile="both")
    try:
        load_corpus(settings, plan)
        with Neo4jSource(settings) as source:
            layer = read_plant_layer(source, _CORPUS_ID)
        item_graph = toy.item_graph()
        result = check_plant_layer(layer, toy.gold, toy.occurrence_map, item_graph, _CORPUS_ID)
        assert result.passed, result
    finally:
        wipe_corpus(settings, _CORPUS_ID)
