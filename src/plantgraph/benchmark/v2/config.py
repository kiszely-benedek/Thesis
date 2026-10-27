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

    #: a hand switch (start/stop) on a motor-driven machine; 1.0 (user, 2026-10-26): every drawn
    #: motor in the real samples has one
    p_motor_hs: Probability = 1.0
    p_cascade: Probability = 0.5  # master controller feeding a slave per eligible slot
    p_split_range: Probability = 0.0  # one controller, two valves; off: one unconfirmed case


#: Equipment that gets a set of monitoring points; pumps, tanks, filters, mixers, agitators and
#: ejectors are left out because their patterns already give them a fixed instrument set.
MONITORED_MAJOR_CLASSES: frozenset[str] = frozenset(
    member.value
    for member in (
        NodeClass.PROCESS_COLUMN,
        NodeClass.PRESSURE_VESSEL,
        NodeClass.GRAVITATIONAL_SEPARATOR,
        NodeClass.SCRUBBING_SEPARATOR,
        NodeClass.TUBULAR_HEAT_EXCHANGER,
        NodeClass.PLATE_HEAT_EXCHANGER,
        NodeClass.AIR_COOLING_SYSTEM,
        NodeClass.ELECTRIC_HEATER,
        NodeClass.FURNACE,
        NodeClass.CENTRIFUGAL_COMPRESSOR,
        NodeClass.RECIPROCATING_COMPRESSOR,
        NodeClass.ROTARY_COMPRESSOR,
    )
)


class IntRange(BaseModel):
    """An inclusive whole-number range; a draw from it is uniform."""

    low: int = Field(ge=0)
    high: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> IntRange:
        if self.low > self.high:
            raise ValueError(f"expected low <= high, got {self.low} > {self.high}")
        return self


def _default_monitor_variable_weights() -> dict[Literal["T", "P"], float]:
    return {"T": 1.0, "P": 1.0}


class InstrumentDensity(BaseModel):
    """How many instruments the patterns add beyond the control loops (pid-vocabulary 13.5).

    Every value is declared, not measured: a neutral choice (even odds for an optional item) or
    a value chosen so the instruments-to-valves ratio lands in the acceptance band (13.7).
    """

    #: monitoring points per major item, each a nozzle-mounted gauge or transmitter
    monitor_points_per_major_item: IntRange = IntRange(low=5, high=7)
    monitor_variable_weights: dict[Literal["T", "P"], float] = Field(
        default_factory=_default_monitor_variable_weights
    )
    p_monitor_local: Probability = 0.7  # a gauge (`TI`/`PI`), else `TT -> TI` / `PT -> PI`
    tray_temperature_points: IntRange = IntRange(low=2, high=4)
    reactor_temperature_points: IntRange = IntRange(low=3, high=5)
    p_optional_instrument: Probability = 0.5  # every `[...]` instrument of base 7.2
    p_point_level_switch: Probability = 0.5  # `LSH -> LAH`, `LSL -> LAL`
    p_bearing_temperature: Probability = 0.5  # `TT -> TIAH` on pumps and compressors
    p_indicator_alarm: Probability = 0.5  # alarm letters on an indicator bubble
    p_motor_current: Probability = 0.5  # `IT -> II` on a compressor
    p_vfd: Probability = 0.5  # variable speed on a compressor or dosing pump
    p_multivariable: Probability = 0.5  # `UC` on the reactor

    @field_validator("monitor_variable_weights")
    @classmethod
    def _check_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        _require_positive(weights, "monitor_variable_weights")
        return weights


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


#: the patterns each flowsheet slot may hold (design 8.1); U10 (desalter) is deliberately absent:
#: it is not generated (decided 2026-10-25), so it has no weight and no slot entry
CONDITIONING_PATTERNS: frozenset[str] = frozenset({"U5", "U7", "U8"})
CORE_PATTERNS: frozenset[str] = frozenset(
    {"U3+U2", "U3", "U6"}
)  # "U3+U2": reactor, then compressor
SEPARATION_PATTERNS: frozenset[str] = frozenset({"U1", "U6"})
MAX_CONDITIONING_UNITS = 2  # Conditioning{0..2}
MAX_SEPARATION_UNITS = 3  # Separation{1..3}


def _default_conditioning_count_weights() -> dict[int, float]:
    return {0: 1.0, 1: 1.0, 2: 1.0}


def _default_conditioning_weights() -> dict[str, float]:
    return {"U5": 1.0, "U7": 1.0, "U8": 1.0}


