"""Precision, recall and F1 from counts: the one place these formulas live."""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel, ConfigDict


class Counts(NamedTuple):
    """True positives, false positives and false negatives of one set of pairs."""

    tp: int
    fp: int
    fn: int

    def plus(self, other: Counts, times: int = 1) -> Counts:
        """This plus `times` copies of `other`."""
        return Counts(
            self.tp + times * other.tp, self.fp + times * other.fp, self.fn + times * other.fn
        )


class Prf(BaseModel):
    """Counts with precision, recall and F1; None where a denominator is zero."""

    model_config = ConfigDict(frozen=True)

    tp: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None
    f1: float | None


def prf_of(counts: Counts) -> Prf:
    """Precision, recall and F1 of `counts`; F1 is None when either is zero or missing."""
    predicted, actual = counts.tp + counts.fp, counts.tp + counts.fn
    precision = counts.tp / predicted if predicted else None
    recall = counts.tp / actual if actual else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return Prf(tp=counts.tp, fp=counts.fp, fn=counts.fn, precision=precision, recall=recall, f1=f1)


def f1_of_counts(counts: Counts) -> float | None:
    """F1 as 2tp / (2tp + fp + fn); None when there is nothing to score. Used by the bootstrap."""
    total = 2 * counts.tp + counts.fp + counts.fn
    return 2 * counts.tp / total if total else None
