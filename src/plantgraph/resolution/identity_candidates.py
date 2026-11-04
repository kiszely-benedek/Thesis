"""Candidate pairs for identity resolution: which occurrences might be one item.

Design: `exp0004-v2.md` section 5.2.

When the same equipment is drawn on two sheets with differently written tags, comparing every
occurrence with every other is quadratic in plant size. **Blocking** keeps only pairs that share a
cheap key, so a decider (string score, rule or model) judges a short list. The key is the node
class plus the tag's digits with every "0" removed: formatting changes (separators, zero padding,
case) and class-code synonyms leave it intact, while a different item rarely shares it.

Content keys `(sheet_id, tag, node_class)` name an occurrence by what is printed, never by its id,
so a salt-renamed `localize()` (gate G2) yields the same candidates. Answer-key-free: scoring
the blocking against the gold links lives in `eval/blocking_metrics.py`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from itertools import combinations
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.models import ConnectorPair
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.resolution.identity_card import (
    OccurrenceDescription,
    describe_occurrence,
    render_pair_card,
    richer_first,
)


class ContentKey(NamedTuple):
    """An occurrence named by what is printed: sheet, tag and class. Never an occurrence id."""

    sheet_id: str
    tag: str
    node_class: str


#: (node_class, the tag's digits without zeros) — occurrences sharing it may be the same item
BlockingKey = tuple[str, str]


class CandidatePair(BaseModel):
    """Two occurrences on different sheets that might be one item, with the card a decider reads.

    `first` is occurrence A of the card (more properties; tie: lower sheet id).
    """

    model_config = ConfigDict(frozen=True)

    first: ContentKey
    second: ContentKey
    blocking_key: BlockingKey
    card: str
    # the card's unit facts in structured form (same source), for context rules like D2;
    # a unit is None when the symbol prints none (a reference), the sheet units are sorted
    first_unit: str | None = None
    first_sheet_units: tuple[str, ...] = ()
    second_unit: str | None = None
    second_sheet_units: tuple[str, ...] = ()

    def unordered(self) -> frozenset[ContentKey]:
        """The pair without an order, to compare with gold links."""
        return frozenset((self.first, self.second))


class CandidateSet(BaseModel):
    """All candidate pairs of a corpus, in a deterministic order, with what was left out."""

    model_config = ConfigDict(frozen=True)

    pairs: list[CandidatePair]
    #: tagged equipment occurrences seen; all-pairs = n*(n-1)/2 is the reduction ratio's baseline
    n_occurrences: int
    #: occurrences whose content key appears twice on one sheet: no safe decision, left out
    n_ambiguous_occurrences: int
    #: occurrences whose tag has no non-zero digit: the blocking key cannot be formed
    n_without_digits: int


def blocking_key(tag: str, node_class: str) -> BlockingKey | None:
    """The blocking key of a tag, or None when the tag has no non-zero digit."""
    digits = "".join(ch for ch in tag if ch.isdigit() and ch != "0")
    return (node_class, digits) if digits else None


def generate_candidates(
    sheets: Sequence[SheetGraph],
    connector_pairs: Sequence[ConnectorPair],
    classes: frozenset[str] = EQUIPMENT_CLASSES,
) -> CandidateSet:
    """Block the equipment occurrences of localized `sheets` and build one card per candidate pair.

    Pairs on one sheet are excluded (an item is drawn once per sheet), and so are pairs with equal
    tag and class (already grouped by `identity.group_identities`). `connector_pairs` come from
    the resolver's own `pair_connectors`; they only feed the card's sheet-link line.
    """
    tagged = _tagged_occurrences(sheets, classes)
    unique, n_ambiguous = _drop_ambiguous_content_keys(tagged)
    blocks, n_without_digits = _blocks(unique)
    sheets_by_id = {sheet.sheet_id: sheet for sheet in sheets}
    joins = _connector_pairs_between_sheets(connector_pairs)
    descriptions: dict[ContentKey, OccurrenceDescription] = {}
    pairs = [
        _candidate_pair(key, one, other, sheets_by_id, joins, descriptions)
        for key, members in sorted(blocks.items())
        for one, other in _cross_sheet_pairs(members)
    ]
    pairs.sort(key=lambda pair: (pair.blocking_key, pair.first, pair.second))
    return CandidateSet(
        pairs=pairs,
        n_occurrences=len(tagged),
        n_ambiguous_occurrences=n_ambiguous,
        n_without_digits=n_without_digits,
    )


def content_key_of(sheet_id: str, attributes: dict[str, object]) -> ContentKey:
    """The content key of a node's attributes on `sheet_id`; the node needs a tag and a class."""
    return ContentKey(sheet_id, str(attributes["tag"]), str(attributes["node_class"]))


