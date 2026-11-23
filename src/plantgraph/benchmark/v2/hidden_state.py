"""The hidden design state of a v2.2 plant (design generator-v2-2 6.1).

Some handbook rules depend on a quantity an engineer decides first and a drawing never shows: how
many horsepower a pump has, the pressure level of a pipe. The generator samples that **hidden
cause** and derives the visible consequence (a min-flow line, a relief valve size) from it.

The state lives in `GenerationRecordV22` and is read by the rule checks. It is never written to the
DEXPI model, the graph under retrieval, a prompt or a question's gold (ADR-0021: no value, no unit
reaches the data). `pump_power`, `reflux` and `segment_level` are filled; the other maps stay empty
until their tasks.
"""

from __future__ import annotations

from enum import Enum, IntEnum

from pydantic import BaseModel, Field

# ---- declared conventions (design 17.13 R7): constants, never drawn ----------------------------
# Each one stands behind an API 14C omission code, so a reader can see which codes rest on a
# declaration and not on a drawn fact. They are listed in the registry and named in the thesis
# limitations as conventions of the generated plants.

#: R7 a: the furnace has natural draft (no blower or fan is drawn), so SAC A-6.2 d.2, f.2, i.2 hold
FURNACE_NATURAL_DRAFT = True
#: R7 b: a centrifugal pump's discharge piping is rated for its shut-off head (SAC A-7.2 f.2)
CENTRIFUGAL_DISCHARGE_RATED_FOR_SHUTOFF = True
#: R7 c: a utility side is designed for its header pressure (SAC A-10.2 a.2, the PSH item only)
UTILITY_DESIGNED_FOR_HEADER = True
#: R7: roles of vessels with no separated phases, so SAC A-4.2 d.3 (no level switch) holds
NO_SEPARATED_PHASE_ROLES = frozenset({"reactor", "blend_vessel"})

# exception codes of the three kinds the SAC check reports (derived, declared, scope)
DECLARED_NATURAL_DRAFT = "declared:natural_draft"
DECLARED_SHUTOFF_RATED = "declared:discharge_rated_for_shutoff"
DECLARED_UTILITY_HEADER = "declared:utility_designed_for_header"
DECLARED_NO_SEPARATED_PHASES = "declared:no_separated_phases"
SCOPE_NON_HYDROCARBON = "scope:non_hydrocarbon"
SCOPE_VACUUM_SERVICE = "scope:vacuum_service"


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
    #: the tanks of a storage farm drawn non-flammable (design 17.13 R7 i); API 14C A.5 does not
    #: cover chemical storage (A.5.1 p.30), so their items carry `scope:non_hydrocarbon`
    NON_FLAMMABLE = "non_flammable"


class HiddenDesignState(BaseModel):
    """Design quantities no drawing shows; the maps stay empty until later tasks draw them."""

    #: by run (a line number) or by vessel (a node id); see `pressure_levels.py`
    segment_level: dict[str, PressureLevel] = Field(default_factory=dict)
    pump_power: dict[str, PumpPowerBand] = Field(default_factory=dict)  # by pump set id
    reflux: dict[str, RefluxClass] = Field(default_factory=dict)  # by column id
    fluid_of_service: dict[str, FluidClass] = Field(default_factory=dict)  # by line service code
    #: the declared fluid class of each tank (design 17.13 R7 i); the farm's flag overrides the
    #: plant-wide hydrocarbon declaration for that farm's tanks only
    fluid_of_tank: dict[str, FluidClass] = Field(default_factory=dict)
    #: rule id -> item id -> exception code, for the rare item a rule deliberately lets through
    exceptions: dict[str, dict[str, str]] = Field(default_factory=dict)
