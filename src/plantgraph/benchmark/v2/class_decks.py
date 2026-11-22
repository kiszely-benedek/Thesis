"""Which valve or fitting class fills a role in a trim: one deck per role (pid-vocabulary 13.4).

A **role** is a job a part does ("block valve", "control-valve body"). Several classes can do it,
so each role has a deck of classes: the primary class is dealt twice per deck and every alternative
once (Rule V, pid-vocabulary 13.1). Nothing here is a frequency claim; it only makes sure that the
rarer classes turn up regularly in a corpus.

`VariantDecks` (`deck.py`) deals the decks; its keys are `role:<name>`.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.v21_pins import V21_PURGE_METER_DECK, V21_ROLE_CLASSES
from plantgraph.graph.schema import CONTROL_VALVE_BODY_CLASSES, PIPING_CLASSES

#: role -> {class: how many times it is in the deck}. Table 13.4 of the design note.
#: Read-only: it is the v2.1 pin, so v2.2 grows a copy of it and never edits it in place.
ROLE_CLASSES = V21_ROLE_CLASSES

#: Roles whose class is fixed by a rule, not dealt (table 13.4, "fixed" rows).
COMPRESSOR_SUCTION_BLOCK = "ButterflyValve"
CV_STATION_BYPASS = "GlobeValve"
ON_OFF_VALVE = "BallValve"
PUMP_CHECK = "SwingCheckValve"
MIN_FLOW_CHECK = "GlobeCheckValve"
COMPRESSOR_CHECK = "CheckValve"
PD_RELIEF = "SpringLoadedAngleGlobeSafetyValve"
PLUG_DRAIN = "AnglePlugValve"  # tank bottom drain on rotary-pump farms
TEMPERATURE_TAP_ROOT = "BlindFlange"

#: The purge-connection meter is a deck over "none" and the rotameter (13.4), so it is not a class.
PURGE_METER_DECK = V21_PURGE_METER_DECK
PURGE_METER_ROLE = "purge_meter"


def role_deck_variants() -> dict[str, tuple[str, ...]]:
    """The v2.1 deck contents for `VariantDecks`, keyed `role:<name>`, in a fixed order.

    Reads the `V21_*` pins, not the live names, so growing a live table cannot change v2.1 draws.
    """
    decks = {
        f"role:{role}": tuple(name for name, count in classes.items() for _ in range(count))
        for role, classes in sorted(V21_ROLE_CLASSES.items())
    }
    decks[f"role:{PURGE_METER_ROLE}"] = V21_PURGE_METER_DECK
    return decks


def _check_tables() -> None:
    """Fail at import when a class in the tables is not a schema piping class."""
    named = {name for classes in ROLE_CLASSES.values() for name in classes}
    named |= {COMPRESSOR_SUCTION_BLOCK, CV_STATION_BYPASS, ON_OFF_VALVE, PUMP_CHECK}
    named |= {MIN_FLOW_CHECK, COMPRESSOR_CHECK, PD_RELIEF, PLUG_DRAIN, TEMPERATURE_TAP_ROOT}
    unknown = sorted(named - PIPING_CLASSES)
    if unknown:
        raise ImportError(f"class_decks names classes that are not piping classes: {unknown}")
    for role in ("control_valve_body", "letdown_control_valve_body"):
        stray = sorted(set(ROLE_CLASSES[role]) - CONTROL_VALVE_BODY_CLASSES)
        if stray:
            raise ImportError(f"{role} must hold control-valve bodies, got {stray}")


_check_tables()
