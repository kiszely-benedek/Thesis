"""Build the EXP-0001 report from the scored corpora (design sections 7 and 8).

`build_ladder_report` is pure: it takes `CorpusScores` (from `report_load`) and returns a
`LadderReport`, so it is tested on synthetic scores without any run directory.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.qa.exp0001.ladder_stats import SizeSample, log10_sheets, slope_interval
from plantgraph.qa.exp0001.report_cells import (
    N_BOOT,
    SEED,
    Scope,
    accuracy_differences,
    build_delta,
    cells_of_corpus,
    make_scopes,
    paired_vectors,
)
from plantgraph.qa.exp0001.report_claims import (
    ClaimInputs,
    WallSettings,
    all_claims,
    wall_figures,
)
from plantgraph.qa.exp0001.report_load import CorpusScores
from plantgraph.qa.exp0001.report_models import (
    CASCADE,
    CTX_HIGH,
    CTX_LOW,
    SCOPE_ALL,
    SCOPE_COMMON,
    LadderReport,
    PairedDelta,
    Trend,
)

#: The ladder the slope is fitted on; H100 (stage C) is shown beside it, never in the slope.
LADDER_IDS = ("H1", "H3", "H10", "H30")


def build_ladder_report(
    corpora: Sequence[CorpusScores],
    cutoff_s: float,
    ladder_ids: Sequence[str] = LADDER_IDS,
    wall: WallSettings | None = None,
) -> LadderReport:
    """Tables, paired differences, the slope and the X1-X6 verdicts for the corpora given.

    Raises:
        ValueError: none of `ladder_ids` is among the corpora (the scopes cannot be fixed).
    """
    ordered = sorted(corpora, key=lambda c: c.size.n_sheets)
    ladder = [c for c in ordered if c.size.corpus_id in ladder_ids]
    if not ladder:
        raise ValueError(f"expected at least one corpus among {list(ladder_ids)}, found none")
    scopes = make_scopes([c.families for c in ladder])
    cells = [cell for c in ordered for cell in cells_of_corpus(c.size.corpus_id, c.scores, scopes)]
    deltas = [d for c in ordered for d in _deltas_of_corpus(c, scopes)]
    trend = _trend(ladder, _scope_named(scopes, SCOPE_COMMON))
    ratios = [call.chars / call.tokens for c in ordered for call in c.ctx_calls]
    inputs = ClaimInputs(
        sizes=[c.size for c in ordered],
        ladder_ids=[c.size.corpus_id for c in ladder],
        cells=cells,
        deltas=deltas,
        trend=trend,
        ratios=ratios,
        wall=wall or WallSettings(),
    )
    figures = wall_figures(inputs)
    return LadderReport(
        cutoff_s=cutoff_s,
        n_boot=N_BOOT,
        seed=SEED,
        sizes=[c.size for c in ordered],
        scope_families=_scope_families(scopes, ordered),
        cells=cells,
        deltas=deltas,
        trends=[trend] if trend else [],
        claims=all_claims(inputs),
        absent=[line for c in ordered for line in c.absent],
        wall_sheets=None if isinstance(figures, str) else figures.wall_sheets,
    )


def _scope_named(scopes: Sequence[Scope], name: str) -> Scope:
    return next(s for s in scopes if s.name == name)


def _scope_families(
    scopes: Sequence[Scope], corpora: Sequence[CorpusScores]
) -> dict[str, list[str]]:
    seen = frozenset().union(*(c.families for c in corpora))
    return {s.name: sorted(s.families if s.families is not None else seen) for s in scopes}


def _deltas_of_corpus(corpus: CorpusScores, scopes: Sequence[Scope]) -> list[PairedDelta]:
    """ContextRAG-high minus cascade_v3 (every scope), and low minus high (scope `all`, X6)."""
    corpus_id = corpus.size.corpus_id
    found: list[PairedDelta | None] = []
    if CTX_HIGH in corpus.scores and CASCADE in corpus.scores:
        pair = (corpus.scores[CTX_HIGH], corpus.scores[CASCADE])
        found += [build_delta(corpus_id, s, (CTX_HIGH, CASCADE), pair) for s in scopes]
    if CTX_HIGH in corpus.scores and CTX_LOW in corpus.scores:
        found += _effort_deltas(corpus, _scope_named(scopes, SCOPE_ALL))
    return [d for d in found if d is not None]


def _effort_deltas(corpus: CorpusScores, scope: Scope) -> list[PairedDelta | None]:
    pair = (corpus.scores[CTX_LOW], corpus.scores[CTX_HIGH])
    names = (CTX_LOW, CTX_HIGH)
    corpus_id = corpus.size.corpus_id
    return [
        build_delta(corpus_id, scope, names, pair, "acc@120"),
        build_delta(corpus_id, scope, names, pair, "cost_usd"),
    ]


def _trend(ladder: Sequence[CorpusScores], scope: Scope) -> Trend | None:
    """Slope of (ContextRAG-high minus cascade_v3) over log10(sheets); `None` below two sizes."""
    samples: list[SizeSample] = []
    names: list[str] = []
    for corpus in ladder:
        if CTX_HIGH not in corpus.scores or CASCADE not in corpus.scores:
            continue
        ctx, cascade = paired_vectors(corpus.scores[CTX_HIGH], corpus.scores[CASCADE], scope)
        if not ctx:
            continue
        x = log10_sheets(corpus.size.n_sheets)
        samples.append(SizeSample(x, accuracy_differences(ctx, cascade)))
        names.append(corpus.size.corpus_id)
    if len(samples) < 2:
        return None
    interval = slope_interval(samples, N_BOOT, SEED)
    return Trend(
        scope=SCOPE_COMMON,
        slope=interval.estimate,
        ci=interval,
        n_boot=N_BOOT,
        seed=SEED,
        sizes=names,
    )
