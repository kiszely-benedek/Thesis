"""The graph schema shared by the plant generator and the splitter.

Terms, because the code is about an engineering domain the reader may not know:

- **P&ID**: a piping and instrumentation diagram — the technical drawing of a
  plant's pipes and instruments.
- **topology layer**: what the generator emits and the splitter cuts up — just
  "what connects to what, over which kind of edge" (`send_to`, `control`,
  ...). This is this module's subject.
- **structure layer**: containment, sheets, cross-sheet resolution
  (`is_located_in`, `has_sheet`, ...). Produced by the graph loader in Neo4j;
  **never** present in the splitter's input graph (see design section 4.1: a
  "unit contains its items" edge would break the splitter's
  neighbourhood-based clustering).
- **node_class**: a pyDEXPI class name (e.g. `CentrifugalPump`), together with
  its curated ancestor-class chain as a Neo4j label (`labels_for`).

This module holds the valid node and edge types and their required properties
— the `validate_plant_graph` and `validate_sheet_graph` functions built on top
of them live in the sibling module, `plantgraph.graph.validation` (split out
because of the 400-line file limit; the design still describes this as one
file). Neither this nor the sibling module imports `pydexpi` or
`plantgraph.benchmark` (`plant-generator.md` §4.5): the latter builds on these
modules, never the other way round.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class NodeCategory(str, Enum):
    """Which functional group a node_class belongs to (a column of the §4.2 table)."""

    EQUIPMENT = "equipment"
    PIPING = "piping"
    INSTRUMENTATION = "instrumentation"
    CONNECTOR = "connector"
    STRUCTURE = "structure"
    #: the `GenericItem` fallback's category, when pyDEXPI's ancestor chain has no curated root
    #: (ADR-0016, kg-construction.md §3.1 "Label cut-off")
    OTHER = "other"


class NodeClass(str, Enum):
    """Every node class in the schema — a curated name chain, verified against pyDEXPI 1.2.0.

    12 classes are produced by the generator, 4 stub classes by the splitter
    (when it cuts an edge, it places an off-page connector stub on both
    sheets), and 4 structural classes exist only in the graph store
    (`plant-generator.md` §4.2).
    """

    CENTRIFUGAL_PUMP = "CentrifugalPump"
    COMPRESSOR = "Compressor"
    TANK = "Tank"
    PRESSURE_VESSEL = "PressureVessel"
    PROCESS_COLUMN = "ProcessColumn"
    HEAT_EXCHANGER = "HeatExchanger"
    GLOBE_VALVE = "GlobeValve"
    BALL_VALVE = "BallValve"
    CHECK_VALVE = "CheckValve"
    PROCESS_SIGNAL_GENERATING_FUNCTION = "ProcessSignalGeneratingFunction"
    PROCESS_INSTRUMENTATION_FUNCTION = "ProcessInstrumentationFunction"
    ACTUATING_FUNCTION = "ActuatingFunction"
    FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR = "FlowOutPipeOffPageConnector"
    FLOW_IN_PIPE_OFF_PAGE_CONNECTOR = "FlowInPipeOffPageConnector"
    FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR = "FlowOutSignalOffPageConnector"
    FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR = "FlowInSignalOffPageConnector"
    PROCESS_PLANT = "ProcessPlant"
    PLANT_SECTION = "PlantSection"
    DRAWING_SET = "DrawingSet"
    SHEET = "Sheet"
    #: fallback for a real file's pyDEXPI class the schema has not curated (ADR-0016)
    GENERIC_ITEM = "GenericItem"


class Relation(str, Enum):
    """Every edge type in the schema: 4 topology relations and 5 structural relations (§4.3)."""

    SEND_TO = "send_to"
    SEND_SIGNAL_TO = "send_signal_to"
    CONTROL = "control"
    MEASURED_BY = "measured_by"
    IS_LOCATED_IN = "is_located_in"
    HAS_SHEET = "has_sheet"
    IS_DRAWN_ON = "is_drawn_on"
    CONTINUES_AS = "continues_as"
    SAME_TAGGED_ITEM_AS = "same_tagged_item_as"
    #: a `GenericItem` fallback's edge relation, for a pyDEXPI edge label the schema does not
    #: curate — kept, never dropped (ADR-0016)
    RELATED_TO = "related_to"


class ClassSpec(BaseModel):
    """A node_class's Neo4j label chain, category, and tag prefix — one row of the §4.2 table."""

    model_config = ConfigDict(frozen=True)

    labels: tuple[str, ...]
    category: NodeCategory
    tag_prefix: str | None = None


