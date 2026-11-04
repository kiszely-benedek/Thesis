"""Pair deciders: given a candidate pair, say how likely it is one physical item (D0 to D2).

Design: `exp0004-v2.md` section 5.4. A **decider** reads a `CandidatePair` (two occurrences of
equipment on different sheets whose tags may be written differently, e.g. `P-1203A` and `12-P-03A`)
and returns a score plus an accept flag. The thresholds are parameters: they are tuned on a
development corpus outside this module (section 5.5), never chosen here.

- D0 `ExactTagDecider`: today's resolver, equal tag and class only.
- D1 `StringSimilarityDecider`: similarity of the tags after a fixed normaliser.
- D2 `UnitAwareDecider`: D1 plus the context rule "the two occurrences sit in the same unit".

The model-based decider (D4) is deliberately not here: `resolution/` never imports `plantgraph.llm`.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from plantgraph.resolution.identity_candidates import CandidatePair

_KEPT_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


class PairDecision(BaseModel):
    """A decider's verdict on one pair. `score` orders accepted links (higher = more sure)."""

    model_config = ConfigDict(frozen=True)

    score: float
    accept: bool


class PairDecider(Protocol):
    """Anything that can judge a candidate pair; D0, D1, D2 and later the model-based D4."""

    name: str

    def decide(self, pair: CandidatePair) -> PairDecision:
        """Judge one candidate pair."""
        ...


def normalise_tag(tag: str) -> str:
    """Upper-case and keep only letters and digits, so `12-p-03a` becomes `12P03A`.

    Fixed before any tag variant existed: no zero handling and no synonym table, because either
    would encode one of the variant operators (section 5.4).
    """
    return "".join(ch for ch in tag.upper() if ch in _KEPT_CHARACTERS)


def string_similarity(first_tag: str, second_tag: str) -> float:
    """Ratio in [0, 1] of the normalised tags; 0.0 when either has nothing left to compare."""
    one, other = normalise_tag(first_tag), normalise_tag(second_tag)
    if not one or not other:
        return 0.0
    return SequenceMatcher(None, one, other, autojunk=False).ratio()


class ExactTagDecider:
    """D0: accepts only an equal tag and class, as the resolver does today (score 1.0 or 0.0)."""

    name = "d0"

    def decide(self, pair: CandidatePair) -> PairDecision:
        """Score 1.0 and accept when tag and class are equal."""
        same = (pair.first.tag, pair.first.node_class) == (pair.second.tag, pair.second.node_class)
        return PairDecision(score=1.0 if same else 0.0, accept=same)


class StringSimilarityDecider:
    """D1: accepts when the normalised tags are at least `threshold` similar (score = ratio)."""

    name = "d1"

    def __init__(self, threshold: float) -> None:
        _check_threshold(threshold)
        self.threshold = threshold

    def decide(self, pair: CandidatePair) -> PairDecision:
        """Score the normalised tag similarity."""
        score = string_similarity(pair.first.tag, pair.second.tag)
        return PairDecision(score=score, accept=score >= self.threshold)


class UnitAwareDecider:
    """D2: D1's rule, and A's unit must be among the units printed on B's sheet (design 5.4).

    A's unit is its own printed unit; a reference prints none, so then every unit on A's sheet
    counts ("its sheet's unit", read as a set because a sheet can carry several units).
    Unknown units (an empty set) reject: the rule cannot confirm the pair, and a spare in
    another unit would otherwise pass on text alone. A and B follow the card's richer-first order.
    """

    name = "d2"

    def __init__(self, threshold: float) -> None:
        _check_threshold(threshold)
        self.threshold = threshold

    def decide(self, pair: CandidatePair) -> PairDecision:
        """Score the tag similarity, or 0.0 when the units do not agree."""
        if not units_agree(pair):
            return PairDecision(score=0.0, accept=False)
        score = string_similarity(pair.first.tag, pair.second.tag)
        return PairDecision(score=score, accept=score >= self.threshold)


def units_agree(pair: CandidatePair) -> bool:
    """True when A's unit (else its sheet's units) is among the units printed on B's sheet."""
    a_units = {pair.first_unit} if pair.first_unit is not None else set(pair.first_sheet_units)
    return bool(a_units & set(pair.second_sheet_units))


def _check_threshold(threshold: float) -> None:
    if not 0.0 < threshold <= 1.0:
        raise ValueError(f"expected a decider threshold in (0, 1], got {threshold}")
