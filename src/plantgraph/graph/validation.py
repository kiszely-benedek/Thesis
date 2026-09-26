"""Ellenőrzi, hogy egy gráf megfelel-e a `schema.py`-ban rögzített sémának.

Két belépési pont van, mert a generátor és a splitter kimenete más-más
szabályt követ (`plant-generator.md` §4.5): egy teljes üzemgráfban nincs
off-page connector csonk és minden csomópont teljes attribútumkészlettel
rendelkezik, egy lap-gráfban viszont mindkettő megengedett.
"""

from __future__ import annotations

from typing import Literal

import networkx as nx
from pydantic import BaseModel

from plantgraph.graph.schema import (
    CONNECTOR_CLASSES,
    GENERATOR_CLASSES,
    IMPORTABLE_CLASSES,
    KNOWN_CLASSES,
    RELATION_ENDPOINTS,
    TOPOLOGY_RELATIONS,
    Relation,
)

SchemaViolationKind = Literal[
    "unknown_class", "missing_property", "unknown_relation", "bad_endpoint", "duplicate_tag"
]


class SchemaViolation(BaseModel):
    """Egy séma-ellenőrzés talált hibája: milyen fajta, melyik csomóponton/élen, mi a baj."""

    kind: SchemaViolationKind
    subject: str
    detail: str


_PLANT_REQUIRED_PROPERTIES: tuple[str, ...] = ("tag", "plant_id", "unit_id")
_CONNECTOR_REQUIRED_PROPERTIES: tuple[str, ...] = ("connector_number", "referenced_drawing_number")


def validate_plant_graph(plant: nx.DiGraph[str]) -> list[SchemaViolation]:
    """Ellenőrzi a generátor kimenetét: generátor-osztályok, kötelező tulajdonságok, egyedi tag-ek.

    Connector-csomópont (off-page connector csonk) itt hiba: azokat csak a
    splitter tesz a lapokra, egy teljes üzemgráfban nincs helyük.
    """
    violations: list[SchemaViolation] = []
    tags_seen: dict[str, str] = {}
    for node_id in sorted(plant.nodes):
        violations.extend(_validate_plant_node(node_id, plant.nodes[node_id], tags_seen))
    for source, target in sorted(plant.edges):
        violations.extend(_validate_edge(plant, source, target))
    return violations


def _validate_plant_node(
    node_id: str, attrs: dict[str, object], tags_seen: dict[str, str]
) -> list[SchemaViolation]:
    """Csomópont-ellenőrzés plant graph kontextusban: ismert osztály, kötelező mezők, egyedi tag."""
    node_class = attrs.get("node_class")
    class_violation = _check_node_class(node_id, node_class, allowed=GENERATOR_CLASSES)
    if class_violation is not None:
        return [class_violation]
    violations = _check_required_properties(node_id, attrs, _PLANT_REQUIRED_PROPERTIES)
    duplicate = _check_duplicate_tag(node_id, attrs.get("tag"), tags_seen)
    if duplicate is not None:
        violations.append(duplicate)
    return violations


def validate_sheet_graph(sheet: nx.DiGraph[str]) -> list[SchemaViolation]:
    """Ellenőrzi a splitter egy lapját: generátor-, connector- és `GenericItem` is megengedett.

    A reference-előfordulások (azonosság-alapú kereszthivatkozás,
    `plant-generator.md` §4.4) csak `tag`-et és `node_class`-t hordoznak, ezért
    itt nem várjuk el a `plant_id`/`unit_id`-t — az csak a home előforduláson van.
    `IMPORTABLE_CLASSES` a `GenericItem`-et is tartalmazza (ADR-0016): egy valódi
    Proteus-import lapja máskülönben minden fallback-csomópontot elutasítana.
    """
    violations: list[SchemaViolation] = []
    tags_seen: dict[str, str] = {}
    allowed = IMPORTABLE_CLASSES
    for node_id in sorted(sheet.nodes):
        violations.extend(_validate_sheet_node(node_id, sheet.nodes[node_id], allowed, tags_seen))
    for source, target in sorted(sheet.edges):
        violations.extend(_validate_edge(sheet, source, target))
    return violations


