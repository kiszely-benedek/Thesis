"""What a pattern needs from its caller: the trim context plus the pattern-level knobs.

`TrimContext` (one per process unit) carries the random stream, numbering and class decks the trims
use. A pattern also reads three more groups of declared knobs, which are not part of
`TrimConvention`: how loops are shaped (`InstrumentConvention`), how many instruments there are
(`InstrumentDensity`) and the pattern shapes (`PatternKnobs`).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from plantgraph.benchmark.v2.config import (
    GeneratorConfigV2,
    InstrumentConvention,
    InstrumentDensity,
    PatternKnobs,
)
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext, UnitNumbering
from plantgraph.benchmark.v2.vocabulary import TrainConventions


@dataclass(frozen=True)
class PatternContext:
    """Everything one unit's pattern shares; `style` is the line style of its main process lines."""

    trim: TrimContext
    instruments: InstrumentConvention
    density: InstrumentDensity
    knobs: PatternKnobs
    style: LineStyle

    @classmethod
    def from_config(
        cls,
        config: GeneratorConfigV2,
        unit_no: int,
        rng: random.Random,
        conventions: TrainConventions,
        decks: VariantDecks,
        style: LineStyle,
        numbering: UnitNumbering | None = None,
    ) -> PatternContext:
        """The context of unit `unit_no`, its knobs read from `config`."""
        trim = TrimContext(unit_no, rng, config.trims, conventions, decks, numbering)
        return cls(trim, config.instruments, config.density, config.patterns, style)

    @property
    def unit_no(self) -> int:
        """The process unit's number."""
        return self.trim.unit_no

    def chance(self, probability: float) -> bool:
        """True with the given probability, drawn from the unit's stream."""
        return self.trim.chance(probability)

    def deal(self, deck_key: str) -> str:
        """The next card of the variant deck `deck_key` (see `variants.py`)."""
        return self.trim.decks.deal(deck_key)
