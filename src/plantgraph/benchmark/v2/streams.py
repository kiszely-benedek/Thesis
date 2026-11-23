"""The named random streams of the v2 generator (generator-v2-realism.md 8.2).

Each decision family draws from its own `random.Random`, seeded by a string. A string seed is
hashed with SHA-512 by Python, so the stream does not depend on `PYTHONHASHSEED`. Separate streams
are what make a plant's first *n* units identical to the *n*-unit plant (prefix stability): unit
*u* never consumes a number another unit would have used.
"""

from __future__ import annotations

import random


def master_rng(seed: int) -> random.Random:
    """The flowsheet stream: train count, train shape, pattern choice per slot."""
    return random.Random(f"{seed}:flowsheet")


def unit_rng(seed: int, unit_no: int) -> random.Random:
    """One unit's internals (sizes, optional trims and instruments); no other unit reads it."""
    return random.Random(f"{seed}:unit:{unit_no}")


def handbook_unit_rng(seed: int, unit_no: int) -> random.Random:
    """The v2.2 handbook draws of one unit (hidden pump power band); v2.1 never touches it."""
    return random.Random(f"{seed}:unit{unit_no}:handbook")


def handbook_rule_rng(seed: int, unit_no: int, rule: str) -> random.Random:
    """One alternative's own stream inside a unit, so adding a rule never shifts another's draws."""
    return random.Random(f"{seed}:unit{unit_no}:handbook:{rule}")


def handbook_train_rng(seed: int, train_no: int, rule: str) -> random.Random:
    """One alternative's stream for a whole train (a company-style choice, same for every unit)."""
    return random.Random(f"{seed}:train{train_no}:handbook:{rule}")


def handbook_document_rng(seed: int, document_no: int, rule: str) -> random.Random:
    """One company convention's stream for a whole document (design 5), from the document alone.

    The name has no train or unit in it, so a document's draws never depend on how many trains
    the plant has, and no v2.1 stream is read.
    """
    return random.Random(f"{seed}:document{document_no}:handbook:{rule}")


def train_rng(seed: int, train_no: int) -> random.Random:
    """One train's conventions (on-off letter, spare naming)."""
    return random.Random(f"{seed}:train:{train_no}")


def deck_rng(seed: int, pattern_id: str) -> random.Random:
    """The shuffle stream of one pattern's variant deck."""
    return random.Random(f"{seed}:deck:{pattern_id}")
