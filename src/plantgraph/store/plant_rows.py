"""Rows for the merged plant layer: one node per physical item, built only from a `Resolution`.

The occurrence layer (`neo4j_rows.py`) stores every drawing; this layer stores
what the drawings are *of*. A pump drawn on three sheets is three occurrences
but one **plant item**, and a pipe cut by an **off-page connector** (the stub a
drafter draws where a line leaves one sheet and continues on another) is one
edge between two items, not three hops through stubs (ADR-0036).

Nothing here reads the answer key: the item set is `Resolution.plant`, and the
member lists come from the sheets plus the resolver's identity groups and
connector pairs. Pure data transformation, no `neo4j` driver import.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Literal

from plantgraph.benchmark.models import ConnectorPair
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema
from plantgraph.resolution.models import Resolution
from plantgraph.store.neo4j_rows import (
    NodeRow,
    RelationshipRow,
    corpus_row,
    has_sheet_row,
    occurrence_labels,
    plant_section_rows,
    plant_section_uid,
    process_plant_rows,
    section_in_plant_rows,
    sheet_row,
    uid,
)

#: which layers of the graph one load writes (ADR-0036)
StoreProfile = Literal["occurrence", "plant", "both"]

_TOPOLOGY_RELATION_VALUES: frozenset[str] = frozenset(
    relation.value for relation in schema.TOPOLOGY_RELATIONS
)


def item_uid(corpus_id: str, home_key: str) -> str:
    """The uid of one plant item, from its home occurrence's local key (`item:` cannot clash)."""
    return uid(corpus_id, f"item:{home_key}")


def _sheet_of(local_key: str) -> str:
    return local_key.split(":", 1)[0]


# --- who belongs to which item --------------------------------------------------------------


def _paired_stub_keys(pairs: Sequence[ConnectorPair]) -> set[str]:
    return {pair.from_key for pair in pairs} | {pair.to_key for pair in pairs}


def _home_of(resolution: Resolution) -> dict[str, str]:
    """Reference occurrence -> the home occurrence of its identity group."""
    return {
        reference: group.home
        for group in resolution.identity_groups
        for reference in group.references
    }


def members_by_item(sheets: Sequence[SheetGraph], resolution: Resolution) -> dict[str, list[str]]:
    """Home key -> the keys of every occurrence drawn for that item; paired stubs belong to none.

    Raises:
        ValueError: if the members' homes are not exactly the nodes of `resolution.plant`.
    """
    _check_no_stub_chains(sheets, resolution)
    home_of = _home_of(resolution)
    paired = _paired_stub_keys(resolution.connector_pairs)
    members: dict[str, list[str]] = defaultdict(list)
    for sheet in sorted(sheets, key=lambda sheet: sheet.sheet_id):
        for node_id in sheet.graph.nodes:
            key = f"{sheet.sheet_id}:{node_id}"
            if key not in paired:
                members[home_of.get(key, key)].append(key)
    if set(members) != set(resolution.plant.nodes):
        only_members = sorted(set(members) - set(resolution.plant.nodes))[:3]
        only_plant = sorted(set(resolution.plant.nodes) - set(members))[:3]
        raise ValueError(
            "the sheets' items and resolution.plant disagree; expected the same home keys, "
            f"found only in the sheets {only_members}, only in the plant {only_plant}"
        )
    return dict(members)


def _check_no_stub_chains(sheets: Sequence[SheetGraph], resolution: Resolution) -> None:
    """Fail early, with the chain named, before it shows up as a puzzling node mismatch."""
    sheets_by_id = {sheet.sheet_id: sheet for sheet in sheets}
    for pair in resolution.connector_pairs:
        _real_neighbour(sheets_by_id, pair.from_key, incoming=True)
        _real_neighbour(sheets_by_id, pair.to_key, incoming=False)


# --- node rows -------------------------------------------------------------------------------


def plant_node_rows(
    corpus_id: str, sheets: Sequence[SheetGraph], resolution: Resolution
) -> list[NodeRow]:
    """One `PlantItem` row per node of `resolution.plant`, with the home occurrence's properties."""
    rows = []
    for home_key in sorted(members_by_item(sheets, resolution)):
        attrs = resolution.plant.nodes[home_key]
        row_uid = item_uid(corpus_id, home_key)
        props = {"uid": row_uid, "corpus_id": corpus_id, **attrs}
        rows.append(NodeRow(_item_labels(home_key, attrs), row_uid, _without_none(props)))
    return rows


