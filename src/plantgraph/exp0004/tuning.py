"""Choose the thresholds of D1 and D2 (design 5.5): dev corpus only, ties to the higher tau."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.exp0004.corpus import DEV_SEED, Corpus
from plantgraph.exp0004.deciders import run_decider
from plantgraph.resolution.identity_deciders import (
    PairDecider,
    StringSimilarityDecider,
    UnitAwareDecider,
    string_similarity,
)

DeciderFactory = Callable[[float], PairDecider]


class Taus(BaseModel):
    """The two tuned thresholds (what `taus.json` holds)."""

    model_config = ConfigDict(frozen=True)

    tau1: float
    tau2: float


class TuningRow(BaseModel):
    """One candidate threshold and the pair-level F1 it reached."""

    tau: float
    f1: float | None


def observed_thresholds(corpus: Corpus) -> list[float]:
    """Every distinct D1 score on the candidates, rounded to 12 places, zero excluded."""
    scores = {
        round(string_similarity(pair.first.tag, pair.second.tag), 12)
        for pair in corpus.candidates.pairs
        if pair.first.tag
    }
    return sorted(score for score in scores if score > 0)


def pick_best(rows: Sequence[TuningRow]) -> float:
    """The threshold with the best F1 (a missing F1 counts as 0); a tie goes to the higher tau."""
    if not rows:
        raise ValueError("expected at least one threshold to choose from, got none")
    return max(rows, key=lambda row: (row.f1 or 0.0, row.tau)).tau


def tune_decider(corpus: Corpus, make: DeciderFactory) -> tuple[float, list[TuningRow]]:
    """Try every observed score as the threshold of `make`; return the best and the full trace."""
    refuse_non_dev_corpus(corpus)
    rows = [_try(corpus, make, tau) for tau in observed_thresholds(corpus)]
    return pick_best(rows), rows


def tune(corpus: Corpus) -> tuple[Taus, dict[str, list[TuningRow]]]:
    """Tune D1 and D2 on the dev corpus."""
    tau1, trace1 = tune_decider(corpus, StringSimilarityDecider)
    tau2, trace2 = tune_decider(corpus, UnitAwareDecider)
    return Taus(tau1=tau1, tau2=tau2), {"d1": trace1, "d2": trace2}


def refuse_non_dev_corpus(corpus: Corpus) -> None:
    """No decider is tuned on a test corpus (design 5.5)."""
    if corpus.spec.seed != DEV_SEED:
        raise ValueError(
            f"expected the dev corpus (seed {DEV_SEED}) to tune on, got seed {corpus.spec.seed}: "
            "thresholds are never tuned on a test corpus"
        )


def _try(corpus: Corpus, make: DeciderFactory, tau: float) -> TuningRow:
    run = run_decider(corpus, make(tau))
    return TuningRow(tau=tau, f1=run.pair_level.f1)
