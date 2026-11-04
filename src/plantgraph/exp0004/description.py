"""Corpus counts and the blocking gate I0 (what `build` writes into `corpus.json`)."""

from __future__ import annotations

from pydantic import BaseModel

from plantgraph.eval.blocking_metrics import (
    BlockingMetrics,
    gold_links_from_groups,
    score_blocking,
)
from plantgraph.exp0004.corpus import Corpus, CorpusSpec
from plantgraph.exp0004.pairs import PairRecord
from plantgraph.resolution.identity_deciders import units_agree


class CorpusDescription(BaseModel):
    """Counts of a built corpus and its blocking quality."""

    n_units: int
    n_sheets: int
    generate_s: float
    n_identity_groups: int
    n_variant_draws: int
    blocking: BlockingMetrics
    n_candidates_true: int
    n_candidates_false: int
    units_agree_true: int  # the context fact behind D2: true pairs whose units agree
    units_agree_false: int
    n_ambiguous_occurrences: int
    n_without_digits: int


class CorpusFile(BaseModel):
    """What `build` writes as `corpus.json`: the spec to rebuild from, and what came out."""

    spec: CorpusSpec
    description: CorpusDescription


def describe(corpus: Corpus, records: list[PairRecord]) -> CorpusDescription:
    """Counts, the blocking gate and the units facts of `corpus`."""
    groups = corpus.manifest.identity_groups
    gold_links = gold_links_from_groups(groups, corpus.occurrence_map, corpus.sheets)
    truth = [record.is_true for record in records]
    agree = [units_agree(pair) for pair in corpus.candidates.pairs]
    return CorpusDescription(
        n_units=corpus.n_units,
        n_sheets=len(corpus.sheets),
        generate_s=round(corpus.generate_s, 1),
        n_identity_groups=len(groups),
        n_variant_draws=len(corpus.draws),
        blocking=score_blocking(corpus.candidates, gold_links),
        n_candidates_true=sum(truth),
        n_candidates_false=len(records) - sum(truth),
        units_agree_true=sum(a for a, t in zip(agree, truth, strict=True) if t),
        units_agree_false=sum(a for a, t in zip(agree, truth, strict=True) if not t),
        n_ambiguous_occurrences=corpus.candidates.n_ambiguous_occurrences,
        n_without_digits=corpus.candidates.n_without_digits,
    )
