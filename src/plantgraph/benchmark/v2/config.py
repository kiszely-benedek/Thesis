"""Every setting of the v2 plant generator (design notes generator-v2-pid-vocabulary and -realism).

`GeneratorConfigV2` is a separate type from v1's `GeneratorConfig`, never a new field on it: v1's
JSON is stored in every old `ingest.json` and must stay byte-identical. The `generator_version`
discriminator tells the two apart when a config is read back from JSON.

A **probability** here is a *declared design parameter*, not a measured frequency: the real
sheets the design cites give ranges, never a per-item rate. The comment on each field names where
its value comes from. Knobs the design declares without a value (units per train, pattern-choice
weights, instrument density) are not here yet; they arrive with the module that uses them.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.graph.schema_classes import NodeClass

Probability = Annotated[float, Field(ge=0.0, le=1.0)]

#: The 25 equipment leaves of the schema allowlist minus `SpiralHeatExchanger` and
#: `ElectricalSeparator`, which stay importable but are not generated (decided 2026-10-25).
GENERATED_EQUIPMENT_CLASSES: frozenset[str] = frozenset(
    member.value
    for member in (
        NodeClass.CENTRIFUGAL_PUMP,
        NodeClass.RECIPROCATING_PUMP,
        NodeClass.ROTARY_PUMP,
        NodeClass.EJECTOR_PUMP,
        NodeClass.CENTRIFUGAL_COMPRESSOR,
        NodeClass.RECIPROCATING_COMPRESSOR,
        NodeClass.ROTARY_COMPRESSOR,
        NodeClass.AIR_EJECTOR,
        NodeClass.TANK,
        NodeClass.PRESSURE_VESSEL,
        NodeClass.PROCESS_COLUMN,
        NodeClass.TUBULAR_HEAT_EXCHANGER,
        NodeClass.PLATE_HEAT_EXCHANGER,
        NodeClass.AIR_COOLING_SYSTEM,
        NodeClass.ELECTRIC_HEATER,
        NodeClass.FURNACE,
        NodeClass.GRAVITATIONAL_SEPARATOR,
        NodeClass.SCRUBBING_SEPARATOR,
        NodeClass.LIQUID_FILTER,
        NodeClass.GAS_FILTER,
        NodeClass.STATIC_MIXER,
        NodeClass.ROTARY_MIXER,
        NodeClass.AGITATOR,
    )
)

if not GENERATED_EQUIPMENT_CLASSES <= EQUIPMENT_CLASSES:  # guards a stale list after a schema edit
    raise ImportError(
        f"GENERATED_EQUIPMENT_CLASSES must be equipment classes; "
        f"not in the schema: {sorted(GENERATED_EQUIPMENT_CLASSES - EQUIPMENT_CLASSES)}"
    )


class VentDrainConvention(str, Enum):
    """Whether every vessel gets a valved vent and drain (the sources disagree, design 6.11)."""

    KLM_ALL = "klm_all"  # a valved drain on every column and vessel
    HNF_CLOSED = "hnf_closed"  # only where the drain joins a closed system


CondensateMode = Literal["trap", "trap_station", "drain_pot"]
PumpPressureMode = Literal["per_pump_pi", "header_pt"]
PumpSetGroup = Literal["with_suction_vessel", "own_sheet"]


def _default_condensate_weights() -> dict[CondensateMode, float]:
    return {"trap": 2.0, "trap_station": 1.0, "drain_pot": 1.0}


def _default_pump_pressure_weights() -> dict[PumpPressureMode, float]:
    return {"per_pump_pi": 3.0, "header_pt": 1.0}


def _default_pump_set_group_weights() -> dict[PumpSetGroup, float]:
    return {"with_suction_vessel": 2.0, "own_sheet": 1.0}


def _require_positive(weights: dict[str, float], name: str) -> None:
    non_positive = {key: value for key, value in weights.items() if value <= 0}
    if non_positive:
        raise ValueError(f"{name} must be strictly positive; got non-positive {non_positive}")


class SheetKnobs(BaseModel):
    """How many items one drawn sheet may hold (design 7.1)."""

    #: real sheets carry 1-16 equipment items; 4 of 16 carry only 1-2 (design 7.1, Q6 = A)
    min_equipment_per_sheet: int = Field(default=1, ge=1, le=16)
    max_equipment_per_sheet: int = Field(default=16, ge=1, le=16)
    #: a declared cap on drawn symbols before the off-page stubs are added (base 9)
    max_symbols_before_stubs: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def _check_range(self) -> SheetKnobs:
        if self.min_equipment_per_sheet > self.max_equipment_per_sheet:
            raise ValueError(
                "min_equipment_per_sheet must not exceed max_equipment_per_sheet; got "
                f"min={self.min_equipment_per_sheet}, max={self.max_equipment_per_sheet}"
            )
        return self


class TrimConvention(BaseModel):
    """Chances of the standard local arrangements ("trims") around a machine or line.

    A trim is a fixed set of fittings a drawing repeats: a pump's suction strainer, a control
    valve's block-and-bypass valves. Values: generator-v2-realism.md 6 and the pid-vocabulary
    note 5.4/7.1; all declared parameters.
    """

    p_pump_vent_drain: Probability = 1.0
    p_min_flow: Probability = 0.3
    p_cv_station: Probability = 0.6  # lowered from 0.8 by the real samples (D1: 5 of 8)
    p_cv_reducers: Probability = 0.5
    p_cv_drain: Probability = 0.3
    p_limit_switches: Probability = 0.5
    p_psv_blocks: Probability = 0.5
    p_psv_drain: Probability = 0.3
    vent_drain_convention: VentDrainConvention = VentDrainConvention.KLM_ALL
    p_hnf_vent_drain: Probability = 0.3  # the HNF reading: draw the vent/drain with this chance
    p_thermal_relief: Probability = 1.0
    p_exchanger_vent_drain: Probability = 0.5
    p_battery_limit: Probability = 0.5
    p_open_drain: Probability = 0.3
    p_skillet: Probability = 0.5
    p_flex_connector: Probability = 0.3
    p_flush_connection: Probability = 0.3
    #: steam condensate removal: a single trap, a trap with blocks and bypass, a drain pot
    condensate_mode_weights: dict[CondensateMode, float] = Field(
        default_factory=_default_condensate_weights
    )
    #: pump pressure shown by a local gauge per pump, or by one transmitter on the header
    pump_pressure_mode_weights: dict[PumpPressureMode, float] = Field(
        default_factory=_default_pump_pressure_weights
    )

    @field_validator("condensate_mode_weights", "pump_pressure_mode_weights")
    @classmethod
    def _check_mode_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        _require_positive(weights, "mode weights")
        return weights


class InstrumentConvention(BaseModel):
    """Chances of the optional control-loop shapes (design 5.1, 5.3)."""

    p_motor_hs: Probability = 0.5  # a hand switch (start/stop) on a motor-driven machine
    p_cascade: Probability = 0.5  # master controller feeding a slave per eligible slot
    p_split_range: Probability = 0.0  # one controller, two valves; off: one unconfirmed case


class PatternKnobs(BaseModel):
    """Shape choices inside the process patterns (base 7.1, 7.2; pid-vocabulary 7.1)."""

    p_triple_pump_set: Probability = 0.15  # an A/B/C set instead of A/B
    p_single_pump: Probability = 0.2  # an unspared service pump
    p_column_combined: Probability = 0.3  # a column system drawn on one sheet instead of two
    #: where a pump set is drawn: with its suction vessel, or on a sheet of its own (design 7.1)
    pump_set_group_weights: dict[PumpSetGroup, float] = Field(
        default_factory=_default_pump_set_group_weights
    )

    @field_validator("pump_set_group_weights")
    @classmethod
    def _check_group_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        _require_positive(weights, "pump_set_group_weights")
        return weights

    @model_validator(mode="after")
    def _check_pump_set_chances(self) -> PatternKnobs:
        if self.p_triple_pump_set + self.p_single_pump > 1.0:
            raise ValueError(
                "p_triple_pump_set + p_single_pump must not exceed 1; got "
                f"{self.p_triple_pump_set} + {self.p_single_pump}"
            )
        return self


class FlowsheetKnobs(BaseModel):
    """Extra long-range streams the flowsheet grammar may add (base 8.1)."""

    p_side_draw: Probability = 0.2  # a column side product to a later tank
    p_shared_farm_feed: Probability = 0.2  # a second feed from an earlier train's product tanks


class GeneratorConfigV2(BaseModel):
    """Everything the v2 generator reads. Identity fields first, then the knob groups."""

    generator_version: Literal["v2"] = "v2"
    plant_id: str = Field(default="plant0", pattern=r"^[a-z0-9]+$")
    seed: int = 0
    n_units: int = Field(ge=1)  # no declared default: the size search picks it
    #: weight overrides per equipment class; a class absent here keeps its pattern's own weight
    equipment_weights: dict[str, float] = Field(default_factory=dict)
    sheets: SheetKnobs = Field(default_factory=SheetKnobs)
    trims: TrimConvention = Field(default_factory=TrimConvention)
    instruments: InstrumentConvention = Field(default_factory=InstrumentConvention)
    patterns: PatternKnobs = Field(default_factory=PatternKnobs)
    flowsheet: FlowsheetKnobs = Field(default_factory=FlowsheetKnobs)

    @field_validator("equipment_weights")
    @classmethod
    def _check_equipment_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        unknown = sorted(set(weights) - GENERATED_EQUIPMENT_CLASSES)
        if unknown:
            raise ValueError(
                f"equipment_weights has classes the v2 generator does not generate: {unknown}; "
                f"expected a subset of {sorted(GENERATED_EQUIPMENT_CLASSES)}"
            )
        _require_positive(weights, "equipment_weights")
        return weights
