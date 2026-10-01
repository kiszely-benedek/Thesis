"""One-corpus node and relationship rows, from localized sheets and a resolution.

Split out of `neo4j_plan.py` purely for the 400-line file limit (the same
reason `pydexpi_generic.py` split off from `pydexpi_adapter.py`) — this module
is still pure data transformation, still with no `neo4j` driver import.
`neo4j_plan.py` turns these rows into batched `CypherStatement`s; this module
only decides what each row is and what `uid` and labels it gets.

Vocabulary: an **occurrence** is one appearance of an equipment or piping
symbol on one sheet, and a **corpus** is one set of sheets loaded together
under one `corpus_id` (`neo4j_plan.py`'s docstring has the fuller glossary).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Literal, NamedTuple

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema
from plantgraph.resolution.models import Resolution

#: Safe Neo4j label shape (design §3.1 rule 7) — the loader cannot import pyDEXPI
#: (ADR-0003) to re-derive a `GenericItem`'s ancestor chain, so it re-checks the
#: same shape the importer already enforced, as a second, independent gate.
_LABEL_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")

#: the closed whitelist for edge relationship types read from sheet data (§7.4) —
#: `has_sheet`, `is_drawn_on`, `continues_as` and `same_tagged_item_as` never come
#: from sheet data, so they need no such check: this module writes those literals itself.
_TOPOLOGY_RELATION_VALUES: frozenset[str] = frozenset(
    relation.value for relation in schema.TOPOLOGY_RELATIONS
)

#: sentinel local key for the one corpus node — no real sheet_id may equal this
#: (`check_unique_uids` catches it if one somehow does).
_CORPUS_LOCAL_KEY = "corpus"


class NodeRow(NamedTuple):
    """One node to be created: its Neo4j label set, its uid, and its property dict."""

    labels: tuple[str, ...]
    uid: str
    props: dict[str, object]


class RelationshipRow(NamedTuple):
    """One relationship to be created, matched by the endpoints' `uid` properties."""

    rel_type: str
    source_uid: str
    target_uid: str
    props: dict[str, object]


def uid(corpus_id: str, local_key: str) -> str:
    """The store-wide unique id of one element: its corpus, plus its key within it."""
    return f"{corpus_id}|{local_key}"


def check_unique_uids(rows: Sequence[NodeRow]) -> None:
    """Raise if two node rows would collide on the same `uid` (design §7.7).

    Raises:
        ValueError: naming the duplicate uid.
    """
    seen: set[str] = set()
    for row in rows:
        if row.uid in seen:
            raise ValueError(f"duplicate node uid {row.uid!r}; every occurrence must be unique")
        seen.add(row.uid)


# --- node rows: corpus, sheets, occurrences -----------------------------------------------


def all_node_rows(corpus_id: str, sheets: Sequence[SheetGraph]) -> list[NodeRow]:
    """Every node row for one corpus: the corpus itself, each sheet, and each occurrence."""
    rows = [_corpus_row(corpus_id)]
    for sheet in sheets:
        rows.append(_sheet_row(corpus_id, sheet))
        rows += _occurrence_rows(corpus_id, sheet)
    rows += _plant_section_rows(corpus_id, sheets)
    rows += _process_plant_rows(corpus_id, sheets)
    return rows


def plant_section_uid(corpus_id: str, unit_id: str) -> str:
    """The uid of one unit's `PlantSection` (ADR-0026); `unit:` cannot clash with `sheet:occ`."""
    return uid(corpus_id, f"unit:{unit_id}")


def process_plant_uid(corpus_id: str, plant_id: str) -> str:
    """The uid of the `ProcessPlant` for one plant id (ADR-0026)."""
    return uid(corpus_id, f"plant:{plant_id}")


def _visible_ids(sheets: Sequence[SheetGraph], key: str) -> set[str]:
    """Every distinct string value of one visible property (`unit_id` or `plant_id`)."""
    found: set[str] = set()
    for sheet in sheets:
        for _node_id, attrs in sheet.graph.nodes(data=True):
            value = attrs.get(key)
            if isinstance(value, str):
                found.add(value)
    return found


def _plant_section_rows(corpus_id: str, sheets: Sequence[SheetGraph]) -> list[NodeRow]:
    """One `PlantSection` per distinct `unit_id` drawn on the sheets — never from the answer key."""
    labels = ("CorpusNode", schema.NodeClass.PLANT_SECTION.value)
    rows = []
    for unit_id in sorted(_visible_ids(sheets, "unit_id")):
        row_uid = plant_section_uid(corpus_id, unit_id)
        rows.append(
            NodeRow(labels, row_uid, {"uid": row_uid, "corpus_id": corpus_id, "unit_id": unit_id})
        )
    return rows


