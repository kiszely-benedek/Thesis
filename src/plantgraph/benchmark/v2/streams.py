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


def train_rng(seed: int, train_no: int) -> random.Random:
    """One train's conventions (on-off letter, spare naming)."""
    return random.Random(f"{seed}:train:{train_no}")


def deck_rng(seed: int, pattern_id: str) -> random.Random:
    """The shuffle stream of one pattern's variant deck."""
    return random.Random(f"{seed}:deck:{pattern_id}")
