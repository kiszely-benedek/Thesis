"""How good is the blocking? Pair completeness and reduction ratio (design `exp0004-v2.md` 5.2).

Blocking (`resolution/identity_candidates.py`) keeps a short list of candidate pairs. Two numbers
say whether the list is any good, and both need the answer key, which is why they live here and
not in `resolution/`:

- **pair completeness**: the share of true same-item links that are on the list (1.0: none lost);
- **reduction ratio**: how much of the all-pairs work blocking saved (0.99: 1 % of all pairs left).

A *gold link* is a (home, reference) pair of one `IdentityGroup`: the full drawing and one of its
short repeats. A link whose two tags are still equal is not blocking's job (the exact-tag resolver
already merges it), so it is not counted.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from pydantic import BaseModel

from plantgraph.benchmark.models import IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.identity_candidates import CandidateSet, ContentKey, content_key_of
from plantgraph.resolution.localize import OccurrenceMap


class BlockingMetrics(BaseModel):
    """Counts and ratios of one blocking run. A ratio is None when its denominator is zero."""

    n_candidates: int
    n_all_pairs: int  # n*(n-1)/2 over all tagged equipment occurrences
    n_gold_links: int
    n_gold_links_found: int
    pair_completeness: float | None
    reduction_ratio: float | None


def score_blocking(
    candidates: CandidateSet, gold_links: Collection[frozenset[ContentKey]]
) -> BlockingMetrics:
    """Compare the candidate list with the gold links (both as unordered content-key pairs)."""
    candidate_set = {pair.unordered() for pair in candidates.pairs}
    found = sum(1 for link in gold_links if link in candidate_set)
    n_all_pairs = candidates.n_occurrences * (candidates.n_occurrences - 1) // 2
    n_candidates = len(candidates.pairs)
    return BlockingMetrics(
        n_candidates=n_candidates,
        n_all_pairs=n_all_pairs,
        n_gold_links=len(gold_links),
        n_gold_links_found=found,
        pair_completeness=found / len(gold_links) if gold_links else None,
        reduction_ratio=1 - n_candidates / n_all_pairs if n_all_pairs else None,
    )


def gold_links_from_groups(
    groups: Sequence[IdentityGroup], occurrence_map: OccurrenceMap, sheets: Sequence[SheetGraph]
) -> set[frozenset[ContentKey]]:
    """The gold links of `groups`, named by the content keys of the localized `sheets`.

    Args:
        groups: the answer key's identity groups (original "sheet:node_id" keys).
        occurrence_map: from `localize()`; undone here to find each occurrence on `sheets`.
        sheets: the localized sheets the candidates were generated from.

    Raises:
        ValueError: if a group names an occurrence that is not on `sheets`.
    """
    original_to_local = {
        original: local for local, original in occurrence_map.local_to_original.items()
    }
    keys = _content_keys_by_local_key(sheets)
    links: set[frozenset[ContentKey]] = set()
    for group in groups:
        home = _lookup(keys, original_to_local, group.home)
        for reference in group.references:
            repeat = _lookup(keys, original_to_local, reference)
            if (home.tag, home.node_class) != (repeat.tag, repeat.node_class):
                links.add(frozenset((home, repeat)))
    return links


def _content_keys_by_local_key(sheets: Sequence[SheetGraph]) -> dict[str, ContentKey]:
    return {
        f"{sheet.sheet_id}:{node_id}": content_key_of(sheet.sheet_id, attributes)
        for sheet in sheets
        for node_id, attributes in sheet.graph.nodes(data=True)
        if attributes.get("tag") and attributes.get("node_class")
    }


def _lookup(
    keys: dict[str, ContentKey], original_to_local: dict[str, str], original_key: str
) -> ContentKey:
    local_key = original_to_local.get(original_key)
    if local_key is None or local_key not in keys:
        raise ValueError(
            f"expected occurrence {original_key!r} on the localized sheets, found none"
        )
    return keys[local_key]
