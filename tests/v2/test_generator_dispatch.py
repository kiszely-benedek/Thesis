"""The dispatch: every stored config stays v1, a v2 config comes back as v2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from plant_v2 import graph_of
from pydantic import TypeAdapter

from plantgraph.benchmark.generator_dispatch import (
    AnyGeneratorConfig,
    generate_plant_graph_any,
    generator_config_from_json,
)
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.v2.config import GeneratorConfigV2

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ANY = TypeAdapter(AnyGeneratorConfig)


def _stored_generator_blocks() -> list[tuple[Path, dict[str, object]]]:
    """The `config.generator` block of each `ingest.json` under `data/` (Proteus runs have none)."""
    blocks = []
    for path in sorted((_REPO_ROOT / "data").glob("**/ingest.json")):
        config = json.loads(path.read_text(encoding="utf-8"))["config"]
        if "generator" in config:
            blocks.append((path, config["generator"]))
    return blocks


def test_every_stored_ingest_json_dispatches_to_v1_and_dumps_back_unchanged() -> None:
    blocks = _stored_generator_blocks()
    if not blocks:
        pytest.skip("no ingest.json under data/ (the run outputs are git-ignored)")
    for path, block in blocks:
        config = generator_config_from_json(block)
        assert type(config) is GeneratorConfig, path
        assert config.model_dump(mode="json") == block, path
        assert _ANY.validate_python(block) == config, path


def test_a_v1_dict_without_the_version_key_is_never_read_as_v2() -> None:
    config = generator_config_from_json({"n_units": 3, "seed": 2})
    assert type(config) is GeneratorConfig
    assert "generator_version" not in config.model_dump(mode="json")


def test_a_v2_config_round_trips_through_json_and_dispatches_back_to_v2() -> None:
    original = GeneratorConfigV2(seed=5, n_units=4)
    stored = json.loads(original.model_dump_json())
    assert stored["generator_version"] == "v2"
    assert generator_config_from_json(stored) == original
    assert _ANY.validate_python(stored) == original


def test_the_record_of_a_v2_plant_names_its_config_as_v2() -> None:
    from plant_v2 import generated

    record_config = json.loads(generated(1, 3).record.generator_config)
    assert type(generator_config_from_json(record_config)) is GeneratorConfigV2


def test_generate_plant_graph_any_builds_a_v2_plant_for_a_v2_config() -> None:
    plant = generate_plant_graph_any(GeneratorConfigV2(seed=1, n_units=3))
    expected, _ = graph_of(1, 3)
    assert set(plant.nodes) == set(expected.nodes)
    assert all("sheet_group" in attrs for _, attrs in plant.nodes(data=True))


def test_generate_plant_graph_any_builds_a_v1_plant_for_a_v1_config() -> None:
    plant = generate_plant_graph_any(GeneratorConfig(seed=1, n_units=2))
    assert plant.number_of_nodes() > 0
    assert not any("sheet_group" in attrs for _, attrs in plant.nodes(data=True))
