"""Run one decider over a corpus: accepted links, their grouping, and who said what.

The pair-level answer is read after grouping (design 5.3): a candidate pair counts as "said same"
when both occurrences ended up in one predicted group, whether by a direct link, by exact tag, or
by a chain of links. This is what makes the one-to-one rule visible in the score.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.models import IdentityGroup
from plantgraph.eval.resolution_scoring import PairScore, score_identity_groups
from plantgraph.exp0004.corpus import Corpus, content_keys
from plantgraph.exp0004.d4_stats import LlmStats
from plantgraph.exp0004.metrics import Counts, Prf, prf_of
from plantgraph.exp0004.pairs import is_true_pair
from plantgraph.resolution.identity_candidates import CandidatePair, ContentKey
from plantgraph.resolution.identity_deciders import (
    ExactTagDecider,
    PairDecider,
    StringSimilarityDecider,
    UnitAwareDecider,
)
from plantgraph.resolution.identity_links import IdentityLinkSet, decide_links, group_with_links

DECIDER_IDS = ("d0", "d1", "d2", "d4")  # d4 is the chat model: built in `d4_session`


class DeciderRun(BaseModel):
    """One decider on one corpus (what `decisions/<decider>.json` holds)."""

    model_config = ConfigDict(frozen=True)

    decider: str
    threshold: float | None
    link_set: IdentityLinkSet
    said_same: list[bool]  # aligned with the corpus's pair list
    pair_level: Prf
    group_level: PairScore
    n_dropped_one_to_one: int
    n_identity_conflicts: int
    llm: LlmStats | None = None  # D4 only: calls, parse failures, cost, latency


def make_decider(decider_id: str, tau: float | None) -> PairDecider:
    """D0 takes no threshold; D1 and D2 need one; D4 is not built here.

    Raises:
        ValueError: unknown id, D4 (it needs a model client), or a missing threshold.
    """
    if decider_id == "d0":
        return ExactTagDecider()
    if decider_id == "d4":
        raise ValueError("expected d4 to be built with a chat client (d4_session), not here")
    if decider_id not in DECIDER_IDS:
        raise ValueError(f"expected a decider id in {DECIDER_IDS}, got {decider_id!r}")
    if tau is None:
        raise ValueError(f"expected a threshold for decider {decider_id}, got none")
    return StringSimilarityDecider(tau) if decider_id == "d1" else UnitAwareDecider(tau)


def run_decider(corpus: Corpus, decider: PairDecider) -> DeciderRun:
    """Decide every candidate pair, group the accepted links, score pair-level and group-level."""
    pairs = corpus.candidates.pairs
    link_set = decide_links(pairs, decider)
    grouping = group_with_links(corpus.sheets, link_set)
    predicted = _group_index(grouping.groups, content_keys(corpus.sheets))
    said_same = [_same_group(predicted, pair) for pair in pairs]
    truth = [is_true_pair(pair, corpus) for pair in pairs]
    return DeciderRun(
        decider=decider.name,
        threshold=getattr(decider, "threshold", None),
        link_set=link_set,
        said_same=said_same,
        pair_level=prf_of(count_outcomes(said_same, truth)),
        group_level=_group_level(corpus, grouping.groups),
        n_dropped_one_to_one=grouping.n_dropped_one_to_one,
        n_identity_conflicts=grouping.n_identity_conflicts,
    )


def count_outcomes(said_same: Sequence[bool], truth: Sequence[bool]) -> Counts:
    """True/false positives and false negatives of the answers against the truth."""
    pairs = list(zip(said_same, truth, strict=True))
    return Counts(
        tp=sum(1 for said, true in pairs if said and true),
        fp=sum(1 for said, true in pairs if said and not true),
        fn=sum(1 for said, true in pairs if true and not said),
    )


def _group_index(
    groups: Sequence[IdentityGroup], keys: dict[str, ContentKey]
) -> dict[ContentKey, int]:
    """Content key to the index of its predicted group (members are local keys)."""
    return {
        keys[member]: index
        for index, group in enumerate(groups)
        for member in (group.home, *group.references)
    }


def _same_group(index: dict[ContentKey, int], pair: CandidatePair) -> bool:
    first = index.get(pair.first)
    return first is not None and first == index.get(pair.second)


def _group_level(corpus: Corpus, groups: Sequence[IdentityGroup]) -> PairScore:
    """`score_identity_groups` on original keys (predicted groups translated back)."""
    to_original = corpus.occurrence_map.local_to_original
    translated = [
        group.model_copy(
            update={
                "home": to_original[group.home],
                "references": [to_original[member] for member in group.references],
            }
        )
        for group in groups
    ]
    return score_identity_groups(translated, corpus.manifest.identity_groups)
