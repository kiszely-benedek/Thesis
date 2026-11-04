"""Identity links: accepted "these two are one item" decisions, and the groups they form.

Design: `exp0004-v2.md` section 5.3. A decider (`identity_deciders.py`) judges candidate pairs;
the accepted ones become `IdentityLink`s. Grouping then merges them with the groups found by exact
tag (today's resolver) into `IdentityGroup`s: one physical item, drawn on several sheets.

Links name occurrences by content key (sheet, tag, class), never by occurrence id, so a
salt-renamed `localize()` (gate G2) maps them onto the same groups.

Two rules keep a wrong link from merging two real items. Both rest on one fact: an item is drawn
at most once per sheet.
- **One-to-one**: an occurrence links to at most one occurrence per other sheet, best score first.
  This is what separates the installed spares `P-1203A` and `P-1203B` when both look alike.
- **Same-sheet split**: a link that would put two occurrences of one sheet into one group is
  refused and counted as an identity conflict.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.models import IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.resolution.identity import group_identities
from plantgraph.resolution.identity_candidates import CandidatePair, ContentKey, content_key_of
from plantgraph.resolution.identity_deciders import PairDecider, string_similarity


class IdentityLink(BaseModel):
    """One accepted pair, named by content keys."""

    model_config = ConfigDict(frozen=True)

    first: ContentKey
    second: ContentKey
    score: float  # the decider's score; the order in which links compete for the one-to-one rule
    string_score: float  # D1's tag similarity; breaks ties between equal scores


class IdentityLinkSet(BaseModel):
    """The links one decider accepted on one corpus (what the `--identity-links` file holds)."""

    model_config = ConfigDict(frozen=True)

    decider: str
    links: list[IdentityLink]


class LinkedGrouping(BaseModel):
    """Identity groups after merging links, with what the two rules removed."""

    groups: list[IdentityGroup]
    n_ambiguous_tag_keys: int  # exact-tag keys duplicated on one sheet (as `group_identities`)
    n_dropped_one_to_one: int
    n_identity_conflicts: int


def decide_links(pairs: Sequence[CandidatePair], decider: PairDecider) -> IdentityLinkSet:
    """Run `decider` over `pairs` and keep the accepted ones as links."""
    links: list[IdentityLink] = []
    for pair in pairs:
        decision = decider.decide(pair)
        if decision.accept:
            links.append(
                IdentityLink(
                    first=pair.first,
                    second=pair.second,
                    score=decision.score,
                    string_score=string_similarity(pair.first.tag, pair.second.tag),
                )
            )
    return IdentityLinkSet(decider=decider.name, links=links)


def group_with_links(
    sheets: Sequence[SheetGraph],
    link_set: IdentityLinkSet,
    classes: frozenset[str] = EQUIPMENT_CLASSES,
) -> LinkedGrouping:
    """Exact-tag groups plus the links, under the one-to-one rule and the same-sheet split.

    Raises:
        ValueError: a link names a content key that is not a unique occurrence on `sheets`.
    """
    exact_groups, n_ambiguous = group_identities(sheets, classes)
    nodes = _equipment_nodes(sheets, classes)
    by_content_key = _unique_by_content_key(nodes)
    kept, n_dropped = _one_to_one(_in_priority_order(link_set.links))

    components = _Components(nodes)
    for group in exact_groups:
        components.merge_exact_group([group.home, *group.references])
    n_conflicts = 0
    for link in kept:
        one, other = _local_key(by_content_key, link.first), _local_key(by_content_key, link.second)
        if not components.merge(one, other):
            n_conflicts += 1
    return LinkedGrouping(
        groups=components.groups(),
        n_ambiguous_tag_keys=n_ambiguous,
        n_dropped_one_to_one=n_dropped,
        n_identity_conflicts=n_conflicts,
    )


# --- steps -------------------------------------------------------------------------------------


class _Node(NamedTuple):
    local_key: str  # "sheet:node id", as `identity.group_identities` writes it
    content_key: ContentKey
    property_count: int


def _equipment_nodes(sheets: Sequence[SheetGraph], classes: frozenset[str]) -> dict[str, _Node]:
    """Every tagged equipment occurrence, by local key."""
    nodes: dict[str, _Node] = {}
    for sheet in sheets:
        for node_id, attributes in sheet.graph.nodes(data=True):
            if attributes.get("tag") and attributes.get("node_class") in classes:
                local_key = f"{sheet.sheet_id}:{node_id}"
                content_key = content_key_of(sheet.sheet_id, attributes)
                nodes[local_key] = _Node(local_key, content_key, len(attributes))
    return nodes


def _unique_by_content_key(nodes: dict[str, _Node]) -> dict[ContentKey, str]:
    """Content key to local key; keys printed twice on one sheet are ambiguous and left out."""
    found: dict[ContentKey, list[str]] = {}
    for node in nodes.values():
        found.setdefault(node.content_key, []).append(node.local_key)
    return {key: local_keys[0] for key, local_keys in found.items() if len(local_keys) == 1}


def _local_key(by_content_key: dict[ContentKey, str], key: ContentKey) -> str:
    if key not in by_content_key:
        raise ValueError(
            f"expected the link's occurrence {tuple(key)} to be unique on the given sheets; "
            "it is missing or printed twice on its sheet"
        )
    return by_content_key[key]


def _in_priority_order(links: Sequence[IdentityLink]) -> list[IdentityLink]:
    """Best score first; ties by D1 score (higher first), then content key, so order is stable."""
    return sorted(
        links, key=lambda link: (-link.score, -link.string_score, link.first, link.second)
    )


def _one_to_one(ordered: Sequence[IdentityLink]) -> tuple[list[IdentityLink], int]:
    """Drop a link when either occurrence already has a link to the other one's sheet."""
    taken: set[tuple[ContentKey, str]] = set()  # (occurrence, the other sheet it is linked to)
    kept: list[IdentityLink] = []
    for link in ordered:
        slots = {(link.first, link.second.sheet_id), (link.second, link.first.sheet_id)}
        if slots & taken:
            continue
        taken |= slots
        kept.append(link)
    return kept, len(ordered) - len(kept)


