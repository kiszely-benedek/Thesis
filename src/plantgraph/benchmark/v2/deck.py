"""Variant decks: every variant of a pattern turns up regularly (pid-vocabulary.md 5.2).

Drawing a variant at random would leave rare ones unused in a small corpus. A **deck** instead
shuffles all variants, deals them in order, and reshuffles when it runs out, so each variant
appears once in every `len(variants)` instances of the pattern. The decks are keyed by pattern
id and each has its own random stream, so the variant of unit *u* depends only on how many
instances of its pattern came before it (prefix stability).
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

from plantgraph.benchmark.v2.streams import deck_rng


class VariantDeck:
    """A shuffled deck of variant names that refills itself."""

    def __init__(self, variants: Sequence[str], rng: random.Random) -> None:
        if not variants:
            raise ValueError("a variant deck needs at least one variant; got an empty list")
        self._variants = tuple(variants)
        self._rng = rng
        self._pile: list[str] = []

    def deal(self) -> str:
        """The next variant; reshuffles first when the deck is empty."""
        if not self._pile:
            self._pile = list(self._variants)
            self._rng.shuffle(self._pile)
        return self._pile.pop()


class VariantDecks:
    """One `VariantDeck` per pattern id, each seeded from the plant seed and its own id."""

    def __init__(self, seed: int, variants_by_pattern: Mapping[str, Sequence[str]]) -> None:
        self._decks = {
            pattern_id: VariantDeck(variants, deck_rng(seed, pattern_id))
            for pattern_id, variants in sorted(variants_by_pattern.items())
        }

    def deal(self, pattern_id: str) -> str:
        """The next variant of `pattern_id`."""
        if pattern_id not in self._decks:
            raise ValueError(
                f"no variant deck for pattern {pattern_id!r}; known: {sorted(self._decks)}"
            )
        return self._decks[pattern_id].deal()
