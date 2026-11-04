"""Score the deciders of one corpus: pair-level and group-level, per family and operator, with CIs.

Pure functions over `PairRecord`s and `DeciderRun`s; no corpus rebuild and no I/O, so they run on a
scripted toy in a unit test. The subsets are `all` and one per variant family present; a pair with
family `none` (no rewritten occurrence) is only in `all`. A metric is named "decider|subset".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.eval.resolution_scoring import PairScore
from plantgraph.exp0004.bootstrap import (
    N_RESAMPLES,
    SEED,
    BlockCounts,
    Interval,
    interval_of,
    paired_difference,
    resample_f1,
)
from plantgraph.exp0004.deciders import DeciderRun, count_outcomes
from plantgraph.exp0004.metrics import Counts, Prf, prf_of
from plantgraph.exp0004.pairs import NONE, PairRecord

ALL = "all"
Resampled = dict[str, list[float | None]]  # metric to its F1 on every bootstrap resample


class SubsetScore(BaseModel):
    """Pair-level scores of one decider on one subset, with the F1 interval."""

    model_config = ConfigDict(frozen=True)

    prf: Prf
    f1_ci: Interval


class Recovery(BaseModel):
    """Descriptive: of the gold pairs an operator produced, how many the groups recovered."""

    model_config = ConfigDict(frozen=True)

    gold: int
    recovered: int


class DeciderScore(BaseModel):
    """Everything reported for one decider."""

    model_config = ConfigDict(frozen=True)

    decider: str
    threshold: float | None
    subsets: dict[str, SubsetScore]
    group_level: PairScore
    n_dropped_one_to_one: int
    n_identity_conflicts: int
    per_operator: dict[str, Recovery]


class Contrast(BaseModel):
    """F1(plus) minus F1(minus), paired on the same resampled blocks."""

    model_config = ConfigDict(frozen=True)

    plus: str
    minus: str
    estimate: float | None
    ci: Interval


class ScoreFile(BaseModel):
    """What `score` writes as `score.json`."""

    corpus_id: str
    n_pairs: int
    n_blocks: int
    n_resamples: int
    bootstrap_seed: int
    deciders: list[DeciderScore]
    contrasts: list[Contrast]


def score_corpus(
    corpus_id: str,
    pairs: Sequence[PairRecord],
    runs: Sequence[DeciderRun],
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
) -> ScoreFile:
    """Score every run against the pair labels; the bootstrap resamples blocks of pairs."""
    _check_alignment(pairs, runs)
    subsets = subsets_of(pairs)
    metrics = [_metric(run.decider, subset) for run in runs for subset in subsets]
    blocks = block_counts(pairs, runs, subsets)
    resampled = resample_f1(blocks, metrics, n_resamples, seed)
    scores = [_decider_score(run, pairs, subsets, resampled) for run in runs]
    return ScoreFile(
        corpus_id=corpus_id,
        n_pairs=len(pairs),
        n_blocks=len(blocks),
        n_resamples=n_resamples,
        bootstrap_seed=seed,
        deciders=scores,
        contrasts=_contrasts(scores, subsets, resampled),
    )


def subsets_of(pairs: Sequence[PairRecord]) -> list[str]:
    """`all` first, then each family present among the pairs, sorted."""
    return [ALL, *sorted({pair.family for pair in pairs} - {NONE})]


def block_counts(
    pairs: Sequence[PairRecord], runs: Sequence[DeciderRun], subsets: Sequence[str]
) -> list[BlockCounts]:
    """Counts per block for every metric; blocks in sorted-name order."""
    members: dict[str, list[PairRecord]] = defaultdict(list)
    for pair in pairs:
        members[pair.block].append(pair)
    return [
        {
            _metric(run.decider, subset): _counts(members[block], run, subset)
            for run in runs
            for subset in subsets
        }
        for block in sorted(members)
    ]


def _metric(decider: str, subset: str) -> str:
    return f"{decider}|{subset}"


def _counts(pairs: Sequence[PairRecord], run: DeciderRun, subset: str) -> Counts:
    """Outcome counts of `run` on the pairs belonging to `subset`."""
    chosen = [pair for pair in pairs if subset == ALL or pair.family == subset]
    return count_outcomes(
        [run.said_same[pair.index] for pair in chosen], [pair.is_true for pair in chosen]
    )


def _check_alignment(pairs: Sequence[PairRecord], runs: Sequence[DeciderRun]) -> None:
    if not pairs:
        raise ValueError("expected at least one candidate pair to score, got none")
    if [pair.index for pair in pairs] != list(range(len(pairs))):
        raise ValueError("expected pair indices 0..n-1 in order, got a different numbering")
    for run in runs:
        if len(run.said_same) != len(pairs):
            raise ValueError(
                f"expected decider {run.decider} to answer {len(pairs)} pairs, "
                f"got {len(run.said_same)}: the decision file is from another corpus"
            )


def _decider_score(
    run: DeciderRun, pairs: Sequence[PairRecord], subsets: Sequence[str], resampled: Resampled
) -> DeciderScore:
    subset_scores = {
        subset: SubsetScore(
            prf=prf_of(_counts(pairs, run, subset)),
            f1_ci=interval_of(resampled[_metric(run.decider, subset)]),
        )
        for subset in subsets
    }
    return DeciderScore(
        decider=run.decider,
        threshold=run.threshold,
        subsets=subset_scores,
        group_level=run.group_level,
        n_dropped_one_to_one=run.n_dropped_one_to_one,
        n_identity_conflicts=run.n_identity_conflicts,
        per_operator=_per_operator(run, pairs),
    )


def _per_operator(run: DeciderRun, pairs: Sequence[PairRecord]) -> dict[str, Recovery]:
    gold: dict[str, int] = defaultdict(int)
    recovered: dict[str, int] = defaultdict(int)
    for pair in pairs:
        if pair.is_true:
            gold[pair.operator] += 1
            recovered[pair.operator] += int(run.said_same[pair.index])
    return {
        operator: Recovery(gold=gold[operator], recovered=recovered[operator])
        for operator in sorted(gold)
    }


def _contrasts(
    scores: Sequence[DeciderScore], subsets: Sequence[str], resampled: Resampled
) -> list[Contrast]:
    """Later minus earlier decider per subset; per decider, a family minus the next."""
    wanted: list[tuple[str, str]] = []
    for position, later in enumerate(scores):
        for earlier in scores[:position]:
            wanted += [(_metric(later.decider, s), _metric(earlier.decider, s)) for s in subsets]
    families = [subset for subset in subsets if subset != ALL]
    for score in scores:
        wanted += [
            (_metric(score.decider, one), _metric(score.decider, other))
            for one, other in zip(families, families[1:], strict=False)
        ]
    by_metric = {
        _metric(score.decider, subset): sub.prf
        for score in scores
        for subset, sub in score.subsets.items()
    }
    return [_contrast(plus, minus, by_metric, resampled) for plus, minus in wanted]


def _contrast(plus: str, minus: str, by_metric: dict[str, Prf], resampled: Resampled) -> Contrast:
    plus_f1, minus_f1 = by_metric[plus].f1, by_metric[minus].f1
    estimate = None if plus_f1 is None or minus_f1 is None else plus_f1 - minus_f1
    differences = paired_difference(resampled[plus], resampled[minus])
    return Contrast(plus=plus, minus=minus, estimate=estimate, ci=interval_of(differences))