class _Components:
    """Union-find over occurrences that refuses a merge putting two of one sheet together."""

    def __init__(self, nodes: dict[str, _Node]) -> None:
        self._nodes = nodes
        self._parent = {key: key for key in nodes}
        self._sheets = {key: {node.content_key.sheet_id} for key, node in nodes.items()}

    def merge_exact_group(self, local_keys: list[str]) -> None:
        """Merge an exact-tag group; `group_identities` already guarantees one per sheet."""
        for other in local_keys[1:]:
            self.merge(local_keys[0], other)

    def merge(self, one: str, other: str) -> bool:
        """Join two occurrences' components; False (and no change) on a same-sheet conflict."""
        root_one, root_other = self._find(one), self._find(other)
        if root_one == root_other:
            return True
        if self._sheets[root_one] & self._sheets[root_other]:
            return False
        self._parent[root_other] = root_one
        self._sheets[root_one] |= self._sheets.pop(root_other)
        return True

    def groups(self) -> list[IdentityGroup]:
        """One group per component of two or more occurrences, sorted by home tag and key."""
        members: dict[str, list[_Node]] = {}
        for key, node in self._nodes.items():
            members.setdefault(self._find(key), []).append(node)
        built = [_to_group(nodes) for nodes in members.values() if len(nodes) >= 2]
        return sorted(built, key=lambda group: (group.tag, group.home))

    def _find(self, key: str) -> str:
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]  # path halving
            key = self._parent[key]
        return key


def _to_group(nodes: list[_Node]) -> IdentityGroup:
    """Home = most properties, ties by sheet id (never the id: it must survive a G2 salt)."""
    home = min(nodes, key=lambda n: (-n.property_count, n.content_key.sheet_id))
    references = sorted(n.local_key for n in nodes if n.local_key != home.local_key)
    return IdentityGroup(tag=home.content_key.tag, home=home.local_key, references=references)