def _item_labels(home_key: str, attrs: Mapping[str, object]) -> tuple[str, ...]:
    """The occurrence's label chain with `PlantItem` (and, for a lone stub, its marker) added."""
    sheet_id, node_id = home_key.split(":", 1)
    chain = occurrence_labels(sheet_id, node_id, attrs)[1:]  # drop `CorpusNode`, re-added first
    extra = [schema.PLANT_ITEM_LABEL]
    if attrs.get("node_class") in schema.CONNECTOR_CLASSES:
        extra.append(schema.UNRESOLVED_CONNECTOR_LABEL)
    return ("CorpusNode", *extra, *chain)


def _without_none(props: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in props.items() if value is not None}


# --- relationship rows ------------------------------------------------------------------------


def plant_relationship_rows(
    corpus_id: str,
    sheets: Sequence[SheetGraph],
    resolution: Resolution,
    asserted_by: Literal["resolver", "oracle"],
) -> list[RelationshipRow]:
    """Item-to-item edges, plus each item's `is_drawn_on` sheets and `is_located_in` unit."""
    members = members_by_item(sheets, resolution)
    rows = _edge_rows(corpus_id, sheets, resolution, asserted_by)
    rows += _item_sheet_rows(corpus_id, members)
    rows += _item_unit_rows(corpus_id, resolution)
    return rows


def drawn_as_rows(
    corpus_id: str,
    sheets: Sequence[SheetGraph],
    resolution: Resolution,
    asserted_by: Literal["resolver", "oracle"],
) -> list[RelationshipRow]:
    """One `drawn_as` row per occurrence that belongs to an item: item -> occurrence."""
    return [
        RelationshipRow(
            schema.Relation.DRAWN_AS.value,
            item_uid(corpus_id, home_key),
            uid(corpus_id, member),
            {"asserted_by": asserted_by},
        )
        for home_key, keys in members_by_item(sheets, resolution).items()
        for member in keys
    ]


def _item_sheet_rows(corpus_id: str, members: Mapping[str, Sequence[str]]) -> list[RelationshipRow]:
    relation = schema.Relation.IS_DRAWN_ON.value
    return [
        RelationshipRow(relation, item_uid(corpus_id, home_key), uid(corpus_id, sheet_id), {})
        for home_key, keys in members.items()
        for sheet_id in sorted({_sheet_of(key) for key in keys})
    ]


def _item_unit_rows(corpus_id: str, resolution: Resolution) -> list[RelationshipRow]:
    relation = schema.Relation.IS_LOCATED_IN.value
    rows = []
    for home_key, attrs in resolution.plant.nodes(data=True):
        unit_id = attrs.get("unit_id")
        if isinstance(unit_id, str):
            target = plant_section_uid(corpus_id, unit_id)
            rows.append(RelationshipRow(relation, item_uid(corpus_id, home_key), target, {}))
    return rows


def _edge_rows(
    corpus_id: str,
    sheets: Sequence[SheetGraph],
    resolution: Resolution,
    asserted_by: Literal["resolver", "oracle"],
) -> list[RelationshipRow]:
    pairs_by_edge = _pairs_by_edge(sheets, resolution)
    drawn_whole = _edges_drawn_whole(sheets, resolution)
    rows = []
    for source, target, attrs in resolution.plant.edges(data=True):
        rel_type = attrs.get("relation")
        if rel_type not in _TOPOLOGY_RELATION_VALUES:
            raise ValueError(
                f"plant edge {(source, target)!r} has relation {rel_type!r}, "
                f"expected one of {sorted(_TOPOLOGY_RELATION_VALUES)}"
            )
        props = {key: value for key, value in attrs.items() if key != "relation"}
        props["asserted_by"] = asserted_by
        found = pairs_by_edge.get((source, target), [])
        if found:
            props["via_connector_uids"] = _via_uids(corpus_id, found)
        if found and (source, target) not in drawn_whole:
            first = found[0]  # pairs are sorted, so this is the smallest `via`
            props["crossed_sheets"] = [_sheet_of(first.from_key), _sheet_of(first.to_key)]
        rows.append(
            RelationshipRow(
                rel_type,
                item_uid(corpus_id, source),
                item_uid(corpus_id, target),
                _without_none(props),
            )
        )
    return rows


def _via_uids(corpus_id: str, pairs: Sequence[ConnectorPair]) -> list[str]:
    return [
        stub_uid
        for pair in pairs
        for stub_uid in (uid(corpus_id, pair.from_key), uid(corpus_id, pair.to_key))
    ]


