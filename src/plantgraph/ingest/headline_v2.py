"""The headline corpus preset for the v2 generator, and the search that sizes it in sheets.

The v2 twin of `headline.py` (which stays untouched). A **headline corpus** is one of the synthetic
plants the thesis's main claim is measured on; its size is counted in **sheets** (drawing pages),
while the generator is sized in **units** (process areas), so `smallest_n_units_v2` converts one
into the other. Unlike v1, the sheet count comes from the planner itself (`plan_plant`, no pyDEXPI),
not from a formula.

Corpus ids carry the generator version `g21` (v2.1, ADR-0065): `D100g21` is the dev corpus (seed 1)
of about 100 sheets, `H100g21p3` the third of the five drawn sealed plants of that size,
`X100g21s211` any other tuning plant; see `headline_corpus_id_v2`. The drawn test seeds live in
`seed_plan.py`; `TEST_SEEDS_V2` below is the superseded first measurement's table.

**Seed ranges** (design vocabulary 14.5). Seeds 0-999 are dev and tuning seeds: every composition
sweep stays inside them. Seeds 5000-5999 are test seeds, never looked at while tuning; the ones a
corpus will use are written down in `TEST_SEEDS_V2` before that corpus is generated.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.graph import schema
from plantgraph.ingest.headline import SizeSearchResult
from plantgraph.ingest.seed_plan import TEST_SEED_RANGE, SeedPlan, require_drawn_test_seed

#: the dev corpora use this seed; every other seed is a test corpus (ADR-0045's rule)
DEV_SEED = 1

#: seeds 0-999 are free to tune on; 5000-5999 (`TEST_SEED_RANGE`) are reserved for test plants
TUNING_SEEDS = range(0, 1000)

#: The FIRST measurement's table (ADR-0059), kept for its records and the hygiene check; EXP-0008
#: draws fresh seeds (`SeedPlan`). Target sheets -> the one test seed of that size. 3, 10 and 30
#: sheets are nested prefixes of one
#: plant (as v1's seed 3 was), so they share a seed. The 1-sheet seed is the first one in 5100-5399
#: whose one-unit plan fits on one sheet (`first_single_sheet_seed`; the scan is re-run in a test).
TEST_SEEDS_V2: dict[int, int] = {
    1: 5100,
    3: 5001,
    10: 5001,
    30: 5001,
    100: 5002,
    1000: 5003,
}

#: the duplication rate the ids call "the preset"; any other rate adds a `d<percent>` suffix
_PRESET_DUPLICATION_RATE = 0.25


class SplitConfigV2(SplitConfig):
    """A `SplitConfig` whose equipment classes are written sorted, so the JSON is reproducible.

    The base class keeps a `set`, whose JSON order follows `PYTHONHASHSEED`; v2 records must be
    byte-identical run to run. It still reads back as a plain `SplitConfig`.
    """

    @field_serializer("equipment_classes")
    def _sorted_classes(self, classes: set[str]) -> list[str]:
        return sorted(classes)


class HeadlinePresetV2(BaseModel):
    """How every v2 headline corpus is generated and split."""

    model_config = ConfigDict(frozen=True)

    #: ADR-0028: a quarter of the equipment with cross-sheet neighbours is also drawn as a
    #: reference elsewhere; the sensitivity runs at 0 and 0.5 override this
    duplication_rate: float = Field(default=0.25, ge=0.0, le=1.0)
    #: the v2 generator draws its own sheets, so no per-sheet budget is used; any valid value
    sheet_equipment_budget: int = 16
    connector_label_detail: ConnectorLabelDetail = ConnectorLabelDetail.DRAWING_ONLY
    exact_match_tags: bool = True

    def generator_config(self, n_units: int, seed: int) -> GeneratorConfigV2:
        """The generator settings for a plant of `n_units` units."""
        return GeneratorConfigV2(n_units=n_units, seed=seed)

    def split_config(self, seed: int) -> SplitConfigV2:
        """The splitter settings: honour the generator's own sheets, with the v2 class set."""
        return SplitConfigV2(
            strategy="by_sheet_group",
            sheet_equipment_budget=self.sheet_equipment_budget,
            seed=seed,
            duplication_rate=self.duplication_rate,
            equipment_classes=set(schema.EQUIPMENT_CLASSES),
            connector_label_detail=self.connector_label_detail,
            exact_match_tags=self.exact_match_tags,
        )


