"""The variant decks of the patterns (pid-vocabulary 13.3) and the label a variant gets.

Each axis of a pattern that has alternatives is a deck (`deck.py`): every card is dealt once per
cycle, and a primary option appears twice (Rule V, pid-vocabulary 13.1). Nothing here is a
frequency claim. The two pump-set decks are built from the weights in `PatternKnobs` and
`TrimConvention`, so the config stays the one place those numbers live.
"""

from __future__ import annotations

from collections.abc import Mapping

from plantgraph.benchmark.v2.class_decks import role_deck_variants
from plantgraph.benchmark.v2.config import PatternKnobs, TrimConvention

#: deck key -> {card: copies}; the cards of one axis, table 13.3 of the design
PATTERN_DECKS: dict[str, dict[str, int]] = {
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

PUMP_SET_GROUP_DECK = "pump_set.group"
PUMP_SET_PRESSURE_DECK = "pump_set.pressure"


def deck_from_weights[K: str](weights: Mapping[K, float], name: str) -> dict[str, int]:
    """Turn declared weights into card counts; a weight must be a whole number (a card count)."""
    fractional = {key: value for key, value in weights.items() if value != int(value)}
    if fractional:
        raise ValueError(
            f"{name} feeds a variant deck, so every weight must be a whole number; got {fractional}"
        )
    return {key: int(value) for key, value in weights.items()}


def _cards(counts: Mapping[str, int]) -> tuple[str, ...]:
    return tuple(card for card, copies in counts.items() for _ in range(copies))


def pattern_deck_variants(
    knobs: PatternKnobs | None = None, trims: TrimConvention | None = None
) -> dict[str, tuple[str, ...]]:
    """The pattern decks for `VariantDecks`, in a fixed order."""
    knobs = knobs or PatternKnobs()
    trims = trims or TrimConvention()
    group = deck_from_weights(knobs.pump_set_group_weights, "pump_set_group_weights")
    pressure = deck_from_weights(trims.pump_pressure_mode_weights, "pump_pressure_mode_weights")
    counts = {**PATTERN_DECKS, PUMP_SET_GROUP_DECK: group, PUMP_SET_PRESSURE_DECK: pressure}
    return {key: _cards(cards) for key, cards in sorted(counts.items())}


def all_deck_variants(
    knobs: PatternKnobs | None = None, trims: TrimConvention | None = None
) -> dict[str, tuple[str, ...]]:
    """Every deck a pattern deals from: the role decks of the trims and the pattern decks."""
    return {**role_deck_variants(), **pattern_deck_variants(knobs, trims)}


def variant_label(**choices: object) -> str:
    """`tanks=3|metering=none`: the axis choices of one instance, in the order given."""
    return "|".join(f"{axis}={choice}" for axis, choice in choices.items())