def _process_plant_rows(corpus_id: str, sheets: Sequence[SheetGraph]) -> list[NodeRow]:
    """One `ProcessPlant` per distinct `plant_id` drawn on the sheets."""
    labels = ("CorpusNode", schema.NodeClass.PROCESS_PLANT.value)
    rows = []
    for plant_id in sorted(_visible_ids(sheets, "plant_id")):
        row_uid = process_plant_uid(corpus_id, plant_id)
        rows.append(
            NodeRow(labels, row_uid, {"uid": row_uid, "corpus_id": corpus_id, "plant_id": plant_id})
        )
    return rows


def _corpus_row(corpus_id: str) -> NodeRow:
    row_uid = uid(corpus_id, _CORPUS_LOCAL_KEY)
    labels = ("CorpusNode", schema.NodeClass.DRAWING_SET.value)
    props = _drop_none({"uid": row_uid, "corpus_id": corpus_id, "drawing_set_id": corpus_id})
    return NodeRow(labels, row_uid, props)


def _sheet_row(corpus_id: str, sheet: SheetGraph) -> NodeRow:
    row_uid = uid(corpus_id, sheet.sheet_id)
    labels = ("CorpusNode", schema.NodeClass.SHEET.value)
    props = _drop_none({"uid": row_uid, "corpus_id": corpus_id, "sheet_id": sheet.sheet_id})
    return NodeRow(labels, row_uid, props)


def _occurrence_rows(corpus_id: str, sheet: SheetGraph) -> list[NodeRow]:
    """One row per node already on the (localized) sheet — off-page connector stubs included."""
    rows = []
    for node_id, attrs in sheet.graph.nodes(data=True):
        local_key = f"{sheet.sheet_id}:{node_id}"
        row_uid = uid(corpus_id, local_key)
        labels = _occurrence_labels(sheet.sheet_id, node_id, attrs)
        props = _drop_none({"uid": row_uid, "corpus_id": corpus_id, **attrs})
        rows.append(NodeRow(labels, row_uid, props))
    return rows


def _occurrence_labels(sheet_id: str, node_id: str, attrs: Mapping[str, object]) -> tuple[str, ...]:
    """The Neo4j label set for one occurrence: `CorpusNode` plus its class chain.

    A known class's chain comes straight from `labels_for`. A `GenericItem`
    additionally carries its own real pyDEXPI ancestor chain as a node
    property (`dexpi_labels`) — the one case where a label comes from sheet
    data rather than the schema, so it is re-validated here (§3.1 rule 7).
    """
    node_class = attrs.get("node_class")
    if not isinstance(node_class, str):
        raise ValueError(f"sheet {sheet_id!r} node {node_id!r} has no string node_class")
    class_labels = schema.labels_for(node_class)
    if node_class != schema.NodeClass.GENERIC_ITEM.value:
        return ("CorpusNode", *class_labels)
    generic_chain = _validated_generic_chain(sheet_id, node_id, attrs)
    return ("CorpusNode", *generic_chain, *class_labels)


def _validated_generic_chain(
    sheet_id: str, node_id: str, attrs: Mapping[str, object]
) -> tuple[str, ...]:
    chain = attrs.get("dexpi_labels", [])
    if not isinstance(chain, list):
        raise ValueError(f"sheet {sheet_id!r} node {node_id!r} has a non-list dexpi_labels")
    for label in chain:
        if not isinstance(label, str) or not _LABEL_PATTERN.match(label):
            raise ValueError(
                f"sheet {sheet_id!r} node {node_id!r} has unsafe GenericItem label {label!r}; "
                f"expected {_LABEL_PATTERN.pattern!r}"
            )
    return tuple(chain)


# --- relationship rows: hierarchy, topology, resolver links -------------------------------


def all_relationship_rows(
    corpus_id: str,
    sheets: Sequence[SheetGraph],
    resolution: Resolution,
    asserted_by: Literal["resolver", "oracle"],
) -> list[RelationshipRow]:
    """Every relationship row: hierarchy and topology per sheet, plus the resolver's links."""
    rows: list[RelationshipRow] = []
    for sheet in sheets:
        sheet_uid = uid(corpus_id, sheet.sheet_id)
        rows.append(_has_sheet_row(corpus_id, sheet_uid))
        rows += _is_drawn_on_rows(corpus_id, sheet, sheet_uid)
        rows += _topology_rows(corpus_id, sheet)
    rows += _located_in_rows(corpus_id, sheets)
    rows += _continues_as_rows(corpus_id, resolution, asserted_by)
    rows += _same_tagged_item_as_rows(corpus_id, resolution, asserted_by)
    return rows