def smallest_n_units_v2(
    target_sheets: int, preset: HeadlinePresetV2, seed: int
) -> SizeSearchResult:
    """The fewest units whose planned plant has at least `target_sheets` sheets.

    Units are drawn in order and the first *n* units of a big plant equal the *n*-unit plant
    (planner prefix stability), so one plan of `target_sheets` units is enough (every unit is
    at least one sheet); the result is then confirmed by planning exactly `n_units` units.

    Raises:
        ValueError: if `target_sheets` is below 1, or if the confirming plan disagrees.
    """
    if target_sheets < 1:
        raise ValueError(f"expected target_sheets >= 1, found {target_sheets}")
    big_plan = plan_plant(preset.generator_config(target_sheets, seed))
    total = 0
    for n_units, unit in enumerate(big_plan.units, start=1):
        total += unit.sheets.sheet_count
        if total >= target_sheets:
            return _confirmed(
                target_sheets, n_units, total, total - unit.sheets.sheet_count, preset, seed
            )
    raise ValueError(f"{target_sheets} units plan only {total} sheets, not {target_sheets}")


def _confirmed(
    target_sheets: int,
    n_units: int,
    predicted: int,
    one_unit_fewer: int,
    preset: HeadlinePresetV2,
    seed: int,
) -> SizeSearchResult:
    """Plan exactly `n_units` units and insist it has the sheets the prefix sum promised."""
    planned = plan_plant(preset.generator_config(n_units, seed)).sheet_count
    if planned != predicted:
        raise ValueError(
            f"expected {predicted} sheets for {n_units} units (prefix sum), the {n_units}-unit "
            f"plan has {planned}: the planner is not prefix-stable"
        )
    return SizeSearchResult(
        target_sheets=target_sheets,
        n_units=n_units,
        predicted_sheets=predicted,
        predicted_sheets_one_unit_fewer=one_unit_fewer,
    )


def headline_corpus_id_v2(
    target_sheets: int,
    seed: int,
    duplication_rate: float = _PRESET_DUPLICATION_RATE,
    seed_plan: SeedPlan | None = None,
) -> str:
    """The id of a v2.1 headline corpus, `<role letter><sheets>g21[...]`.

    - `D100g21` the dev seed; `X100g21s211` any other tuning seed (seed spelled out).
    - `H100g21p3` the third drawn sealed plant of that size; `H3g21` / `H10g21` / `H30g21` the
      ladder plant; `H1g21` a drawn 1-sheet candidate; `VAL100g21` the re-validation plant.
    - A duplication rate other than the preset's 0.25 adds `d0` / `d50` / `d100` (after the plant).

    Raises:
        ValueError: a test-range seed that is retired, or not in `seed_plan` (not drawn yet).
    """
    rate = (
        "" if duplication_rate == _PRESET_DUPLICATION_RATE else f"d{round(duplication_rate * 100)}"
    )
    return f"{_role_stem(target_sheets, seed, seed_plan)}{rate}"


def _role_stem(target_sheets: int, seed: int, seed_plan: SeedPlan | None) -> str:
    if seed == DEV_SEED:
        return f"D{target_sheets}g21"
    if seed not in TEST_SEED_RANGE:
        return f"X{target_sheets}g21s{seed}"
    return _test_role_stem(target_sheets, seed, seed_plan)


def _test_role_stem(target_sheets: int, seed: int, seed_plan: SeedPlan | None) -> str:
    require_drawn_test_seed(seed, seed_plan)
    assert seed_plan is not None  # require_drawn_test_seed raised otherwise
    index = seed_plan.plant_index(target_sheets, seed)
    if index is not None:
        return f"H{target_sheets}g21p{index}"
    if seed_plan.validation.get(target_sheets) == seed:
        return f"VAL{target_sheets}g21"
    is_ladder = target_sheets in (3, 10, 30) and seed == seed_plan.ladder_seed
    if is_ladder or (target_sheets == 1 and seed in seed_plan.single_sheet_candidates):
        return f"H{target_sheets}g21"
    raise ValueError(
        f"expected seed {seed} to be drawn for {target_sheets} sheets, found it is not"
    )


def first_single_sheet_seed(first: int, last: int) -> int:
    """The first seed in `first..last` whose one-unit plant is drawn on one sheet (the H1 rule).

    Raises:
        ValueError: if no seed in the range qualifies.
    """
    preset = HeadlinePresetV2()
    for seed in range(first, last + 1):
        if plan_plant(preset.generator_config(1, seed)).sheet_count == 1:
            return seed
    raise ValueError(f"expected a one-sheet one-unit plant among seeds {first}..{last}, found none")