CLASS_SPECS: dict[NodeClass, ClassSpec] = {
    NodeClass.CENTRIFUGAL_PUMP: ClassSpec(
        labels=("CentrifugalPump", "Pump", "Equipment", "TaggedPlantItem"),
        category=NodeCategory.EQUIPMENT,
        tag_prefix="P",
    ),
    NodeClass.COMPRESSOR: ClassSpec(
        labels=("Compressor", "Equipment", "TaggedPlantItem"),
        category=NodeCategory.EQUIPMENT,
        tag_prefix="C",
    ),
    NodeClass.TANK: ClassSpec(
        labels=("Tank", "Vessel", "Equipment", "TaggedPlantItem"),
        category=NodeCategory.EQUIPMENT,
        tag_prefix="TK",
    ),
    NodeClass.PRESSURE_VESSEL: ClassSpec(
        labels=("PressureVessel", "Vessel", "Equipment", "TaggedPlantItem"),
        category=NodeCategory.EQUIPMENT,
        tag_prefix="V",
    ),
    NodeClass.PROCESS_COLUMN: ClassSpec(
        labels=("ProcessColumn", "Equipment", "TaggedPlantItem"),
        category=NodeCategory.EQUIPMENT,
        tag_prefix="T",
    ),
    NodeClass.HEAT_EXCHANGER: ClassSpec(
        labels=("HeatExchanger", "Equipment", "TaggedPlantItem"),
        category=NodeCategory.EQUIPMENT,
        tag_prefix="E",
    ),
    NodeClass.GLOBE_VALVE: ClassSpec(
        labels=("GlobeValve", "OperatedValve", "PipingComponent"),
        category=NodeCategory.PIPING,
        tag_prefix="GV",
    ),
    NodeClass.BALL_VALVE: ClassSpec(
        labels=("BallValve", "OperatedValve", "PipingComponent"),
        category=NodeCategory.PIPING,
        tag_prefix="BV",
    ),
    NodeClass.CHECK_VALVE: ClassSpec(
        labels=("CheckValve", "PipingComponent"),
        category=NodeCategory.PIPING,
        tag_prefix="CHV",
    ),
    NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION: ClassSpec(
        labels=("ProcessSignalGeneratingFunction",),
        category=NodeCategory.INSTRUMENTATION,
        tag_prefix="{var}T",
    ),
    NodeClass.PROCESS_INSTRUMENTATION_FUNCTION: ClassSpec(
        labels=("ProcessInstrumentationFunction",),
        category=NodeCategory.INSTRUMENTATION,
        tag_prefix="{var}IC",
    ),
    NodeClass.ACTUATING_FUNCTION: ClassSpec(
        labels=("ActuatingFunction",),
        category=NodeCategory.INSTRUMENTATION,
        tag_prefix="{var}V",
    ),
    NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR: ClassSpec(
        labels=("FlowOutPipeOffPageConnector", "PipeOffPageConnector"),
        category=NodeCategory.CONNECTOR,
    ),
    NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR: ClassSpec(
        labels=("FlowInPipeOffPageConnector", "PipeOffPageConnector"),
        category=NodeCategory.CONNECTOR,
    ),
    NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR: ClassSpec(
        labels=("FlowOutSignalOffPageConnector", "SignalOffPageConnector"),
        category=NodeCategory.CONNECTOR,
    ),
    NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR: ClassSpec(
        labels=("FlowInSignalOffPageConnector", "SignalOffPageConnector"),
        category=NodeCategory.CONNECTOR,
    ),
    NodeClass.PROCESS_PLANT: ClassSpec(labels=("ProcessPlant",), category=NodeCategory.STRUCTURE),
    NodeClass.PLANT_SECTION: ClassSpec(labels=("PlantSection",), category=NodeCategory.STRUCTURE),
    NodeClass.DRAWING_SET: ClassSpec(labels=("DrawingSet",), category=NodeCategory.STRUCTURE),
    NodeClass.SHEET: ClassSpec(labels=("Sheet",), category=NodeCategory.STRUCTURE),
    # the per-instance ancestor chain (`dexpi_labels`) is a node property, not this
    # class-level entry — the latter only gives the Neo4j label (`adapters/pydexpi_generic.py`)
    NodeClass.GENERIC_ITEM: ClassSpec(labels=("GenericItem",), category=NodeCategory.OTHER),
}


def _classes_in_category(category: NodeCategory) -> frozenset[str]:
    """Filter a category's node_class names out of CLASS_SPECS.

    A single source, not a duplicated list.
    """
    return frozenset(
        node_class.value for node_class, spec in CLASS_SPECS.items() if spec.category is category
    )


