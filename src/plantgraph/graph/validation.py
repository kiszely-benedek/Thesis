"""Check whether a graph conforms to the schema fixed in `schema.py`.

There are two entry points, because the generator's and the splitter's output
follow different rules (`plant-generator.md` §4.5): a full plant graph has no
off-page connector stubs and every node carries a complete set of attributes,
while a sheet graph allows both.
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
    """A violation found by schema validation: what kind, on which node/edge, what's wrong."""

    kind: SchemaViolationKind
    subject: str
    detail: str


_PLANT_REQUIRED_PROPERTIES: tuple[str, ...] = ("tag", "plant_id", "unit_id")
_CONNECTOR_REQUIRED_PROPERTIES: tuple[str, ...] = ("connector_number", "referenced_drawing_number")


def validate_plant_graph(plant: nx.DiGraph[str]) -> list[SchemaViolation]:
    """Validate the generator's output: generator classes, required properties, unique tags.

    A connector node (an off-page connector stub) is an error here: only the
    splitter places those, on sheets — a full plant graph has no room for them.
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
    """Node validation in the plant-graph context: known class, required fields, unique tag."""
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
    """Validate one of the splitter's sheets: generator, connector, and `GenericItem` all allowed.

    Reference occurrences (identity-based cross-referencing, `plant-generator.md`
    §4.4) carry only `tag` and `node_class`, so `plant_id`/`unit_id` are not
    required here — those live only on the home occurrence. `IMPORTABLE_CLASSES`
    also includes `GenericItem` (ADR-0016): otherwise a real Proteus import's
    sheet would reject every fallback node.
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
    """Node validation in the sheet-graph context.

    A connector node has its own required fields (§4.4).
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
    """Flag a node_class that is unknown, or not allowed in this kind of graph."""
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
    """List the required properties that are missing (None or absent)."""
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
    """Flag a tag already seen — a missing tag is already reported by _check_required_properties."""
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
    """Validate an edge's relation and endpoint classes against the §4.3 table."""
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