def _located_in_rows(corpus_id: str, sheets: Sequence[SheetGraph]) -> list[RelationshipRow]:
    """`is_located_in`: occurrence -> its unit, and unit -> its plant (ADR-0026).

    Only occurrences that carry a `unit_id` get one. A reference occurrence or a
    connector stub shows none on the drawing, so it reaches its unit through
    `same_tagged_item_as` instead.
    """
    relation = schema.Relation.IS_LOCATED_IN.value
    rows = []
    plants_of_unit: dict[str, set[str]] = {}
    for sheet in sheets:
        for node_id, attrs in sheet.graph.nodes(data=True):
            unit_id = attrs.get("unit_id")
            if not isinstance(unit_id, str):
                continue
            source = uid(corpus_id, f"{sheet.sheet_id}:{node_id}")
            rows.append(
                RelationshipRow(relation, source, plant_section_uid(corpus_id, unit_id), {})
            )
            plant_id = attrs.get("plant_id")
            if isinstance(plant_id, str):
                plants_of_unit.setdefault(unit_id, set()).add(plant_id)
    return rows + _section_in_plant_rows(corpus_id, plants_of_unit)


def _section_in_plant_rows(
    corpus_id: str, plants_of_unit: Mapping[str, set[str]]
) -> list[RelationshipRow]:
    relation = schema.Relation.IS_LOCATED_IN.value
    rows = []
    for unit_id, plant_ids in sorted(plants_of_unit.items()):
        if len(plant_ids) != 1:
            raise ValueError(
                f"unit {unit_id!r} is drawn with plant ids {sorted(plant_ids)}; "
                "expected exactly one"
            )
        (plant_id,) = plant_ids
        source = plant_section_uid(corpus_id, unit_id)
        rows.append(RelationshipRow(relation, source, process_plant_uid(corpus_id, plant_id), {}))
    return rows


def _has_sheet_row(corpus_id: str, sheet_uid: str) -> RelationshipRow:
    corpus_uid = uid(corpus_id, _CORPUS_LOCAL_KEY)
    return RelationshipRow(schema.Relation.HAS_SHEET.value, corpus_uid, sheet_uid, {})


def _is_drawn_on_rows(corpus_id: str, sheet: SheetGraph, sheet_uid: str) -> list[RelationshipRow]:
    return [
        RelationshipRow(
            schema.Relation.IS_DRAWN_ON.value,
            uid(corpus_id, f"{sheet.sheet_id}:{node_id}"),
            sheet_uid,
            {},
        )
        for node_id in sheet.graph.nodes
    ]


def _topology_rows(corpus_id: str, sheet: SheetGraph) -> list[RelationshipRow]:
    """One row per edge already on the sheet — the edge's own `relation` becomes the type."""
    rows = []
    for source, target, attrs in sheet.graph.edges(data=True):
        rel_type = attrs.get("relation")
        if rel_type not in _TOPOLOGY_RELATION_VALUES:
            raise ValueError(
                f"sheet {sheet.sheet_id!r} edge {(source, target)!r} has relation {rel_type!r}, "
                f"expected one of {sorted(_TOPOLOGY_RELATION_VALUES)}"
            )
        props = _drop_none({key: value for key, value in attrs.items() if key != "relation"})
        rows.append(
            RelationshipRow(
                rel_type,
                uid(corpus_id, f"{sheet.sheet_id}:{source}"),
                uid(corpus_id, f"{sheet.sheet_id}:{target}"),
                props,
            )
        )
    return rows


def _continues_as_rows(
    corpus_id: str, resolution: Resolution, asserted_by: Literal["resolver", "oracle"]
) -> list[RelationshipRow]:
    """One row per paired off-page connector: outgoing stub -> incoming stub (§5.2)."""
    return [
        RelationshipRow(
            schema.Relation.CONTINUES_AS.value,
            uid(corpus_id, pair.from_key),
            uid(corpus_id, pair.to_key),
            {"asserted_by": asserted_by, "match_rule": pair.match_rule.value},
        )
        for pair in resolution.connector_pairs
    ]


def _same_tagged_item_as_rows(
    corpus_id: str, resolution: Resolution, asserted_by: Literal["resolver", "oracle"]
) -> list[RelationshipRow]:
    """One row per reference occurrence, pointing at its identity group's home (§5.3)."""
    return [
        RelationshipRow(
            schema.Relation.SAME_TAGGED_ITEM_AS.value,
            uid(corpus_id, reference),
            uid(corpus_id, group.home),
            {"asserted_by": asserted_by},
        )
        for group in resolution.identity_groups
        for reference in group.references
    ]


def _drop_none(props: dict[str, object]) -> dict[str, object]:
    """Cypher's `SET n = row.props` would otherwise write an explicit null property."""
    return {key: value for key, value in props.items() if value is not None}
