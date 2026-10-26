"""Determinism and prefix stability of a whole v2 plant (S14, S15)."""

from __future__ import annotations

import os
import random
import subprocess
import sys

from plant_v2 import generated

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.planner import plan_plant

_DIGEST_SCRIPT = """
import hashlib
from pydexpi.loaders.json_serializer import JsonSerializer
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import generate_plant_v2
plant = generate_plant_v2(GeneratorConfigV2(seed=4, n_units=15))
print(hashlib.sha256(JsonSerializer().export_to_bytes(plant.model)).hexdigest())
print(hashlib.sha256(plant.record.model_dump_json().encode()).hexdigest())
"""


def _digests(hash_seed: int) -> list[str]:
    env = {**os.environ, "PYTHONHASHSEED": str(hash_seed)}
    out = subprocess.run(
        [sys.executable, "-c", _DIGEST_SCRIPT], env=env, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def test_same_seed_gives_identical_dexpi_bytes_and_record_under_hash_seeds_0_and_999() -> None:
    first, second = _digests(0), _digests(999)
    assert len(first) == 2 and first == second


def test_generation_leaves_the_global_random_stream_alone() -> None:
    random.seed(123)
    expected = random.random()
    random.seed(123)
    plan_plant(GeneratorConfigV2(seed=2, n_units=8))
    assert random.random() == expected


def test_a_different_seed_changes_the_plant() -> None:
    def tags(seed: int) -> list[str]:
        graph, _ = generated(seed, 10).graph()
        return sorted(str(d.get("tag")) for _, d in graph.nodes(data=True))

    assert tags(1) != tags(2)


def test_the_first_n_units_of_a_bigger_plant_are_identical_to_the_n_unit_plant() -> None:
    """S15: unit internals, joins and sheet groups do not depend on later units."""
    small = plan_plant(GeneratorConfigV2(seed=6, n_units=7))
    large = plan_plant(GeneratorConfigV2(seed=6, n_units=16))
    assert small.units == large.units[:7]
    assert small.trains == large.trains[: len(small.trains)]
