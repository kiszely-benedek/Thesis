"""Tests for `GeneratorConfigV2`: validation, declared values, and v1 staying untouched."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.v2.config import (
    GENERATED_EQUIPMENT_CLASSES,
    GeneratorConfigV2,
    PatternKnobs,
    SheetKnobs,
    TrimConvention,
    VentDrainConvention,
)
from plantgraph.graph.schema import EQUIPMENT_CLASSES


def test_generated_equipment_is_23_classes_without_the_two_dropped() -> None:
    assert len(GENERATED_EQUIPMENT_CLASSES) == 23
    assert GENERATED_EQUIPMENT_CLASSES <= EQUIPMENT_CLASSES
    assert {"SpiralHeatExchanger", "ElectricalSeparator"}.isdisjoint(GENERATED_EQUIPMENT_CLASSES)
    # the two dropped classes are still in the schema, for importing real files
    assert {"SpiralHeatExchanger", "ElectricalSeparator"} <= EQUIPMENT_CLASSES


def test_defaults_carry_the_declared_values() -> None:
    config = GeneratorConfigV2(n_units=3)
    assert config.generator_version == "v2"
    assert (config.sheets.min_equipment_per_sheet, config.sheets.max_equipment_per_sheet) == (1, 16)
    assert config.sheets.max_symbols_before_stubs == 100
    assert config.trims.p_cv_station == 0.6
    assert config.trims.vent_drain_convention is VentDrainConvention.KLM_ALL
    assert config.trims.condensate_mode_weights == {
        "trap": 2.0,
        "trap_station": 1.0,
        "drain_pot": 1.0,
    }
    assert config.trims.pump_pressure_mode_weights == {"per_pump_pi": 3.0, "header_pt": 1.0}
    assert config.instruments.p_motor_hs == 1.0
    assert config.instruments.p_cascade == 0.5
    assert config.instruments.p_split_range == 0.0
    assert config.patterns.p_triple_pump_set == 0.15


def test_json_round_trip_keeps_the_discriminator() -> None:
    config = GeneratorConfigV2(n_units=5, seed=7, equipment_weights={"Tank": 2.0})
    data = json.loads(config.model_dump_json())
    assert data["generator_version"] == "v2"
    assert GeneratorConfigV2.model_validate(data) == config


def test_wrong_generator_version_is_rejected() -> None:
    with pytest.raises(ValidationError, match="generator_version"):
        GeneratorConfigV2.model_validate({"generator_version": "v1", "n_units": 1})


def test_n_units_is_required_and_positive() -> None:
    with pytest.raises(ValidationError):
        GeneratorConfigV2.model_validate({})
    with pytest.raises(ValidationError):
        GeneratorConfigV2(n_units=0)


def test_equipment_weight_keys_must_be_generated_classes() -> None:
    with pytest.raises(ValidationError, match="SpiralHeatExchanger"):
        GeneratorConfigV2(n_units=1, equipment_weights={"SpiralHeatExchanger": 1.0})
    with pytest.raises(ValidationError, match="NoSuchClass"):
        GeneratorConfigV2(n_units=1, equipment_weights={"NoSuchClass": 1.0})


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_equipment_weights_must_be_positive(bad: float) -> None:
    with pytest.raises(ValidationError, match="strictly positive"):
        GeneratorConfigV2(n_units=1, equipment_weights={"Tank": bad})


@pytest.mark.parametrize("bad", [0.0, -2.0])
def test_mode_weights_must_be_positive(bad: float) -> None:
    with pytest.raises(ValidationError, match="strictly positive"):
        TrimConvention(condensate_mode_weights={"trap": bad, "drain_pot": 1.0})
    with pytest.raises(ValidationError, match="strictly positive"):
        PatternKnobs(pump_set_group_weights={"own_sheet": bad})


def test_mode_weight_keys_are_closed_sets() -> None:
    with pytest.raises(ValidationError):
        TrimConvention(pump_pressure_mode_weights={"surprise": 1.0})


def test_sheet_range_minimum_must_not_exceed_maximum() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        SheetKnobs(min_equipment_per_sheet=5, max_equipment_per_sheet=4)


@pytest.mark.parametrize("field", ["min_equipment_per_sheet", "max_equipment_per_sheet"])
@pytest.mark.parametrize("bad", [0, 17])
def test_equipment_per_sheet_stays_within_1_to_16(field: str, bad: int) -> None:
    with pytest.raises(ValidationError):
        SheetKnobs(**{field: bad})


def test_sheet_bounds_1_and_16_are_accepted() -> None:
    knobs = SheetKnobs(min_equipment_per_sheet=16, max_equipment_per_sheet=16)
    assert knobs.min_equipment_per_sheet == 16


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_probabilities_stay_within_0_and_1(bad: float) -> None:
    with pytest.raises(ValidationError):
        TrimConvention(p_cv_station=bad)


def test_pump_set_chances_must_leave_room_for_the_default_pair() -> None:
    with pytest.raises(ValidationError, match="must not exceed 1"):
        PatternKnobs(p_triple_pump_set=0.6, p_single_pump=0.5)


def test_v1_config_json_has_no_v2_field() -> None:
    v1 = json.loads(GeneratorConfig().model_dump_json())
    assert "generator_version" not in v1
    assert set(v1) == {
        "plant_id",
        "seed",
        "n_units",
        "equipment_per_unit_min",
        "equipment_per_unit_max",
        "p_recycle",
        "p_cross_link",
        "valves_per_stream_max",
        "p_control_loop",
        "equipment_weights",
        "fluid_codes",
    }
