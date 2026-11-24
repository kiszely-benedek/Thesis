"""The plan of `run_all.sh --smoke`: tiny plants with dev-range seeds, so the whole chain runs fast.

A smoke plant has two or three units (a handful of sheets) and a seed in the dev range, so no test
seed is ever looked at. Sealed plants alternate between tagged and untagged documents, so both
question forms occur. `prereg/seeds.json` is a stand-in; the build skips the seed check.
"""

from __future__ import annotations

import json

from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.qa.exp0009.draw import real_document_flags
from plantgraph.qa.exp0009.plan import PLANTS_PER_SCALE, Exp0009Plan, PlantSpec22, Role, plant_id

_SEED_BASE = 20


def smoke_prior_text() -> str:
    """A prior with no table: every POSITION baseline falls back to its majority code, NO."""
    forms = ("tag", "descriptor")
    document = {f: {"key_fields": [], "majority": "NO", "table": []} for f in forms}
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def _spec(role: Role, scale: int, index: int | None, seed: int, n_units: int) -> PlantSpec22:
    config = HeadlinePresetV22().generator_config(n_units, seed)
    own = real_document_flags(n_units, seed)
    flags = own if index is None else (index % 2 == 0,) * len(own)
    return PlantSpec22(
        plant_id=plant_id(role, scale, index), role=role, scale=scale,
        seed=seed, target_sheets=scale, n_units=n_units,
        predicted_sheets=plan_plant(config).sheet_count, document_untagged=flags,
    )  # fmt: skip


def smoke_plan(prior_text: str) -> Exp0009Plan:
    """Dev, probe, validation and ten sealed plants, each of two or three units."""
    plants = [
        _spec(Role.DEV, 100, None, 1, 3),
        _spec(Role.PROBE, 1000, None, 1, 3),
        _spec(Role.VALIDATION, 100, None, _SEED_BASE, 2),
        _spec(Role.VALIDATION, 1000, None, _SEED_BASE + 1, 3),
    ]
    for scale, base in ((100, _SEED_BASE + 10), (1000, _SEED_BASE + 20)):
        plants += [
            _spec(Role.SEALED, scale, k, base + k, 2 if scale == 100 else 3)
            for k in range(1, PLANTS_PER_SCALE + 1)
        ]
    return Exp0009Plan(
        draw_seed=0, prior_sha256="0" * 64,
        majority_code={f: "NO" for f in json.loads(prior_text)}, plants=tuple(plants),
    )  # fmt: skip