EQUIPMENT_CLASSES: frozenset[str] = _classes_in_category(NodeCategory.EQUIPMENT)
VALVE_CLASSES: frozenset[str] = _classes_in_category(NodeCategory.PIPING)
OPERATED_VALVE_CLASSES: frozenset[str] = frozenset(
    {NodeClass.GLOBE_VALVE.value, NodeClass.BALL_VALVE.value}
)
CONNECTOR_CLASSES: frozenset[str] = _classes_in_category(NodeCategory.CONNECTOR)

# produced only by the generator (equipment + piping component + instrumentation) —
# this is the plant graph's "known class" set, without the connector and structural classes.
# Not among §4.5's named constants, but validation.py needs it —
# so it stays public, not underscored: two modules share it because of the file limit.
GENERATOR_CLASSES: frozenset[str] = (
    EQUIPMENT_CLASSES | VALVE_CLASSES | _classes_in_category(NodeCategory.INSTRUMENTATION)
)
KNOWN_CLASSES: frozenset[str] = frozenset(node_class.value for node_class in NodeClass)

# what a Proteus importer may accept as a node class: the generator's classes, the
# stub classes, plus the fallback with no curated ancestor chain (ADR-0016, §3.1).
# GENERATOR_CLASSES itself is not extended — the generator never produces an unknown class.
IMPORTABLE_CLASSES: frozenset[str] = (
    GENERATOR_CLASSES | CONNECTOR_CLASSES | {NodeClass.GENERIC_ITEM.value}
)

#: `GenericItem` is allowed at both ends of every topology relation in the schema: validation
#: cannot know the fallback's semantics — that is promotion's job (ADR-0016 rule 4).
_GENERIC_ITEM: frozenset[str] = frozenset({NodeClass.GENERIC_ITEM.value})

RELATION_ENDPOINTS: dict[Relation, tuple[frozenset[str], frozenset[str]]] = {
    Relation.SEND_TO: (
        EQUIPMENT_CLASSES
        | VALVE_CLASSES
        | _GENERIC_ITEM
        | {NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value},
        EQUIPMENT_CLASSES
        | VALVE_CLASSES
        | _GENERIC_ITEM
        | {NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value},
    ),
    Relation.SEND_SIGNAL_TO: (
        frozenset(
            {
                NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
                NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
                NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        )
        | _GENERIC_ITEM,
        frozenset(
            {
                NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
                NodeClass.ACTUATING_FUNCTION.value,
                NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        )
        | _GENERIC_ITEM,
    ),
    Relation.CONTROL: (
        frozenset(
            {NodeClass.ACTUATING_FUNCTION.value, NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value}
        )
        | _GENERIC_ITEM,
        frozenset(
            {
                NodeClass.GLOBE_VALVE.value,
                NodeClass.BALL_VALVE.value,
                NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        )
        | _GENERIC_ITEM,
    ),
    Relation.MEASURED_BY: (
        EQUIPMENT_CLASSES | {NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value} | _GENERIC_ITEM,
        frozenset(
            {
                NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
                NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        )
        | _GENERIC_ITEM,
    ),
    # the fallback's edge relation: any importable class may sit at either endpoint
    # (ADR-0016 rule 2) — the schema doesn't know its meaning, it only preserves it
    Relation.RELATED_TO: (IMPORTABLE_CLASSES, IMPORTABLE_CLASSES),
}

# structural relations (is_located_in, has_sheet, ...) have no endpoint set here:
# they never appear as an edge in the generator's/splitter's graph (see the module docstring)
TOPOLOGY_RELATIONS: frozenset[Relation] = frozenset(RELATION_ENDPOINTS)

VISIBLE_NODE_PROPERTIES: frozenset[str] = frozenset(
    {
        "node_class",
        "tag",
        "plant_id",
        "unit_id",
        "loop_tag",
        "measured_variable",
        "connector_number",
        "referenced_drawing_number",
        "referenced_connector_number",
        "line_number",
        "fluid_code",
        # the fallback's own meaning: which pyDEXPI class/labels the drawing showed (ADR-0016)
        "dexpi_class",
        "category",
        "dexpi_labels",
        # a part's printed name, e.g. valve "66KL21" — an identifier, not datasheet data;
        # equipment/datasheet data is out of scope — not part of this thesis (ADR-0021)
        "piping_component_name",
    }
)
VISIBLE_EDGE_PROPERTIES: frozenset[str] = frozenset(
    {"relation", "line_number", "fluid_code", "dexpi_label"}
)


def labels_for(node_class: str) -> tuple[str, ...]:
    """A node_class's Neo4j label chain, together with its ancestor classes (§4.2).

    Raises:
        ValueError: if node_class is not in the schema.
    """
    try:
        return CLASS_SPECS[NodeClass(node_class)].labels
    except ValueError:
        raise ValueError(
            f"unknown node_class {node_class!r}; expected one of {sorted(KNOWN_CLASSES)}"
        ) from None
