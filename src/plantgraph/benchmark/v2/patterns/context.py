"""What a pattern needs from its caller: the trim context plus the pattern-level knobs.

`TrimContext` (one per process unit) carries the random stream, numbering and class decks the trims
use. A pattern also reads three more groups of declared knobs, which are not part of
`TrimConvention`: how loops are shaped (`InstrumentConvention`), how many instruments there are
(`InstrumentDensity`) and the pattern shapes (`PatternKnobs`). The flowsheet knobs ride along for
the one a pattern reads (`p_side_draw`). The sheet knobs ride along for the patterns that choose a
drawing layout by the sheet cap, and `waiting_streams` tells a tank farm how many product streams
of its train still wait for a tank.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from plantgraph.benchmark.v2.config import (
    FlowsheetKnobs,
    GeneratorConfigV2,
    InstrumentConvention,
    InstrumentDensity,
    PatternKnobs,
    SheetKnobs,
)
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.streams import handbook_train_rng, handbook_unit_rng
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
    flowsheet: FlowsheetKnobs = field(default_factory=FlowsheetKnobs)  # `p_side_draw` is read here
    sheets: SheetKnobs = field(default_factory=SheetKnobs)  # the equipment cap per sheet
    waiting_streams: int = 0  # open liquid out-ports of the unit's train (a product farm only)

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
        waiting_streams: int = 0,
        train_no: int | None = None,
    ) -> PatternContext:
        """The context of unit `unit_no` (of train `train_no`), its knobs read from `config`."""
        handbook = isinstance(config, GeneratorConfigV22) and config.handbook.enabled
        knobs = config.handbook if isinstance(config, GeneratorConfigV22) else None
        trim = TrimContext(
            unit_no,
            rng,
            config.trims,
            conventions,
            decks,
            numbering,
            handbook,
            knobs,
            handbook_unit_rng(config.seed, unit_no),
            config.seed,
            handbook and _train_has_no_pv_bypass(config, train_no),
        )
        return cls(
            trim,
            config.instruments,
            config.density,
            config.patterns,
            style,
            config.flowsheet,
            config.sheets,
            waiting_streams,
        )

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


def _train_has_no_pv_bypass(config: GeneratorConfigV2, train_no: int | None) -> bool:
    """The train's company style: pressure-control stations without a bypass (TOG122).

    One draw per train from its own stream, so every unit of the train agrees and no other
    draw moves. A unit built without a train number (a test harness) keeps the bypass.
    """
    if train_no is None or not isinstance(config, GeneratorConfigV22):
        return False
    rng = handbook_train_rng(config.seed, train_no, "pv_no_bypass")
    return rng.random() < config.handbook.p_pv_no_bypass_train