# --- steps -------------------------------------------------------------------------------------


class _Tagged(NamedTuple):
    key: ContentKey
    node_id: str  # needed to read the neighbourhood; never leaves this module's card building


def _tagged_occurrences(sheets: Sequence[SheetGraph], classes: frozenset[str]) -> list[_Tagged]:
    """Every tagged occurrence of `classes` (connector stubs carry no tag, so they never match)."""
    found: list[_Tagged] = []
    for sheet in sheets:
        for node_id, attributes in sheet.graph.nodes(data=True):
            if attributes.get("tag") and attributes.get("node_class") in classes:
                found.append(_Tagged(content_key_of(sheet.sheet_id, attributes), node_id))
    return found


def _drop_ambiguous_content_keys(tagged: list[_Tagged]) -> tuple[list[_Tagged], int]:
    """Drop occurrences whose content key is not unique (same sheet, tag and class twice)."""
    counts = Counter(occurrence.key for occurrence in tagged)
    unique = [occurrence for occurrence in tagged if counts[occurrence.key] == 1]
    return unique, len(tagged) - len(unique)


def _blocks(occurrences: list[_Tagged]) -> tuple[dict[BlockingKey, list[_Tagged]], int]:
    blocks: dict[BlockingKey, list[_Tagged]] = defaultdict(list)
    n_without_digits = 0
    for occurrence in occurrences:
        key = blocking_key(occurrence.key.tag, occurrence.key.node_class)
        if key is None:
            n_without_digits += 1
            continue
        blocks[key].append(occurrence)
    return blocks, n_without_digits


def _cross_sheet_pairs(members: list[_Tagged]) -> list[tuple[_Tagged, _Tagged]]:
    """Block pairs on different sheets, tag or class differing (equal ones are exact-grouped)."""
    return [
        (one, other)
        for one, other in combinations(sorted(members), 2)
        if one.key.sheet_id != other.key.sheet_id
        and (one.key.tag, one.key.node_class) != (other.key.tag, other.key.node_class)
    ]


def _connector_pairs_between_sheets(
    connector_pairs: Sequence[ConnectorPair],
) -> Counter[frozenset[str]]:
    """How many off-page connector pairs join each unordered pair of sheets."""
    joins: Counter[frozenset[str]] = Counter()
    for pair in connector_pairs:
        # a connector key is "sheet:occurrence id"; sheet ids never contain ':'
        joins[frozenset((pair.from_key.partition(":")[0], pair.to_key.partition(":")[0]))] += 1
    return joins


def _candidate_pair(
    key: BlockingKey,
    one: _Tagged,
    other: _Tagged,
    sheets_by_id: dict[str, SheetGraph],
    joins: Counter[frozenset[str]],
    descriptions: dict[ContentKey, OccurrenceDescription],
) -> CandidatePair:
    first, second = richer_first(
        _description(one, sheets_by_id, descriptions),
        _description(other, sheets_by_id, descriptions),
    )
    key_on_sheet = {one.key.sheet_id: one.key, other.key.sheet_id: other.key}  # sheets differ
    n_joining = joins[frozenset((first.sheet_id, second.sheet_id))]
    return CandidatePair(
        first=key_on_sheet[first.sheet_id],
        second=key_on_sheet[second.sheet_id],
        blocking_key=key,
        card=render_pair_card(first, second, n_joining),
        first_unit=first.unit,
        first_sheet_units=first.units_on_sheet,
        second_unit=second.unit,
        second_sheet_units=second.units_on_sheet,
    )


def _description(
    occurrence: _Tagged,
    sheets_by_id: dict[str, SheetGraph],
    descriptions: dict[ContentKey, OccurrenceDescription],
) -> OccurrenceDescription:
    """Describe an occurrence once; every pair of its block reuses the result."""
    if occurrence.key not in descriptions:
        sheet = sheets_by_id[occurrence.key.sheet_id]
        descriptions[occurrence.key] = describe_occurrence(sheet, occurrence.node_id)
    return descriptions[occurrence.key]
