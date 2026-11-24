"""R4: positions read back out of DEXPI, and the file they travel in (design `v2t-b` §10 R4)."""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

import pytest

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import GeneratedPlantV2, generate_plant_v2
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.qa.v2tb.positions import (
    POSITIONS_FILE_NAME,
    read_operating_positions,
    read_positions_file,
    write_positions_file,
)
from plantgraph.qa.v2tb.store_b import ingest_positions
from plantgraph.qa.v2tb.visible import POSITION_CODES


@cache
def _generated() -> GeneratedPlantV2:
    return generate_plant_v2(GeneratorConfigV22(seed=1, n_units=8))


def test_reading_the_dexpi_model_round_trips_annotate_valves_and_equals_the_plan() -> None:
    generated = _generated()
    planned = dict(positions_of(generated.plan.unit_plans))

    read = read_operating_positions(generated.model)

    assert read == planned
    assert len(read) > 100  # a real plant: the check is not vacuous
    assert set(read.values()) <= set(POSITION_CODES)


def test_a_model_without_the_attribute_reads_as_no_positions() -> None:
    from plantgraph.benchmark.v2.config import GeneratorConfigV2

    plain = generate_plant_v2(GeneratorConfigV2(seed=1, n_units=2))

    assert read_operating_positions(plain.model) == {}


def test_the_file_is_sorted_json_and_its_sha256_is_the_hash_of_its_bytes(tmp_path: Path) -> None:
    path = tmp_path / POSITIONS_FILE_NAME

    sha256 = write_positions_file(path, {"b": "NC", "a": "NO"})

    assert sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert list(json.loads(path.read_text("utf-8"))) == ["a", "b"]
    assert read_positions_file(path) == ({"a": "NO", "b": "NC"}, sha256)


def test_a_missing_or_malformed_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="positions file"):
        read_positions_file(tmp_path / "none.json")
    bad = tmp_path / "bad.json"
    bad.write_text('{"a": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="object of strings"):
        read_positions_file(bad)


def test_the_ingest_step_generates_reads_dexpi_and_writes_the_file(tmp_path: Path) -> None:
    record = ingest_positions(GeneratorConfigV22(seed=1, n_units=8), tmp_path / "corpus")

    expected = dict(positions_of(_generated().plan.unit_plans))
    assert record.positions == expected
    assert read_positions_file(record.path) == (expected, record.sha256)
