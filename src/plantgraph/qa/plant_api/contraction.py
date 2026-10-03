"""Merge repeated drawings and join off-page connector pairs (design §3.1).

Two terms: an **identity link** (`same_tagged_item_as`) says a repeated
drawing of an item on another sheet is the same item as its *home* drawing;
an **off-page connector** pair is the two stubs (one outgoing, one incoming)
where a pipe or signal line leaves one sheet and continues on another.

After contraction, `X -> out-stub ~ in-stub -> Y` is one edge `X -> Y` that
remembers the stubs it crossed (`via`), so a walk never stops at a sheet edge.
Only occurrence classes and the resolver's edges are read; no gold id.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast, get_args

from plantgraph.graph import schema
from plantgraph.qa.graph_view import EdgeRecord
from plantgraph.qa.plant_api.model import ItemEdge, ItemRelation, PropertyValue
from plantgraph.qa.serialize import graphml_safe

_OUT_STUBS = frozenset(
    {
        schema.NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value,
        schema.NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
    }
)
_ITEM_RELATIONS: frozenset[str] = frozenset(get_args(ItemRelation))
_CONTINUES_AS = schema.Relation.CONTINUES_AS.value
_SAME_ITEM = schema.Relation.SAME_TAGGED_ITEM_AS.value
_EDGE_PROPERTY_KEYS = schema.VISIBLE_EDGE_PROPERTIES - {"relation"}

#: One contracted edge: (source, target, relation, stubs crossed, visible edge properties).
_Walked = tuple[str, str, ItemRelation, tuple[str, ...], dict[str, PropertyValue]]


@dataclass(frozen=True)
class Contraction:
    """What contraction found: which item each drawing belongs to, and the merged edges."""

    #: Reference drawing key -> home drawing key. A drawing not listed is its own home.
    home_of: dict[str, str]
    #: Outgoing stub key -> its incoming partner's key (paired stubs only).
    partner_of_out: dict[str, str]
    #: Duplicates removed, sorted; endpoints are home keys (an unpaired stub is its own item).
    edges: list[ItemEdge]


def contract(classes: Mapping[str, str], edges: Sequence[EdgeRecord]) -> Contraction:
    """Contract identity links and stub pairs.

    Args:
        classes: drawing key -> node class, for every drawing in the corpus.
        edges: every resolver edge, including `continues_as` and `same_tagged_item_as`.

    Raises:
        ValueError: an identity chain loops, a stub pair has no outgoing end, or a
            paired stub sits in a role the schema forbids (an edge out of an
            outgoing stub or into an incoming one).
    """
    home_of = _identity_homes(edges)
    partner_of_out = _stub_partners(classes, edges)
    walker = _StubWalker(
        partner_of_out=partner_of_out,
        in_stubs=frozenset(partner_of_out.values()),
        outgoing=_outgoing_topology(edges),
    )
    merged = [
        ItemEdge(
            source=home_of.get(source, source),
            target=home_of.get(target, target),
            relation=relation,
            via=via,
            properties=properties,
        )
        for source, target, relation, via, properties in walker.contracted_edges()
    ]
    return Contraction(home_of=home_of, partner_of_out=partner_of_out, edges=_dedupe(merged))


def _identity_homes(edges: Sequence[EdgeRecord]) -> dict[str, str]:
    """Reference -> final home, following a chain of identity links to its end."""
    direct = {edge.source: edge.target for edge in edges if edge.relation == _SAME_ITEM}
    return {reference: _final_home(reference, direct) for reference in direct}


def _final_home(reference: str, direct: Mapping[str, str]) -> str:
    seen = {reference}
    home = direct[reference]
    while home in direct:
        if home in seen:
            raise ValueError(f"identity links loop through {sorted(seen)[:5]}; expected a tree")
        seen.add(home)
        home = direct[home]
    return home


def _stub_partners(classes: Mapping[str, str], edges: Sequence[EdgeRecord]) -> dict[str, str]:
    """Pair edges (`continues_as`) as outgoing stub -> incoming stub, oriented by class."""
    partners: dict[str, str] = {}
    for edge in edges:
        if edge.relation != _CONTINUES_AS:
            continue
        if classes[edge.source] in _OUT_STUBS:
            partners[edge.source] = edge.target
        elif classes[edge.target] in _OUT_STUBS:
            partners[edge.target] = edge.source
        else:
            raise ValueError(
                f"continues_as {edge.source!r} -> {edge.target!r} joins no outgoing stub; "
                f"classes found: {classes[edge.source]}, {classes[edge.target]}"
            )
    return partners


def _outgoing_topology(edges: Sequence[EdgeRecord]) -> dict[str, list[EdgeRecord]]:
    outgoing: dict[str, list[EdgeRecord]] = {}
    for edge in sorted(edges, key=lambda e: (e.source, e.target, e.relation)):
        if edge.relation in _ITEM_RELATIONS:
            outgoing.setdefault(edge.source, []).append(edge)
    return outgoing


@dataclass(frozen=True)
class _StubWalker:
    partner_of_out: Mapping[str, str]
    in_stubs: frozenset[str]
    outgoing: Mapping[str, list[EdgeRecord]]

    def contracted_edges(self) -> list[_Walked]:
        """Every edge, with stub pairs walked through; properties come from the walked-in edge."""
        found: list[_Walked] = []
        for source in sorted(self.outgoing):
            for edge in self.outgoing[source]:
                found.extend(self._edges_from(edge))
        return found

    def _edges_from(self, edge: EdgeRecord) -> list[_Walked]:
        if edge.source in self.in_stubs:
            return []  # consumed when the matching outgoing stub's incoming edge is walked
        self._require_expected_roles(edge)
        relation = _item_relation(edge.relation)
        properties = _edge_properties(edge)
        if edge.target not in self.partner_of_out:
            return [(edge.source, edge.target, relation, (), properties)]
        return [
            (edge.source, final, relation, via, properties)
            for final, via in self._cross(edge.target, ())
        ]

    def _require_expected_roles(self, edge: EdgeRecord) -> None:
        if edge.source in self.partner_of_out or edge.target in self.in_stubs:
            raise ValueError(
                f"edge {edge.source!r} -> {edge.target!r} leaves a paired outgoing stub or "
                "enters a paired incoming stub; the schema allows the reverse only"
            )

    def _cross(self, out_stub: str, via: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
        """Items reached beyond a paired outgoing stub; a chain of stubs is walked through."""
        if out_stub in via:
            raise ValueError(f"stub pairs loop through {list(via)[:5]}; expected a chain")
        in_stub = self.partner_of_out[out_stub]
        crossed = (*via, out_stub, in_stub)
        reached: list[tuple[str, tuple[str, ...]]] = []
        for edge in self.outgoing.get(in_stub, ()):
            if edge.target in self.partner_of_out:
                reached.extend(self._cross(edge.target, crossed))
            else:
                reached.append((edge.target, crossed))
        return reached


def _item_relation(value: str) -> ItemRelation:
    if value not in _ITEM_RELATIONS:
        raise ValueError(f"expected one of {sorted(_ITEM_RELATIONS)}, found relation {value!r}")
    return cast(ItemRelation, value)


def _edge_properties(edge: EdgeRecord) -> dict[str, PropertyValue]:
    return {
        key: graphml_safe(value)
        for key, value in sorted(edge.properties.items())
        if key in _EDGE_PROPERTY_KEYS and value is not None
    }


def _dedupe(edges: list[ItemEdge]) -> list[ItemEdge]:
    """One edge per (source, target, relation); the one crossing fewest stubs wins.

    A repeated drawing and its home can both show the same pipe, one of them
    cut by a connector; after merging they are the same plant edge.
    """
    best: dict[tuple[str, str, str], ItemEdge] = {}
    for edge in sorted(edges, key=lambda e: (e.source, e.target, e.relation, len(e.via), e.via)):
        best.setdefault((edge.source, edge.target, edge.relation), edge)
    return list(best.values())
