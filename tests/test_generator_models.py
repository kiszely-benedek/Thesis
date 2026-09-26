"""The `GeneratorConfig` validators (`plant-generator.md` §3.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.graph import schema


def test_default_equipment_weights_cover_every_schema_equipment_class() -> None:
    config = GeneratorConfig()
    assert set(config.equipment_weights) == schema.EQUIPMENT_CLASSES
    assert all(weight == 1.0 for weight in config.equipment_weights.values())


def test_equipment_range_rejects_min_above_max() -> None:
    with pytest.raises(ValidationError, match="equipment_per_unit_min"):
        GeneratorConfig(equipment_per_unit_min=5, equipment_per_unit_max=3)


def test_equipment_range_allows_min_equal_to_max() -> None:
    config = GeneratorConfig(equipment_per_unit_min=4, equipment_per_unit_max=4)
    assert config.equipment_per_unit_min == config.equipment_per_unit_max == 4


def test_equipment_weights_rejects_an_unknown_node_class() -> None:
    with pytest.raises(ValidationError, match="unknown node_class"):
        GeneratorConfig(equipment_weights={"SteamTrap": 1.0})


def test_equipment_weights_rejects_a_non_positive_weight() -> None:
    with pytest.raises(ValidationError, match="strictly positive"):
        GeneratorConfig(equipment_weights={"Tank": 0.0})


def test_plant_id_rejects_characters_outside_the_pattern() -> None:
    with pytest.raises(ValidationError):
        GeneratorConfig(plant_id="plant-0")


def test_plant_id_accepts_lowercase_letters_and_digits() -> None:
    config = GeneratorConfig(plant_id="plant0")
    assert config.plant_id == "plant0"


def test_fluid_codes_rejects_an_empty_list() -> None:
    with pytest.raises(ValidationError):
        GeneratorConfig(fluid_codes=[])