def _pairs_by_edge(
    sheets: Sequence[SheetGraph], resolution: Resolution
) -> dict[tuple[str, str], list[ConnectorPair]]:
    """For each plant edge, the connector pairs that produced it, in (from_key, to_key) order."""
    sheets_by_id = {sheet.sheet_id: sheet for sheet in sheets}
    home_of = _home_of(resolution)
    found: dict[tuple[str, str], list[ConnectorPair]] = defaultdict(list)
    for pair in sorted(resolution.connector_pairs, key=lambda p: (p.from_key, p.to_key)):
        pred = _real_neighbour(sheets_by_id, pair.from_key, incoming=True)
        succ = _real_neighbour(sheets_by_id, pair.to_key, incoming=False)
        edge = (home_of.get(pred, pred), home_of.get(succ, succ))
        if not resolution.plant.has_edge(*edge):
            raise ValueError(
                f"pair {pair.from_key!r} -> {pair.to_key!r} joins {edge!r}, "
                "which is not an edge of resolution.plant"
            )
        found[edge].append(pair)
    return found


def _real_neighbour(sheets_by_id: Mapping[str, SheetGraph], stub_key: str, incoming: bool) -> str:
    """The one item beside a paired stub on its own sheet; raises if that is another stub.

    A stub feeding a stub (an incoming connector straight into an outgoing one)
    would make a chain of pairs; the merge never handles that, so refuse it
    here rather than guess which items the line joins.
    """
    sheet_id, node_id = stub_key.split(":", 1)
    graph = sheets_by_id[sheet_id].graph
    neighbours = list(graph.predecessors(node_id) if incoming else graph.successors(node_id))
    side = "incoming" if incoming else "outgoing"
    if len(neighbours) != 1:
        raise ValueError(
            f"stub {stub_key!r} has {len(neighbours)} {side} edges on its sheet; expected one"
        )
    if graph.nodes[neighbours[0]].get("node_class") in schema.CONNECTOR_CLASSES:
        raise ValueError(
            f"stub {stub_key!r} is joined straight to another connector "
            f"{sheet_id}:{neighbours[0]}; chains of connector pairs are not supported"
        )
    return f"{sheet_id}:{neighbours[0]}"


def _edges_drawn_whole(
    sheets: Sequence[SheetGraph], resolution: Resolution
) -> set[tuple[str, str]]:
    """Item edges that some sheet draws end to end, with no connector in between."""
    home_of = _home_of(resolution)
    paired = _paired_stub_keys(resolution.connector_pairs)
    whole: set[tuple[str, str]] = set()
    for sheet in sheets:
        for source, target in sheet.graph.edges:
            keys = (f"{sheet.sheet_id}:{source}", f"{sheet.sheet_id}:{target}")
            if not paired.intersection(keys):
                whole.add((home_of.get(keys[0], keys[0]), home_of.get(keys[1], keys[1])))
    return whole


# --- structure of a `plant`-only load -------------------------------------------------------


def plant_structure_node_rows(
    corpus_id: str, sheets: Sequence[SheetGraph], resolution: Resolution
) -> list[NodeRow]:
    """Corpus, sheet, unit and plant rows when no occurrence layer is loaded.

    Units and plants come from the items' own properties, so the plant layer
    stands alone; a test checks they equal the occurrence-derived sets.
    """
    rows = [corpus_row(corpus_id)]
    rows += [sheet_row(corpus_id, sheet) for sheet in sheets]
    rows += plant_section_rows(corpus_id, _item_values(resolution, "unit_id"))
    rows += process_plant_rows(corpus_id, _item_values(resolution, "plant_id"))
    return rows


def plant_structure_relationship_rows(
    corpus_id: str, sheets: Sequence[SheetGraph], resolution: Resolution
) -> list[RelationshipRow]:
    """`has_sheet` per sheet and unit -> plant `is_located_in`, for a `plant`-only load."""
    rows = [has_sheet_row(corpus_id, uid(corpus_id, sheet.sheet_id)) for sheet in sheets]
    plants_of_unit: dict[str, set[str]] = defaultdict(set)
    for _key, attrs in resolution.plant.nodes(data=True):
        unit_id, plant_id = attrs.get("unit_id"), attrs.get("plant_id")
        if isinstance(unit_id, str) and isinstance(plant_id, str):
            plants_of_unit[unit_id].add(plant_id)
    return rows + section_in_plant_rows(corpus_id, plants_of_unit)


def _item_values(resolution: Resolution, key: str) -> set[str]:
    values = (attrs.get(key) for _node, attrs in resolution.plant.nodes(data=True))
    return {value for value in values if isinstance(value, str)}
