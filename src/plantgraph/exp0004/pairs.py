"""The candidate pairs of a corpus as plain, labelled records.

Truth definition: a candidate pair is a true link iff both occurrences sit in the same gold identity
group. That counts every pair of a group (reference-reference too, as
`eval/resolution_scoring.score_identity_groups` does), not only home-reference pairs.

Family and operator are gold-side facts read from the variant draws; no decider ever sees them.
A pair gets the family and operator of the first rewritten occurrence in it (first, then second).
A pair with no rewritten occurrence has family and operator `NONE`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.exp0004.corpus import Corpus
from plantgraph.resolution.identity_candidates import CandidatePair, ContentKey

NONE = "none"


class PairRecord(BaseModel):
    """One candidate pair with its gold label; `index` is its position in the corpus's pair list."""

    model_config = ConfigDict(frozen=True)

    index: int
    first: ContentKey
    second: ContentKey
    block: str  # pairs that share a blocking key compete with each other: the bootstrap's cluster
    is_true: bool
    family: str
    operator: str


class PairFile(BaseModel):
    """What `build` writes as `pairs.json`."""

    corpus_id: str
    pairs: list[PairRecord]


def build_pair_records(corpus: Corpus) -> list[PairRecord]:
    """Label every candidate pair of `corpus`, in the candidate generator's order."""
    return [_record(index, pair, corpus) for index, pair in enumerate(corpus.candidates.pairs)]


def is_true_pair(pair: CandidatePair, corpus: Corpus) -> bool:
    """Both occurrences are in one gold identity group."""
    first = corpus.gold_group_of.get(pair.first)
    return first is not None and first == corpus.gold_group_of.get(pair.second)


def _record(index: int, pair: CandidatePair, corpus: Corpus) -> PairRecord:
    family, operator = _family_and_operator(pair, corpus)
    return PairRecord(
        index=index,
        first=pair.first,
        second=pair.second,
        block=":".join(pair.blocking_key),
        is_true=is_true_pair(pair, corpus),
        family=family,
        operator=operator,
    )


def _family_and_operator(pair: CandidatePair, corpus: Corpus) -> tuple[str, str]:
    draw = corpus.draw_of.get(pair.first) or corpus.draw_of.get(pair.second)
    if draw is None:
        return NONE, NONE
    return draw.family, draw.operator
