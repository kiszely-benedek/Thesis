"""Tests for the variant deck, the named random streams and the per-train conventions."""

from __future__ import annotations

import random

import pytest

from plantgraph.benchmark.v2.deck import VariantDeck, VariantDecks
from plantgraph.benchmark.v2.plan_models import draw_train_records
from plantgraph.benchmark.v2.streams import deck_rng, master_rng, train_rng, unit_rng
from plantgraph.benchmark.v2.vocabulary import OnOffLetter, SpareNaming, draw_train_conventions

VARIANTS = ("plain", "vacuum", "cascade", "condensate")


def _deal(decks: VariantDecks, pattern_id: str, count: int) -> list[str]:
    return [decks.deal(pattern_id) for _ in range(count)]


@pytest.mark.parametrize("seed", [0, 1, 99])
def test_every_variant_appears_once_per_cycle(seed: int) -> None:
    decks = VariantDecks(seed, {"U1": VARIANTS})
    dealt = _deal(decks, "U1", len(VARIANTS) * 5)
    for start in range(0, len(dealt), len(VARIANTS)):
        assert sorted(dealt[start : start + len(VARIANTS)]) == sorted(VARIANTS)


def test_same_seed_deals_the_same_sequence() -> None:
    first = _deal(VariantDecks(3, {"U1": VARIANTS}), "U1", 12)
    second = _deal(VariantDecks(3, {"U1": VARIANTS}), "U1", 12)
    assert first == second


def test_different_seeds_deal_different_orders() -> None:
    orders = {tuple(_deal(VariantDecks(seed, {"U1": VARIANTS}), "U1", 4)) for seed in range(10)}
    assert len(orders) > 1


def test_decks_are_independent_per_pattern() -> None:
    # dealing U2 in between must not change what U1 deals: prefix stability of the units
    alone = _deal(VariantDecks(5, {"U1": VARIANTS, "U2": VARIANTS}), "U1", 8)
    decks = VariantDecks(5, {"U1": VARIANTS, "U2": VARIANTS})
    mixed = []
    for _ in range(8):
        decks.deal("U2")
        mixed.append(decks.deal("U1"))
    assert mixed == alone


def test_a_longer_deal_extends_the_shorter_one() -> None:
    short = _deal(VariantDecks(2, {"U1": VARIANTS}), "U1", 6)
    long = _deal(VariantDecks(2, {"U1": VARIANTS}), "U1", 11)
    assert long[:6] == short


def test_a_single_variant_deck_repeats_it() -> None:
    assert _deal(VariantDecks(0, {"U7": ("only",)}), "U7", 3) == ["only"] * 3


def test_unknown_pattern_and_empty_deck_raise() -> None:
    with pytest.raises(ValueError, match="no variant deck for pattern 'U9'"):
        VariantDecks(0, {"U1": VARIANTS}).deal("U9")
    with pytest.raises(ValueError, match="at least one variant"):
        VariantDeck((), random.Random(0))


def test_streams_are_named_and_reproducible() -> None:
    assert master_rng(4).random() == master_rng(4).random()
    assert unit_rng(4, 1).random() != unit_rng(4, 2).random()
    assert train_rng(4, 1).random() != unit_rng(4, 1).random()
    assert deck_rng(4, "U1").random() == deck_rng(4, "U1").random()


def test_train_records_follow_the_t2_draw_from_the_train_stream() -> None:
    records = draw_train_records(seed=11, n_trains=3)
    assert [record.train_no for record in records] == [1, 2, 3]
    for record in records:
        assert record.conventions == draw_train_conventions(train_rng(11, record.train_no))


def test_a_train_keeps_its_conventions_when_more_trains_are_added() -> None:
    assert draw_train_records(11, 4)[:2] == draw_train_records(11, 2)


def test_every_convention_value_is_reached_across_seeds() -> None:
    drawn = [record.conventions for seed in range(40) for record in draw_train_records(seed, 2)]
    assert {c.on_off_letter for c in drawn} == set(OnOffLetter)
    assert {c.spare_naming for c in drawn} == set(SpareNaming)
