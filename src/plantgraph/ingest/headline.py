"""The headline corpus preset and the search that sizes a corpus in sheets.

(Design `realism-units-duplication-reach.md` §3.3; ADR-0025, ADR-0028, ADR-0023.)

A **headline corpus** is one of the synthetic plants the thesis's main claim is
measured on. `HeadlinePreset` is the single place that says how such a plant is
generated and split, so no run can drift from it by retyping flags. The claim's
size axis is counted in **sheets** (drawing pages; ADR-0015: about 10, 100,
1,000), but the generator is sized in **units** (process areas), so
`smallest_n_units` converts one into the other.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig, LoopSpec, ValveSpec
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig


class HeadlinePreset(BaseModel):
    """How every headline corpus is generated and split (1-2 sheets per unit)."""

    model_config = ConfigDict(frozen=True)

    equipment_per_unit_min: int = 18
    equipment_per_unit_max: int = 36
    strategy: str = "by_unit"
    sheet_equipment_budget: int = 18
    connector_label_detail: ConnectorLabelDetail = ConnectorLabelDetail.DRAWING_ONLY
    duplication_rate: float = 0.25
    exact_match_tags: bool = True

    def generator_config(self, n_units: int, seed: int) -> GeneratorConfig:
        """The generator settings for a plant of `n_units` units."""
        return GeneratorConfig(
            n_units=n_units,
            seed=seed,
            equipment_per_unit_min=self.equipment_per_unit_min,
            equipment_per_unit_max=self.equipment_per_unit_max,
        )

    def split_config(self, seed: int) -> SplitConfig:
        """The splitter settings (they do not depend on the plant's size)."""
        return SplitConfig(
            strategy=self.strategy,
            sheet_equipment_budget=self.sheet_equipment_budget,
            seed=seed,
            connector_label_detail=self.connector_label_detail,
            duplication_rate=self.duplication_rate,
            exact_match_tags=self.exact_match_tags,
        )


class SizeSearchResult(BaseModel):
    """The outcome of `smallest_n_units`: the chosen size and what it predicts."""

    target_sheets: int
    n_units: int
    predicted_sheets: int
    #: sheets of the first `n_units - 1` units; below the target by construction
    predicted_sheets_one_unit_fewer: int


class _CountingBuilder:
    """A `PlantBuilder` that only counts equipment per unit and builds nothing.

    It lets `plan_plant` run without pyDEXPI, which is much faster than a
    real build, because only the equipment counts are needed to size a corpus.
    """

    backend_version = "counting-builder"

    def __init__(self) -> None:
        #: unit_no -> number of equipment items added to it
        self.equipment_per_unit: dict[int, int] = {}

    def add_section(self, unit_no: int) -> None:
        self.equipment_per_unit[unit_no] = 0

    def add_equipment(
        self,
        node_id: str,
        node_class: str,
        unit_no: int,
        tag: str,
        tag_prefix: str,
        tag_seq: int,
    ) -> None:
        self.equipment_per_unit[unit_no] += 1

    def add_stream(
        self,
        line_number: str,
        fluid_code: str,
        src_id: str,
        dst_id: str,
        valves: Sequence[ValveSpec],
    ) -> None:
        return None

    def add_control_loop(self, loop: LoopSpec) -> None:
        return None


def smallest_n_units(target_sheets: int, preset: HeadlinePreset, seed: int) -> SizeSearchResult:
    """The fewest units whose predicted sheet count reaches `target_sheets`.

    Under `by_unit`, a unit with `e` equipment gets ceil(e / budget) sheets.
    The generator draws unit sizes in order, so the first n units of a big
    plant are exactly an n-unit plant; one planning pass is enough.

    Raises:
        ValueError: if `target_sheets` is below 1.
    """
    if target_sheets < 1:
        raise ValueError(f"expected target_sheets >= 1, found {target_sheets}")
    sheets_per_unit = _predicted_sheets_per_unit(target_sheets, preset, seed)
    total = 0
    for n_units, sheets in enumerate(sheets_per_unit, start=1):
        total += sheets
        if total >= target_sheets:
            return SizeSearchResult(
                target_sheets=target_sheets,
                n_units=n_units,
                predicted_sheets=total,
                predicted_sheets_one_unit_fewer=total - sheets,
            )
    raise ValueError(
        f"{len(sheets_per_unit)} units predict only {total} sheets, not {target_sheets}"
    )


def _predicted_sheets_per_unit(target_sheets: int, preset: HeadlinePreset, seed: int) -> list[int]:
    """Sheets of each unit of a plant big enough to reach the target."""
    # every unit yields at least one sheet, so `target_sheets` units always suffice
    config = preset.generator_config(n_units=target_sheets, seed=seed)
    builder = _CountingBuilder()
    plan_plant(config, builder)
    budget = preset.sheet_equipment_budget
    counts = [builder.equipment_per_unit[unit_no] for unit_no in sorted(builder.equipment_per_unit)]
    return [-(-count // budget) for count in counts]  # ceiling division


def check_realized_sheets(search: SizeSearchResult, realized_sheets: int) -> None:
    """Confirm a built corpus has the sheets the search predicted.

    Equal to the prediction means: at least the target, and one unit fewer
    would have fallen short.

    Raises:
        ValueError: if the built corpus differs from the prediction.
    """
    if realized_sheets != search.predicted_sheets:
        raise ValueError(
            f"expected {search.predicted_sheets} sheets for {search.n_units} units "
            f"(target {search.target_sheets}), built {realized_sheets}"
        )
    if search.predicted_sheets_one_unit_fewer >= search.target_sheets:
        raise ValueError(
            f"n_units - 1 would already reach target {search.target_sheets}: "
            f"{search.predicted_sheets_one_unit_fewer} sheets"
        )
