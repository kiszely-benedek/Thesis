"""The headline corpus preset for the v2 generator, and the search that sizes it in sheets.

The v2 twin of `headline.py` (which stays untouched). A **headline corpus** is one of the synthetic
plants the thesis's main claim is measured on; its size is counted in **sheets** (drawing pages),
while the generator is sized in **units** (process areas), so `smallest_n_units_v2` converts one
into the other. Unlike v1, the sheet count comes from the planner itself (`plan_plant`, no pyDEXPI),
not from a formula.

Corpus ids carry the version: `D100g2` is the dev corpus (seed 1) of about 100 sheets, `H100g2` a
test corpus (a fresh seed); see `headline_corpus_id_v2`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.graph import schema
from plantgraph.ingest.headline import SizeSearchResult

#: the dev corpora use this seed; every other seed is a test corpus (ADR-0045's rule)
DEV_SEED = 1


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


def headline_corpus_id_v2(target_sheets: int, seed: int) -> str:
    """`D100g2` for the dev seed, `H100g2` for any other (test) seed."""
    prefix = "D" if seed == DEV_SEED else "H"
    return f"{prefix}{target_sheets}g2"