def _validate_sheet_node(
    node_id: str,
    attrs: dict[str, object],
    allowed_classes: frozenset[str],
    tags_seen: dict[str, str],
) -> list[SchemaViolation]:
    """Csomópont-ellenőrzés lap-gráf kontextusban.

    A connector-csomópontnak saját kötelező mezői vannak (§4.4).
    """
    node_class = attrs.get("node_class")
    class_violation = _check_node_class(node_id, node_class, allowed=allowed_classes)
    if class_violation is not None:
        return [class_violation]
    required = _CONNECTOR_REQUIRED_PROPERTIES if node_class in CONNECTOR_CLASSES else ("tag",)
    violations = _check_required_properties(node_id, attrs, required)
    duplicate = _check_duplicate_tag(node_id, attrs.get("tag"), tags_seen)
    if duplicate is not None:
        violations.append(duplicate)
    return violations


def _check_node_class(
    subject: str, node_class: object, allowed: frozenset[str]
) -> SchemaViolation | None:
    """Ismeretlen vagy ebben a gráf-fajtában meg nem engedett node_class-t jelez."""
    if node_class not in KNOWN_CLASSES:
        return SchemaViolation(
            kind="unknown_class",
            subject=subject,
            detail=f"node_class {node_class!r} is not part of the schema",
        )
    if node_class not in allowed:
        return SchemaViolation(
            kind="unknown_class",
            subject=subject,
            detail=f"node_class {node_class!r} is not allowed in this graph",
        )
    return None


def _check_required_properties(
    subject: str, attrs: dict[str, object], required: tuple[str, ...]
) -> list[SchemaViolation]:
    """A hiányzó (None vagy nincs jelen) kötelező tulajdonságokat sorolja fel."""
    return [
        SchemaViolation(
            kind="missing_property", subject=subject, detail=f"missing required property {name!r}"
        )
        for name in required
        if attrs.get(name) is None
    ]


def _check_duplicate_tag(
    subject: str, tag: object, tags_seen: dict[str, str]
) -> SchemaViolation | None:
    """Már látott tag-et jelez — a hiányzó tag-et a _check_required_properties már jelenti."""
    if not isinstance(tag, str):
        return None
    first_seen = tags_seen.get(tag)
    if first_seen is not None:
        return SchemaViolation(
            kind="duplicate_tag",
            subject=subject,
            detail=f"tag {tag!r} already used by {first_seen!r}",
        )
    tags_seen[tag] = subject
    return None


def _validate_edge(plant: nx.DiGraph[str], source: str, target: str) -> list[SchemaViolation]:
    """Egy él relációját és végpont-osztályait ellenőrzi a §4.3 tábla szerint."""
    edge_id = f"{source}->{target}"
    relation = plant.edges[source, target].get("relation")
    if relation not in {member.value for member in TOPOLOGY_RELATIONS}:
        return [
            SchemaViolation(
                kind="unknown_relation",
                subject=edge_id,
                detail=f"edge relation {relation!r} is not a topology relation",
            )
        ]
    allowed_from, allowed_to = RELATION_ENDPOINTS[Relation(relation)]
    source_class = plant.nodes[source].get("node_class")
    target_class = plant.nodes[target].get("node_class")

    violations: list[SchemaViolation] = []
    if source_class not in allowed_from:
        violations.append(
            SchemaViolation(
                kind="bad_endpoint",
                subject=edge_id,
                detail=f"relation {relation!r} may not start at node_class {source_class!r}",
            )
        )
    if target_class not in allowed_to:
        violations.append(
            SchemaViolation(
                kind="bad_endpoint",
                subject=edge_id,
                detail=f"relation {relation!r} may not end at node_class {target_class!r}",
            )
        )
    return violations
