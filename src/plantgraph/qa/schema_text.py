"""The schema description CypherRAG shows the Cypher-writing LLM (`qa-system.md` §7).

A **schema text** tells the LLM which node labels, relationship types and
properties exist in the database, so it can write a query that matches. The
lists are generated from the corpus's own `LoadPlan` (what was actually
loaded) and checked against `graph/schema.py` (what is allowed to exist), so
the text cannot drift from the code. The one fixed paragraph explains the
shape of the store: sheets, off-page connectors and the links between them.

Bookkeeping the store adds for its own use (`CorpusNode`, `uid`, `corpus_id`)
is never mentioned: it is noise to the model and not part of the drawing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from plantgraph.graph import schema
from plantgraph.store.neo4j_plan import LoadPlan

_BOOKKEEPING_LABEL = "CorpusNode"

#: A label a `GenericItem` brings from an imported file's own class chain (ADR-0016).
_GENERIC_LABEL = re.compile(r"^[A-Z][A-Za-z0-9]*$")

#: Written against the built store shape (`qa-system.md` §2.1; ADR-0026 unit nodes,
#: ADR-0027 loop numbers on signal connectors, ADR-0028 identity links).
_STRUCTURE_PARAGRAPH = """\
How the graph is organised:
- (:DrawingSet)-[:has_sheet]->(:Sheet {sheet_id}). A sheet is one page of the drawing.
- Every drawn item (equipment, valve, instrument function, off-page connector) is one node and
  has one -[:is_drawn_on]-> (:Sheet). Items have no sheet_id property: the sheet of an item is
  the Sheet it is_drawn_on.
- Material flows along -[:send_to]->: (a)-[:send_to]->(b) means flow runs from a to b.
  Instrument wiring uses send_signal_to, control and measured_by.
- A pipe or signal line that leaves a sheet ends in an off-page connector node
  (FlowOutPipeOffPageConnector or FlowOutSignalOffPageConnector). That node
  -[:continues_as]-> the FlowIn...OffPageConnector on the other sheet, from which the line
  continues. Going from one sheet to the next therefore takes three relationships:
  (item)-[:send_to]->(FlowOut connector)-[:continues_as]->(FlowIn connector)
  -[:send_to]->(next item).
  Connector nodes have no tag. Signal connectors carry loop_tag, the number of their control loop.
- tag is the identifier printed next to an item, for example P-101. piping_component_name is the
  printed name of an imported valve.
- (:PlantSection {unit_id}) is one unit, a group of equipment operated together. An item that
  shows a unit has (item)-[:is_located_in]->(:PlantSection), and each PlantSection
  -[:is_located_in]->(:ProcessPlant {plant_id}). unit_id is also a property of those items.
  Connectors and repeated drawings carry no unit_id.
- (repeat)-[:same_tagged_item_as]->(main) links a repeated drawing of an item on another sheet
  to the main drawing of the same item.
- A node has several labels, a specific class and the general ones above it, so MATCH on a
  general label such as :Equipment to cover a whole family."""


def _known_labels() -> frozenset[str]:
    return frozenset(label for spec in schema.CLASS_SPECS.values() for label in spec.labels)


def _check_labels(labels: Iterable[str]) -> None:
    known = _known_labels()
    for label in labels:
        if label not in known and not _GENERIC_LABEL.match(label):
            raise ValueError(
                f"label {label!r} is not in graph/schema.py and does not match "
                f"{_GENERIC_LABEL.pattern!r}; refusing to describe it to the LLM"
            )


def _check_relationship_types(types: Iterable[str]) -> None:
    known = {relation.value for relation in schema.Relation}
    for relationship_type in types:
        if relationship_type not in known:
            raise ValueError(
                f"relationship type {relationship_type!r} is not in schema.Relation; "
                f"expected one of {sorted(known)}"
            )


def schema_labels(plan: LoadPlan) -> list[str]:
    """This corpus's node labels, sorted, without the bookkeeping label."""
    labels = sorted(label for label in plan.expected_node_labels if label != _BOOKKEEPING_LABEL)
    _check_labels(labels)
    return labels


def schema_relationship_types(plan: LoadPlan) -> list[str]:
    """This corpus's relationship types, sorted."""
    types = sorted(plan.expected_relationship_types)
    _check_relationship_types(types)
    return types


def build_schema_text(plan: LoadPlan) -> str:
    """The schema text for the corpus `plan` describes.

    Raises:
        ValueError: the plan holds a label or relationship type the schema does not allow.
    """
    node_properties = sorted(schema.VISIBLE_NODE_PROPERTIES)
    # `relation` is the relationship's type, not a stored property
    edge_properties = sorted(schema.VISIBLE_EDGE_PROPERTIES - {"relation"})
    return "\n".join(
        [
            "Node labels: " + ", ".join(schema_labels(plan)),
            "Relationship types: " + ", ".join(schema_relationship_types(plan)),
            "Item properties (present only when the drawing shows them): "
            + ", ".join(node_properties),
            "Relationship properties: " + ", ".join(edge_properties),
            "Sheet nodes have sheet_id; DrawingSet nodes have drawing_set_id.",
            "",
            _STRUCTURE_PARAGRAPH,
        ]
    )
