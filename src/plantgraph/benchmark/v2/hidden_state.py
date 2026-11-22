"""The hidden design state of a v2.2 plant (design generator-v2-2 6.1).

Some handbook rules depend on a quantity an engineer decides first and a drawing never shows: how
many horsepower a pump has, the pressure level of a pipe. The generator samples that **hidden
cause** and derives the visible consequence (a min-flow line, a relief valve size) from it.

The state lives in `GenerationRecordV22` and is read by the rule checks. It is never written to the
DEXPI model, the graph under retrieval, a prompt or a question's gold (ADR-0021: no value, no unit
reaches the data). In this first version the maps are empty; later tasks fill them.
"""

from __future__ import annotations

from enum import Enum, IntEnum

from pydantic import BaseModel, Field


class PressureLevel(IntEnum):
    """Ordinal pressure level of a piping segment; no pressure values are stored."""

    VAC = 0
    ATM = 1
    LP = 2
    MP = 3
    HP = 4


class PumpPowerBand(str, Enum):
    """Pump power in hp; the band decides the min-flow method (Toghraei 2019 p.313, p.179)."""

    BELOW_5 = "<5"
    B5_20 = "5-20"
    B20_35 = "20-35"
    ABOVE_35 = ">35"


class RefluxClass(str, Enum):
    """Column reflux ratio L/D, low or high (Toghraei 2019 p.309)."""

    LOW = "low"
    HIGH = "high"


class FluidClass(str, Enum):
    """What a line carries; the only basis for drain and relief destinations."""

    HYDROCARBON = "hydrocarbon"
    WATER = "water"
    STEAM = "steam"
    INERT = "inert"


class HiddenDesignState(BaseModel):
    """Design quantities no drawing shows; the maps stay empty until later tasks draw them."""

    segment_level: dict[str, PressureLevel] = Field(default_factory=dict)  # by piping segment id
    pump_power: dict[str, PumpPowerBand] = Field(default_factory=dict)  # by pump set id
    reflux: dict[str, RefluxClass] = Field(default_factory=dict)  # by column id
    fluid_of_service: dict[str, FluidClass] = Field(default_factory=dict)  # by line service code
    #: rule id -> item id -> exception code, for the rare item a rule deliberately lets through
    exceptions: dict[str, dict[str, str]] = Field(default_factory=dict)
