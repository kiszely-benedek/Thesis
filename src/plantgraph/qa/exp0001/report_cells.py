"""From per-question scores to the report's cells: scopes, per-arm summaries, paired differences."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from plantgraph.qa.cascade.stats import (
    interval_of,
    median,
    paired_bootstrap,
    percentile,
    wilson_interval,
)
from plantgraph.qa.exp0001.report_models import (
    SCOPE_ALL,
    SCOPE_COMMON,
    ArmCell,
    PairedDelta,
    QuestionScore,
)
from plantgraph.qa.models import Outcome, QuestionFamily

N_BOOT = 10_000
SEED = 20261101
#: ADR-0044 U2: this family is left out of every EXP-0001 number.
EXCLUDED_FAMILY = QuestionFamily.LOOP_ACTUATED_VALVE.value


@dataclass(frozen=True)
class Scope:
    """Which questions a table counts: a name and the families allowed (`None` = all of them)."""

    name: str
    families: frozenset[str] | None = None

    def keep(self, scores: Sequence[QuestionScore]) -> list[QuestionScore]:
        """The scores of this scope's families, never the excluded family."""
        allowed = self.families
        return [
            s
            for s in scores
            if s.family != EXCLUDED_FAMILY and (allowed is None or s.family in allowed)
        ]


def make_scopes(ladder_families: Collection[frozenset[str]]) -> list[Scope]:
    """`common`: families with questions at every ladder size; `all`: every family at that size.

    Raises:
        ValueError: no ladder size was given.
    """
    if not ladder_families:
        raise ValueError("expected the families of at least one ladder size, found none")
    shared = frozenset.intersection(*ladder_families) - {EXCLUDED_FAMILY}
    return [Scope(SCOPE_COMMON, shared), Scope(SCOPE_ALL)]


def build_cell(
    corpus_id: str, arm: str, scope: Scope, scores: Sequence[QuestionScore]
) -> ArmCell | None:
    """One arm's summary on one scope; `None` when the scope holds no question here."""
    kept = scope.keep(scores)
    if not kept:
        return None
    in_time = sum(s.correct_at_cutoff for s in kept)
    costs = [s.cost_usd for s in kept]
    latencies = [s.latency_s for s in kept]
    counts = Counter(s.outcome for s in kept)
    return ArmCell(
        corpus_id=corpus_id,
        policy=arm,
        scope=scope.name,
        n=len(kept),
        correct_at_120=in_time,
        acc_at_120=wilson_interval(in_time, len(kept)),
        acc_uncut=sum(s.correct for s in kept) / len(kept),
        cost_mean=sum(costs) / len(costs),
        cost_median=median(costs),
        latency_median=median(latencies),
        latency_p90=percentile(latencies, 90),
        outcomes={outcome.value: counts.get(outcome, 0) for outcome in Outcome},
    )


def paired_vectors(
    a: Sequence[QuestionScore], b: Sequence[QuestionScore], scope: Scope
) -> tuple[list[QuestionScore], list[QuestionScore]]:
    """The two arms' scores on the same in-scope questions, in the same order.

    Raises:
        ValueError: the arms were scored on different questions.
    """
    kept_a, kept_b = scope.keep(a), scope.keep(b)
    if [s.qid for s in kept_a] != [s.qid for s in kept_b]:
        raise ValueError(
            "expected both arms on the same questions in the same order, found a mismatch"
        )
    return kept_a, kept_b


def accuracy_differences(a: Sequence[QuestionScore], b: Sequence[QuestionScore]) -> list[float]:
    """Per-question acc@120 of `a` minus `b` (each -1, 0 or +1)."""
    return [
        float(x.correct_at_cutoff) - float(y.correct_at_cutoff) for x, y in zip(a, b, strict=True)
    ]


def build_delta(
    corpus_id: str,
    scope: Scope,
    names: tuple[str, str],
    scores: tuple[Sequence[QuestionScore], Sequence[QuestionScore]],
    metric: Literal["acc@120", "cost_usd"] = "acc@120",
) -> PairedDelta | None:
    """`names[0]` minus `names[1]` with a paired bootstrap; `None` when the scope is empty."""
    kept_a, kept_b = paired_vectors(scores[0], scores[1], scope)
    if not kept_a:
        return None
    if metric == "acc@120":
        x = [float(s.correct_at_cutoff) for s in kept_a]
        y = [float(s.correct_at_cutoff) for s in kept_b]
    else:
        x, y = [s.cost_usd for s in kept_a], [s.cost_usd for s in kept_b]
    difference = paired_bootstrap(x, y, n_resamples=N_BOOT, seed=SEED)
    return PairedDelta(
        corpus_id=corpus_id,
        scope=scope.name,
        a=names[0],
        b=names[1],
        n=len(kept_a),
        delta=difference.mean,
        ci=interval_of(difference),
        metric=metric,
    )


def cells_of_corpus(
    corpus_id: str, scores: Mapping[str, Sequence[QuestionScore]], scopes: Sequence[Scope]
) -> list[ArmCell]:
    """Every (arm, scope) cell of one corpus that has questions."""
    cells = [
        build_cell(corpus_id, arm, scope, arm_scores)
        for arm, arm_scores in scores.items()
        for scope in scopes
    ]
    return [cell for cell in cells if cell is not None]
