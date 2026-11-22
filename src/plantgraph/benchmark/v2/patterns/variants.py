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
from plantgraph.benchmark.v2.v21_pins import V21_PATTERN_DECKS

#: deck key -> {card: copies}; the cards of one axis, table 13.3 of the design. Read-only: it is the
#: v2.1 pin, so v2.2 grows a copy of it and never edits it in place.
PATTERN_DECKS = V21_PATTERN_DECKS

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
    """The v2.1 pattern decks for `VariantDecks`, in a fixed order (read from the `V21_*` pin)."""
    knobs = knobs or PatternKnobs()
    trims = trims or TrimConvention()
    group = deck_from_weights(knobs.pump_set_group_weights, "pump_set_group_weights")
    pressure = deck_from_weights(trims.pump_pressure_mode_weights, "pump_pressure_mode_weights")
    counts = {**V21_PATTERN_DECKS, PUMP_SET_GROUP_DECK: group, PUMP_SET_PRESSURE_DECK: pressure}
    return {key: _cards(cards) for key, cards in sorted(counts.items())}


def all_deck_variants(
    knobs: PatternKnobs | None = None, trims: TrimConvention | None = None
) -> dict[str, tuple[str, ...]]:
    """Every deck a pattern deals from: the role decks of the trims and the pattern decks."""
    return {**role_deck_variants(), **pattern_deck_variants(knobs, trims)}


def variant_label(**choices: object) -> str:
    """`tanks=3|metering=none`: the axis choices of one instance, in the order given."""
    return "|".join(f"{axis}={choice}" for axis, choice in choices.items())
