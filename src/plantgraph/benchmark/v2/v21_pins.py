"""Frozen copies of every shared table the v2.1 generator draws from (design v2.2 section 9, T0).

v2.1 corpora must stay byte-reproducible after v2.2 lands (see the goldens in
`tests/v2/test_v21_goldens.py`). A random draw reads its table in order, so adding one entry to a
shared table silently changes every draw made from it. These `V21_*` pins are the same trick as the
`V1_*` pins in `graph/schema.py`: the v2.1 code reads the pin, v2.2 may grow the live name.

The pins are read-only (`MappingProxyType`, tuples), so growing a table means copying it, never
editing it in place. Enum members are pinned by value because the enums live in `vocabulary.py`,
which imports this module.

If a golden fails, the change is wrong, never the pin.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType


def _frozen_decks(decks: Mapping[str, Mapping[str, int]]) -> Mapping[str, Mapping[str, int]]:
    """A read-only view of a table of decks (card -> copies), read-only at both levels."""
    return MappingProxyType({key: MappingProxyType(dict(cards)) for key, cards in decks.items()})


#: role -> {valve or fitting class: copies in the deck}; read by `role_deck_variants`.
V21_ROLE_CLASSES = _frozen_decks(
    {
        "block_valve": {"GateValve": 2, "ButterflyValve": 1},
        "vent_drain_valve": {"GateValve": 2, "BallValve": 1},
        "tank_bottom_drain": {"GateValve": 2, "AngleBallValve": 1},
        "control_valve_body": {"GlobeValve": 2, "BallValve": 1, "ButterflyValve": 1},
        "letdown_control_valve_body": {"AngleValve": 2, "AngleGlobeValve": 1, "AngleBallValve": 1},
        "pressure_tap_root": {"BallValve": 2, "NeedleValve": 1},
        "dosing_isolation": {"GateValve": 2, "StraightwayValve": 1},
        "vessel_psv": {"SpringLoadedGlobeSafetyValve": 2, "SpringLoadedAngleGlobeSafetyValve": 1},
        "flow_element_liquid": {"FlowMeasuringElement": 2, "ElectromagneticFlowMeter": 1},
        "flow_element_gas": {"FlowMeasuringElement": 2, "VenturiTube": 1, "FlowNozzle": 1},
        "sight_glass": {"SightGlass": 2, "IlluminatedSightGlass": 1},
        "skillet": {"PipeFlangeSpade": 1, "PipeFlangeSpacer": 1},
    }
)

#: The purge-connection meter deck: "plain" (no meter) twice, the rotameter once.
V21_PURGE_METER_DECK: tuple[str, ...] = ("plain", "plain", "VariableAreaFlowMeter")

#: deck key -> {card: copies}, one deck per axis of a pattern; read by `pattern_deck_variants`.
V21_PATTERN_DECKS = _frozen_decks(
    {
        "U4.tank_count": {"2": 1, "3": 1, "4": 1},
        "U4.transfer_pump": {"CentrifugalPump": 2, "RotaryPump": 1},
        "U4.metering": {
            "none": 4,
            "MassFlowMeasuringElement": 1,
            "PositiveDisplacementFlowMeter": 1,
            "TurbineFlowMeter": 1,
            "VolumeFlowMeasuringElement": 1,
        },
        "U4.manifold": {"GateValve": 2, "PlugValve": 1},
        "U4.tank_service": {"flammable": 1, "non_flammable": 1},
        "U6.vessel": {"PressureVessel": 2, "GravitationalSeparator": 1},
        "U1.vacuum": {"none": 2, "air_ejector": 1, "liquid_ring": 1},
        "U1.condenser": {"TubularHeatExchanger": 2, "AirCoolingSystem": 1},
        "U1.feed_preheater": {"absent": 1, "present": 1},
        "U1.reflux_sight_glass": {"absent": 1, "present": 1},
        "U5.exchanger_count": {"2": 1, "3": 1, "4": 1},
        "U5.exchanger": {"TubularHeatExchanger": 2, "PlateHeatExchanger": 1},
        "U5.trim_heater": {"absent": 1, "ElectricHeater": 1},
        "U5.utility": {"steam": 1, "cooling_water": 1},
        "U2.compressor": {
            "CentrifugalCompressor": 2,
            "ReciprocatingCompressor": 1,
            "RotaryCompressor": 1,
        },
        "U2.aftercooler": {"TubularHeatExchanger": 2, "AirCoolingSystem": 1},
        "U2.suction_filter": {"absent": 1, "present": 1},
        "U2.discharge_ko_drum": {"absent": 1, "present": 1},
        "U3.reactor": {"plain": 2, "agitated": 1},
        "U8.mixer": {"StaticMixer": 2, "RotaryMixer": 1, "EjectorPump": 1},
        "U8.agitated_vessel": {"absent": 1, "present": 1},
        "U8.additive_injection": {"plain": 1, "InLineMixer": 1},
    }
)

#: Train naming conventions: the options of each draw in order, with their weights.
V21_ON_OFF_LETTERS: tuple[str, ...] = ("X", "Y")
V21_ON_OFF_LETTER_WEIGHTS: tuple[int, int] = (1, 1)
V21_SPARE_NAMINGS: tuple[str, ...] = ("suffix", "consecutive")
V21_SPARE_NAMING_WEIGHTS: tuple[int, int] = (3, 2)
