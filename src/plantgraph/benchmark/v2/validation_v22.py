"""Schema validation of a v2.2 plant: the frozen validator, minus the tags a document leaves off.

The frozen `graph.validation.validate_plant_graph` requires a tag on every node that is not an
actuator. A v2.2 document may print **no tag on its manual valves** (Toghraei p.113; a *manual
valve* is a gate, ball, globe or check valve with no actuator), so on such a plant the frozen
validator reports one "missing tag" per manual valve. This wrapper removes exactly those and keeps
every other violation: a control valve, a safety device or an instrument that loses its tag still
fails (design 17.15 S8).

Which valves are exempt comes from the generation record alone: the documents it marks untagged,
and the units each document holds.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.documents import document_of_train
from plantgraph.benchmark.v2.record_v22 import GenerationRecordV22
from plantgraph.benchmark.v2.vocabulary import MANUAL_VALVE_CLASSES
from plantgraph.graph.schema import Relation
from plantgraph.graph.validation import SchemaViolation, validate_plant_graph

_MISSING_TAG_DETAIL = "missing required property 'tag'"


def untagged_manual_valves(plant: nx.DiGraph[str], record: GenerationRecordV22) -> frozenset[str]:
    """The manual and check valves of the documents the record marks untagged."""
    untagged_units = _units_of_untagged_documents(record)
    return frozenset(
        node_id
        for node_id, data in plant.nodes(data=True)
        if _unit_number(data) in untagged_units and _is_manual_valve(plant, node_id)
    )


def validate_plant_graph_v22(
    plant: nx.DiGraph[str], record: GenerationRecordV22
) -> list[SchemaViolation]:
    """`validate_plant_graph` without the "missing tag" violations of untagged manual valves."""
    exempt = untagged_manual_valves(plant, record)
    return [v for v in validate_plant_graph(plant) if not _is_exempt(v, exempt)]


def _is_exempt(violation: SchemaViolation, exempt: frozenset[str]) -> bool:
    return (
        violation.kind == "missing_property"
        and violation.detail == _MISSING_TAG_DETAIL
        and violation.subject in exempt
    )


def _units_of_untagged_documents(record: GenerationRecordV22) -> frozenset[int]:
    """Unit numbers whose document leaves its manual valves untagged."""
    per_document = GeneratorConfigV22.model_validate_json(record.generator_config).handbook
    untagged_documents = {d.document_no for d in record.documents if d.manual_valves_untagged}
    return frozenset(
        unit.unit_no
        for unit in record.units
        if document_of_train(unit.train_no, per_document.trains_per_document) in untagged_documents
    )


def _unit_number(data: dict[str, object]) -> int | None:
    unit_id = data.get("unit_id")
    return int(str(unit_id)) if unit_id is not None else None


def _is_manual_valve(plant: nx.DiGraph[str], node_id: str) -> bool:
    """A manual valve class with no actuator driving it (an actuator edge makes it automatic)."""
    if plant.nodes[node_id]["node_class"] not in MANUAL_VALVE_CLASSES:
        return False
    in_edges = plant.in_edges(node_id, data=True)
    return not any(data["relation"] == Relation.CONTROL.value for *_, data in in_edges)