def _default_core_weights() -> dict[str, float]:
    return {"U3+U2": 1.0, "U3": 1.0, "U6": 2.0}


def _default_separation_count_weights() -> dict[int, float]:
    return {1: 1.0, 2: 1.0, 3: 1.0}


def _default_separation_weights() -> dict[str, float]:
    return {"U1": 1.0, "U6": 1.0}


def _require_keys_within(weights: dict[str, float], allowed: frozenset[str], name: str) -> None:
    unknown = sorted(set(weights) - allowed)
    if unknown:
        raise ValueError(
            f"{name} has unknown patterns {unknown}; expected a subset of {sorted(allowed)}"
        )


def _require_counts_within(weights: dict[int, float], low: int, high: int, name: str) -> None:
    outside = sorted(count for count in weights if not low <= count <= high)
    if outside:
        raise ValueError(f"{name} has counts {outside} outside the grammar's range {low}..{high}")


class FlowsheetKnobs(BaseModel):
    """How the flowsheet grammar draws a train and which extra streams it may add (base 8.1).

    Every weight is declared, not measured (pid-vocabulary 13.2): uniform where no source ranks
    the choices. A weight is for a draw from the master stream; a pattern the generator does not
    have yet is dropped from the draw by the planner, so these defaults stay valid as patterns
    arrive.
    """

    #: how many conditioning units (U5 / U7 / U8) sit between the feed farm and the core
    conditioning_count_weights: dict[int, float] = Field(
        default_factory=_default_conditioning_count_weights
    )
    conditioning_weights: dict[str, float] = Field(default_factory=_default_conditioning_weights)
    core_weights: dict[str, float] = Field(default_factory=_default_core_weights)
    separation_count_weights: dict[int, float] = Field(
        default_factory=_default_separation_count_weights
    )
    separation_weights: dict[str, float] = Field(default_factory=_default_separation_weights)
    #: both are read by patterns that arrive later (a column side draw, a blending additive feed)
    p_side_draw: Probability = 0.2  # a column side product to a later tank
    #: a second feed from an earlier train's product tanks; not implemented in v2.0, so only 0.0
    #: is accepted (an unused knob at 0.2 would make every `ingest.json` claim an edge not drawn)
    p_shared_farm_feed: Probability = 0.0

    @field_validator(
        "conditioning_count_weights",
        "conditioning_weights",
        "core_weights",
        "separation_count_weights",
        "separation_weights",
    )
    @classmethod
    def _check_positive(cls, weights: dict[str, float]) -> dict[str, float]:
        _require_positive({str(key): value for key, value in weights.items()}, "flowsheet weights")
        return weights

    @field_validator("p_shared_farm_feed")
    @classmethod
    def _check_farm_feed_unused(cls, value: float) -> float:
        if value != 0.0:
            raise ValueError(
                f"p_shared_farm_feed is not implemented in v2.0: expected 0.0, got {value}"
            )
        return value

    @model_validator(mode="after")
    def _check_slots(self) -> FlowsheetKnobs:
        _require_keys_within(
            self.conditioning_weights, CONDITIONING_PATTERNS, "conditioning_weights"
        )
        _require_keys_within(self.core_weights, CORE_PATTERNS, "core_weights")
        _require_keys_within(self.separation_weights, SEPARATION_PATTERNS, "separation_weights")
        _require_counts_within(
            self.conditioning_count_weights, 0, MAX_CONDITIONING_UNITS, "conditioning_count_weights"
        )
        _require_counts_within(
            self.separation_count_weights, 1, MAX_SEPARATION_UNITS, "separation_count_weights"
        )
        return self


class GeneratorConfigV2(BaseModel):
    """Everything the v2 generator reads. Identity fields first, then the knob groups.

    There is no per-class equipment weight: which class a role gets is a variant deck (`deck.py`,
    pid-vocabulary 13.4), and a second weight would overlap it.
    """

    generator_version: Literal["v2"] = "v2"
    plant_id: str = Field(default="plant0", pattern=r"^[a-z0-9]+$")
    seed: int = 0
    n_units: int = Field(ge=1)  # no declared default: the size search picks it
    sheets: SheetKnobs = Field(default_factory=SheetKnobs)
    trims: TrimConvention = Field(default_factory=TrimConvention)
    instruments: InstrumentConvention = Field(default_factory=InstrumentConvention)
    density: InstrumentDensity = Field(default_factory=InstrumentDensity)
    patterns: PatternKnobs = Field(default_factory=PatternKnobs)
    flowsheet: FlowsheetKnobs = Field(default_factory=FlowsheetKnobs)
