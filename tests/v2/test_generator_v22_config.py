"""The v2.2 config, the hidden-state container, the three-way dispatch and v2.1 equivalence (T2)."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from pydexpi.loaders.json_serializer import JsonSerializer

from plantgraph.benchmark.generator_dispatch import (
    AnyGeneratorConfig,
    generate_plant_graph_any,
    generator_config_from_json,
)
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.hidden_state import HiddenDesignState
from plantgraph.benchmark.v2.record_v22 import GenerationRecordV22
from plantgraph.benchmark.v2.rules.catalogue import all_rules
from plantgraph.ingest.headline_v2 import headline_corpus_id_v2
from plantgraph.ingest.headline_v22 import HeadlinePresetV22

_ANY = TypeAdapter(AnyGeneratorConfig)


def _v22(seed: int, n_units: int, knobs: HandbookKnobs | None = None) -> GeneratorConfigV22:
    return GeneratorConfigV22(seed=seed, n_units=n_units, handbook=knobs or HandbookKnobs())


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_a_v22_plant_with_every_knob_off_equals_the_v21_plant_of_the_same_seed(seed: int) -> None:
    config = _v22(seed, 6, HandbookKnobs.all_off())
    v22 = generate_plant_v2(config)
    v21 = generate_plant_v2(config.v21_equivalent())
    serializer = JsonSerializer()
    assert serializer.export_to_bytes(v22.model) == serializer.export_to_bytes(v21.model)
    # the record differs in the config JSON (version, handbook group) and the added hidden state
    same_gold = v21.record.model_dump(exclude={"generator_config"})
    assert v22.record.model_dump(exclude={"generator_config", "hidden_state"}) == same_gold
    assert v22.record.seed == v21.record.seed
    assert isinstance(v22.record, GenerationRecordV22)
    assert v22.record.hidden_state == HiddenDesignState()


def test_the_v21_config_is_the_v22_one_with_only_the_version_and_handbook_removed() -> None:
    config = _v22(3, 4)
    v21 = config.v21_equivalent()
    assert type(v21) is GeneratorConfigV2
    assert v21.generator_version == "v2.1"
    assert v21.model_dump() == config.model_dump(exclude={"handbook", "generator_version"}) | {
        "generator_version": "v2.1"
    }


def test_the_dispatch_reads_each_version_back_as_its_own_class() -> None:
    v1 = GeneratorConfig(n_units=2, seed=1)
    v21 = GeneratorConfigV2(n_units=2, seed=1)
    v22 = _v22(1, 2)
    for config in (v1, v21, v22):
        data = config.model_dump(mode="json")
        assert type(generator_config_from_json(data)) is type(config)
        assert _ANY.validate_python(data) == config


def test_the_v22_config_json_says_v22_and_keeps_the_v21_fields_first() -> None:
    data = _v22(1, 2).model_dump(mode="json")
    assert data["generator_version"] == "v2.2"
    assert list(data)[: len(GeneratorConfigV2(n_units=2).model_dump())] == list(
        GeneratorConfigV2(n_units=2).model_dump()
    )
    assert list(data)[-1] == "handbook"


def test_the_dispatch_builds_the_graph_of_a_v22_config() -> None:
    config = _v22(2, 2, HandbookKnobs.all_off())
    v22_graph = generate_plant_graph_any(config)
    v21_graph = generate_plant_graph_any(config.v21_equivalent())
    assert sorted(v22_graph.nodes) == sorted(v21_graph.nodes)
    assert sorted(v22_graph.edges) == sorted(v21_graph.edges)


def test_the_superseded_v2_is_still_refused() -> None:
    with pytest.raises(ValueError, match="superseded generator"):
        generator_config_from_json({"generator_version": "v2", "n_units": 2})


def test_a_weight_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="strictly positive"):
        HandbookKnobs(exchanger_bypass_weights={"tv_alone": 0.0, "two_control_valves": 1.0})


def test_every_declared_parameter_of_a_rule_is_a_field_of_the_v22_config() -> None:
    for rule in all_rules():
        for path in rule.declared_parameters:
            assert _has_field(GeneratorConfigV22, path), f"{rule.rule_id}: {path}"


def _has_field(model: type, path: str) -> bool:
    """Whether the dotted `path` (`group.field`) names a field of the pydantic `model`."""
    head, _, tail = path.partition(".")
    field = model.model_fields.get(head)  # type: ignore[attr-defined]
    if field is None:
        return False
    return not tail or (field.annotation is not None and _has_field(field.annotation, tail))


def test_the_v22_headline_preset_builds_v22_configs_and_g22_ids() -> None:
    preset = HeadlinePresetV22()
    assert type(preset.generator_config(3, 1)) is GeneratorConfigV22
    assert headline_corpus_id_v2(100, 1, generation=preset.generation) == "D100g22"
    assert headline_corpus_id_v2(100, 7, generation=preset.generation) == "X100g22s7"
    assert headline_corpus_id_v2(100, 1) == "D100g21"
