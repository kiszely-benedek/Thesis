"""Identity grouping: the same equipment drawn on several sheets (design `kg-construction.md` §5.3).

The splitter draws some equipment on more than one sheet (`splitter.py:_duplicate_equipment`):
one full-attribute home occurrence, and on every neighbouring sheet a stripped-down
reference (tag and node_class only). `localize()` has already closed off the
shared node_id (L1 leak, design §4.1), so this module can only recognize that two
occurrences are the same physical equipment via the tag and the class — exactly
as a real equipment register would identify it, by tag alone.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import NamedTuple

from plantgraph.benchmark.models import IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES

#: (tag, node_class) — this identifies the physical equipment, never the occurrence id
#: (design §5.3: home selection must not depend on a salt-renamed local key).
_TagKey = tuple[str, str]


class _Occurrence(NamedTuple):
    """A single occurrence of a tag key on one localized sheet."""

    sheet_id: str
    local_key: str
    property_count: int


def group_identities(
    sheets: Sequence[SheetGraph], classes: frozenset[str] = EQUIPMENT_CLASSES
) -> tuple[list[IdentityGroup], int]:
    """Group occurrences by (tag, node_class), and pick the predicted home for each.

    Only looks at `classes` (equipment only, by default): valve tags repeat per
    pipe segment, so merging those across sheets would produce a false merge
    (design §5.3).

    Returns:
        The groups found (sorted by tag), and the count of tag keys that were
        ambiguous within a single sheet — and therefore excluded.
    """
    occurrences_by_key = _occurrences_by_tag_key(sheets, classes)
    ambiguous_tag_keys = _drop_ambiguous_within_a_sheet(occurrences_by_key)
    groups = [
        _build_group(tag, occurrences)
        for (tag, _node_class), occurrences in sorted(occurrences_by_key.items())
        if len({occ.sheet_id for occ in occurrences}) >= 2
    ]
    return groups, ambiguous_tag_keys


def _occurrences_by_tag_key(
    sheets: Sequence[SheetGraph], classes: frozenset[str]
) -> dict[_TagKey, list[_Occurrence]]:
    occurrences: dict[_TagKey, list[_Occurrence]] = defaultdict(list)
    for sheet in sheets:
        for node_id, attrs in sheet.graph.nodes(data=True):
            tag = attrs.get("tag")
            node_class = attrs.get("node_class")
            if not tag or node_class not in classes:
                continue
            local_key = f"{sheet.sheet_id}:{node_id}"
            occurrences[(tag, node_class)].append(
                _Occurrence(sheet.sheet_id, local_key, len(attrs))
            )
    return occurrences


def _drop_ambiguous_within_a_sheet(occurrences_by_key: dict[_TagKey, list[_Occurrence]]) -> int:
    """Drop a tag key if it is not unique within a single sheet (e.g. EX01's duplicated valve tags).

    None of an excluded key's occurrences join any group — the resolver would
    rather make no decision at all than guess which occurrence is the right match.
    """
    ambiguous_keys = [
        key
        for key, occurrences in occurrences_by_key.items()
        if len({occ.sheet_id for occ in occurrences}) < len(occurrences)
    ]
    for key in ambiguous_keys:
        del occurrences_by_key[key]
    return len(ambiguous_keys)


def _build_group(tag: str, occurrences: list[_Occurrence]) -> IdentityGroup:
    """The occurrence with the most properties becomes the predicted home; ties break on sheet id.

    Never the occurrence id: the G2 gate check (a salt-renamed graph) must
    produce the same home, even though the ids would be completely different.
    """
    home = min(occurrences, key=lambda occ: (-occ.property_count, occ.sheet_id))
    references = sorted(occ.local_key for occ in occurrences if occ.local_key != home.local_key)
    return IdentityGroup(tag=tag, home=home.local_key, references=references)
