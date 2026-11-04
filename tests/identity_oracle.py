"""Test helper: the perfect decider. Links every home occurrence to each of its references.

It reads the answer key (`SplitManifest.identity_groups` + the `OccurrenceMap`), so it is only for
tests: it shows what the grouping can achieve when the decider is right.
"""

from __future__ import annotations

from plantgraph.ingest.pipeline import SyntheticCorpus
from plantgraph.resolution.identity_candidates import ContentKey, content_key_of
from plantgraph.resolution.identity_links import IdentityLink, IdentityLinkSet


def oracle_links(corpus: SyntheticCorpus) -> IdentityLinkSet:
    """One link per gold reference, home to reference, keyed by content key."""
    local_of = {orig: local for local, orig in corpus.occurrence_map.local_to_original.items()}
    key_of = _content_keys_by_local_key(corpus)
    links = [
        IdentityLink(
            first=key_of[local_of[group.home]],
            second=key_of[local_of[reference]],
            score=1.0,
            string_score=1.0,
        )
        for group in corpus.manifest.identity_groups
        for reference in group.references
    ]
    return IdentityLinkSet(decider="oracle", links=links)


def _content_keys_by_local_key(corpus: SyntheticCorpus) -> dict[str, ContentKey]:
    return {
        f"{sheet.sheet_id}:{node_id}": content_key_of(sheet.sheet_id, attributes)
        for sheet in corpus.localized_sheets
        for node_id, attributes in sheet.graph.nodes(data=True)
        if attributes.get("tag") and attributes.get("node_class")
    }
