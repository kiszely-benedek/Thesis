"""A one-unit test plant for patterns, written to the graph oracle and the DEXPI builder at once.

Not a test module (no `test_` prefix). `PatternHarness` is a `TrimHarness` whose context also deals
the pattern decks, plus the `PatternContext` the pattern functions take.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

from trim_harness import STYLE, TrimHarness

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.variants import all_deck_variants
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.vocabulary import OnOffLetter, SpareNaming, TrainConventions


class PatternHarness(TrimHarness):
    """Unit 1 with every deck dealt; `config` overrides knobs of the default v2 config."""

    def __init__(
        self,
        seed: int = 0,
        config: GeneratorConfigV2 | None = None,
        spare_naming: SpareNaming = SpareNaming.SUFFIX,
        on_off: OnOffLetter = OnOffLetter.X,
        style: LineStyle = STYLE,
        deck_cards: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        """`deck_cards` replaces whole decks (`{"U4.tank_count": ("3",)}`) to force a variant."""
        config = config or GeneratorConfigV2(n_units=1)
        super().__init__(seed, config.trims, on_off)
        conventions = TrainConventions(on_off_letter=on_off, spare_naming=spare_naming)
        cards = {**all_deck_variants(config.patterns, config.trims), **(deck_cards or {})}
        decks = VariantDecks(seed, cards)
        self.ctx = TrimContext(
            1, random.Random(seed), config.trims, conventions, decks, self.ctx.numbering
        )
        self.pctx = PatternContext(
            self.ctx, config.instruments, config.density, config.patterns, style
        )

    def build(self, instance: PatternInstance) -> PatternInstance:
        """Write the instance's plan to both backends (after naming its unit)."""
        instance.plan.write(self.builder)
        return instance


def config_with(**sections: dict[str, object]) -> GeneratorConfigV2:
    """The default v2 config with some knob groups overridden: `config_with(trims={...})`."""
    base = GeneratorConfigV2(n_units=1)
    updates = {
        name: getattr(base, name).model_copy(update=values) for name, values in sections.items()
    }
    return base.model_copy(update=updates)
