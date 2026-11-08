"""Which plants EXP-0008 builds, with their ids, sheet counts and seeds (review-fixes §5.1).

The launcher's shell scripts ask this module instead of keeping their own tables: the seeds come
from the drawn `SeedPlan` (pre-registration part A), and `--smoke` swaps in tiny plants with dev
seeds so the whole chain can run in minutes without touching a test seed.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, headline_corpus_id_v2
from plantgraph.ingest.seed_plan import PLANTS_PER_SIZE, SeedPlan

#: the ladder's four sizes; 3, 10 and 30 sheets are nested prefixes of one plant
LADDER_SHEETS = (1, 3, 10, 30)
SEALED_SIZES = (100, 1000)
#: a smoke plant never has more sheets than this
SMOKE_SHEETS = 10
_SMOKE_SEED_BASE = 20
_PRESET_DUPLICATION = 0.25
KINDS = (
    "dev",
    "validation",
    "ladder",
    "sealed",
    "descriptive",
    "p4",
    "p3",
    "demo",
)


class PlantSpec(BaseModel):
    """One plant to build: its corpus id, size, seed and duplication rate."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    sheets: int
    seed: int
    duplication_rate: float = _PRESET_DUPLICATION
    #: a tag-variant (V) corpus of EXP-0004: built by `exp0004 build`, not by `ingest synthetic`
    variant: bool = False


class SeedTable(BaseModel):
    """The seeds of every test-role plant, from the drawn plan or invented for the smoke."""

    model_config = ConfigDict(frozen=True)

    validation: dict[int, int]
    ladder_seed: int
    single_sheet_candidates: tuple[int, ...]
    sealed: dict[int, tuple[int, ...]]

    @classmethod
    def from_plan(cls, plan: SeedPlan) -> SeedTable:
        """The table of the drawn seeds."""
        return cls(
            validation=plan.validation,
            ladder_seed=plan.ladder_seed,
            single_sheet_candidates=plan.single_sheet_candidates,
            sealed=plan.sealed,
        )

    @classmethod
    def smoke(cls) -> SeedTable:
        """Dev-range seeds, all distinct, none in the test range."""
        base = _SMOKE_SEED_BASE
        count = PLANTS_PER_SIZE
        return cls(
            validation={100: base, 1000: base + 1},
            ladder_seed=base + 2,
            single_sheet_candidates=(base + 3,),
            sealed={
                100: tuple(range(base + 10, base + 10 + count)),
                1000: tuple(range(base + 20, base + 20 + count)),
            },
        )


def single_sheet_seed(candidates: Sequence[int]) -> int:
    """The first candidate whose one-unit plant is drawn on one sheet (the ladder's H1 rule).

    Raises:
        ValueError: no candidate qualifies.
    """
    preset = HeadlinePresetV2()
    for seed in candidates:
        if plan_plant(preset.generator_config(1, seed)).sheet_count == 1:
            return seed
    raise ValueError(
        f"expected a one-sheet one-unit plant among seeds {list(candidates)}, found none"
    )


class Plan:
    """The plants of EXP-0008, listed by role."""

    def __init__(self, seeds: SeedTable, smoke: bool = False) -> None:
        self._seeds = seeds
        self._smoke = smoke

    def _sheets(self, sheets: int) -> int:
        return min(sheets, SMOKE_SHEETS) if self._smoke else sheets

    def _spec(
        self, corpus_id: str, sheets: int, seed: int, rate: float = _PRESET_DUPLICATION
    ) -> PlantSpec:
        return PlantSpec(
            corpus_id=corpus_id, sheets=self._sheets(sheets), seed=seed, duplication_rate=rate
        )

    def dev(self) -> list[PlantSpec]:
        """Dev and tuning plants (seeds 1 and 211): never test seeds.

        The EXP-0004 dev corpus `D100g21d100Vf` is built by `exp0004 build`, not listed here.
        """
        return [
            self._spec("D100g21", 100, 1),
            self._spec("D1000g21", 1000, 1),
            self._spec("X100g21s211", 100, 211),
        ]

    def validation(self) -> list[PlantSpec]:
        """The two re-validation plants of gate G1."""
        return [self._spec(f"VAL{n}g21", n, self._seeds.validation[n]) for n in SEALED_SIZES]

    def ladder(self) -> list[PlantSpec]:
        """1, 3, 10 and 30 sheets."""
        one = self._spec("H1g21", 1, self._one_sheet_seed())
        return [one] + [
            self._spec(f"H{n}g21", n, self._seeds.ladder_seed) for n in LADDER_SHEETS[1:]
        ]

    def _one_sheet_seed(self) -> int:
        candidates = self._seeds.single_sheet_candidates
        return candidates[0] if self._smoke else single_sheet_seed(candidates)

    def sealed(self, sheets: int | None = None) -> list[PlantSpec]:
        """Five sealed plants per size (or one size only)."""
        sizes = SEALED_SIZES if sheets is None else (sheets,)
        return [
            self._spec(f"H{n}g21p{k}", n, seed)
            for n in sizes
            for k, seed in enumerate(self._seeds.sealed[n], start=1)
        ]

    def descriptive(self) -> list[PlantSpec]:
        """Duplication points d0 and d50 of the first 100-sheet plant."""
        seed = self._seeds.sealed[100][0]
        return [
            self._spec("H100g21p1d0", 100, seed, 0.0),
            self._spec("H100g21p1d50", 100, seed, 0.5),
        ]

    def demo(self) -> list[PlantSpec]:
        """The plant the user's database ends on (ADR-0064, amended): plant 1 at 1,000 sheets."""
        return [self.sealed(1000)[0]]

    def p4(self) -> list[PlantSpec]:
        """The five 1,000-sheet plants as tag-variant corpora (E1-E4), preset duplication."""
        return [_as_variant(p) for p in self.sealed(1000)]

    def p3(self) -> list[PlantSpec]:
        """The registered four-corpus set on plant 1, then the other four 1,000-sheet V corpora."""
        small, large = self.sealed(100)[0], self.sealed(1000)[0]
        registered = [
            _as_variant(small),
            _as_variant(small, 1.0),
            _as_variant(large),
            _as_variant(large, 1.0),
        ]
        return registered + self.p4()[1:]

    def by_kind(self, kind: str) -> list[PlantSpec]:
        """The plants of one role; `kind` is one of `KINDS`."""
        if kind not in KINDS:
            raise ValueError(f"expected one of {KINDS}, found {kind!r}")
        if kind == "sealed":
            return self.sealed()
        return list(getattr(self, kind)())


def _as_variant(plant: PlantSpec, rate: float | None = None) -> PlantSpec:
    """The tag-variant corpus of a plant: id + `d100` when the rate is 1.0, then `V`."""
    use = plant.duplication_rate if rate is None else rate
    stem = plant.corpus_id
    suffix = "" if use == _PRESET_DUPLICATION else f"d{round(use * 100)}"
    return plant.model_copy(
        update={"corpus_id": f"{stem}{suffix}V", "duplication_rate": use, "variant": True}
    )


def checked_id(spec: PlantSpec, seeds: SeedPlan | None) -> str:
    """The id `headline_corpus_id_v2` composes for a plain plant; used to cross-check the plan."""
    return headline_corpus_id_v2(spec.sheets, spec.seed, spec.duplication_rate, seeds)
