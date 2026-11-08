"""The tau grid holds the exact observed scores, so `score >= tau` is tried for each of them."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from plantgraph.exp0004.corpus import Corpus
from plantgraph.exp0004.tuning import observed_thresholds
from plantgraph.resolution.identity_deciders import StringSimilarityDecider, string_similarity


def _corpus_with_tags(*tag_pairs: tuple[str, str]) -> Corpus:
    """A stand-in carrying only what `observed_thresholds` reads: candidate pairs with tags."""
    pairs = [
        SimpleNamespace(first=SimpleNamespace(tag=one), second=SimpleNamespace(tag=other))
        for one, other in tag_pairs
    ]
    return cast(Corpus, SimpleNamespace(candidates=SimpleNamespace(pairs=pairs)))


def test_the_grid_holds_exact_scores_not_twelve_decimal_roundings() -> None:
    exact = string_similarity("P-1203", "P-1203A")  # 12/13, which has no short decimal form
    grid = observed_thresholds(_corpus_with_tags(("P-1203", "P-1203A"), ("AB1", "AB2")))
    assert exact in grid


def test_each_grid_value_accepts_the_pair_that_produced_it() -> None:
    tag_pairs = [("P-101A", "P101"), ("TK-1201", "TK 120"), ("XY", "XZ")]
    pair_of: dict[float, Any] = {}
    for one, other in tag_pairs:
        pair_of[string_similarity(one, other)] = SimpleNamespace(
            first=SimpleNamespace(tag=one, node_class="C"),
            second=SimpleNamespace(tag=other, node_class="C"),
        )
    for tau in observed_thresholds(_corpus_with_tags(*tag_pairs)):
        assert StringSimilarityDecider(tau).decide(pair_of[tau]).accept
