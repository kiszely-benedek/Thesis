"""The drawn test seeds of the final v2 measurement (EXP-0008) and the retired old ones.

A **test seed** is the random seed of a plant that is measured once and never tuned on. ADR-0065
retires every seed the first measurement used and draws fresh ones, once, before any test plant is
generated. `SeedPlan` is the record of that draw; it is written by `qa/exp0008/draw_seeds.py` into
the pre-registration and read back here, so corpus ids and the generator CLI see the same seeds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: seeds 5000-5999 are test seeds (design vocabulary 14.5); dev and tuning seeds stay below 1000
TEST_SEED_RANGE = range(5000, 6000)

#: First-measurement test seeds (ADR-0059: 5100 = 1 sheet, 5001 = 3/10/30, 5002 = 100, 5003 = 1000)
#: and its two validation seeds. None may be a test seed again; `qa.exp0008.hygiene` adds every
#: other seed it finds recorded under `data/runs`.
RETIRED_TEST_SEEDS: frozenset[int] = frozenset({5100, 5001, 5002, 5003, 212, 213})

#: where the draw is written (inside the pre-registration part A, ADR-0065) and read from
DEFAULT_SEED_PLAN_PATH = Path("data/runs/exp0008/prereg/seeds.json")

#: the sizes with several sealed plants (design 5.1): five plants each
SEALED_SIZES = (100, 1000)
PLANTS_PER_SIZE = 5
#: the ladder's 1-sheet plant is the first candidate whose one-unit plan fits on one sheet
SINGLE_SHEET_CANDIDATES = 30


class DrawRecord(BaseModel):
    """How the seeds were drawn, so the draw can be repeated and audited."""

    model_config = ConfigDict(frozen=True)

    draw_seed: int
    method: str
    pool: str
    retired: tuple[int, ...]
    #: where the retired seeds came from (the runs folder that was scanned, how many files)
    retired_sources: str
    drawn_at_utc: str
    python_version: str


class SeedPlan(BaseModel):
    """Every test-role seed of EXP-0008, by role."""

    model_config = ConfigDict(frozen=True)

    #: sheets (100 / 1000) -> the re-validation plant's seed (gate G1)
    validation: dict[int, int]
    #: the one ladder plant of 3, 10 and 30 sheets (nested prefixes of one plant)
    ladder_seed: int
    #: ordered; the first whose one-unit plan fits on one sheet is the ladder's 1-sheet plant
    single_sheet_candidates: tuple[int, ...] = Field(min_length=1)
    #: sheets -> seeds of the five sealed plants; plant index k (1-based) is position k - 1
    sealed: dict[int, tuple[int, ...]]
    draw: DrawRecord

    @model_validator(mode="after")
    def _seeds_are_fresh_and_distinct(self) -> Self:
        seeds = self.all_seeds()
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"expected every test seed to be distinct, found repeats in {seeds}")
        bad = [s for s in seeds if s not in TEST_SEED_RANGE or s in RETIRED_TEST_SEEDS]
        if bad:
            raise ValueError(f"expected fresh seeds in 5000-5999, found {bad}")
        return self

    @model_validator(mode="after")
    def _has_five_plants_per_size(self) -> Self:
        if sorted(self.sealed) != sorted(SEALED_SIZES) or sorted(self.validation) != sorted(
            SEALED_SIZES
        ):
            raise ValueError(f"expected sealed and validation seeds for sizes {SEALED_SIZES}")
        short = {n: len(s) for n, s in self.sealed.items() if len(s) != PLANTS_PER_SIZE}
        if short:
            raise ValueError(f"expected {PLANTS_PER_SIZE} sealed plants per size, found {short}")
        return self

    def all_seeds(self) -> list[int]:
        """Every seed in the plan, in role order."""
        sealed = [seed for size in SEALED_SIZES for seed in self.sealed.get(size, ())]
        validation = [self.validation[size] for size in SEALED_SIZES if size in self.validation]
        return [*validation, self.ladder_seed, *self.single_sheet_candidates, *sealed]

    def plant_index(self, target_sheets: int, seed: int) -> int | None:
        """The 1-based plant index of a sealed seed at that size, `None` if it is not one."""
        seeds = self.sealed.get(target_sheets, ())
        return seeds.index(seed) + 1 if seed in seeds else None


def require_drawn_test_seed(seed: int, seed_plan: SeedPlan | None) -> None:
    """Refuse a test-range seed that is retired or not in the drawn plan.

    Raises:
        ValueError: names the seed and says whether it is retired or simply not drawn.
    """
    if seed not in TEST_SEED_RANGE:
        return
    if seed in RETIRED_TEST_SEEDS:
        raise ValueError(f"expected a fresh test seed, found {seed} (retired by ADR-0065)")
    if seed_plan is None or seed not in seed_plan.all_seeds():
        raise ValueError(f"expected test seed {seed} to be in the drawn seed plan, found it is not")


def load_seed_plan(path: Path = DEFAULT_SEED_PLAN_PATH) -> SeedPlan | None:
    """The drawn plan, or `None` while the seeds have not been drawn yet (file absent)."""
    if not path.is_file():
        return None
    return SeedPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))
