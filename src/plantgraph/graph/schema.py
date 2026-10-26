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
  its ancestor-class chain as a Neo4j label (`labels_for`). The set of classes, and each one's
  chain, category and piping kind, come from the generated table `schema_vocabulary.py`
  (ADR-0058); the node types themselves live in `schema_classes.py`.

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

from plantgraph.graph.schema_classes import (
    ClassSpec,
    NodeCategory,
    NodeClass,
    PipingKind,
    VocabularyRow,
)
from plantgraph.graph.schema_vocabulary import VOCABULARY

# Re-exported: callers import these from `plantgraph.graph.schema`, whichever file defines them.
__all__ = ["ClassSpec", "NodeCategory", "NodeClass", "PipingKind", "VocabularyRow"]


class Relation(str, Enum):
    """Every edge type in the schema: topology, the `related_to` fallback, and structural."""

    SEND_TO = "send_to"
    SEND_SIGNAL_TO = "send_signal_to"
    CONTROL = "control"
    MEASURED_BY = "measured_by"
    #: a vessel or heat exchanger -> its `Agitator` (the stirrer inside it); the only place pyDEXPI
    #: links one equipment item to another (ADR-0058)
    HAS_AGITATOR = "has_agitator"
    IS_LOCATED_IN = "is_located_in"
    HAS_SHEET = "has_sheet"
    IS_DRAWN_ON = "is_drawn_on"
    CONTINUES_AS = "continues_as"
    SAME_TAGGED_ITEM_AS = "same_tagged_item_as"
    #: a `GenericItem` fallback's edge relation, for a pyDEXPI edge label the schema does not
    #: curate — kept, never dropped (ADR-0016)
    RELATED_TO = "related_to"
    #: merged plant item -> each drawn occurrence of it; only in the store's plant layer
    #: (ADR-0036), structural, so it can never appear in a sheet
    DRAWN_AS = "drawn_as"


def _structure(name: NodeClass) -> ClassSpec:
    return ClassSpec(labels=(name.value,), category=NodeCategory.STRUCTURE)


# The derived rows, then the five classes the rule does not cover: the four structural ones, and
# `GenericItem`. Its per-instance ancestor chain (`dexpi_labels`) is a node property, not this
# class-level entry; the latter only gives the Neo4j label (`adapters/pydexpi_generic.py`).
CLASS_SPECS: dict[NodeClass, ClassSpec] = {
    **{NodeClass(row.name): row for row in VOCABULARY},
    NodeClass.PROCESS_PLANT: _structure(NodeClass.PROCESS_PLANT),
    NodeClass.PLANT_SECTION: _structure(NodeClass.PLANT_SECTION),
    NodeClass.DRAWING_SET: _structure(NodeClass.DRAWING_SET),
    NodeClass.SHEET: _structure(NodeClass.SHEET),
    NodeClass.GENERIC_ITEM: ClassSpec(labels=("GenericItem",), category=NodeCategory.OTHER),
}


def _classes_in_category(category: NodeCategory) -> frozenset[str]:
    """Filter a category's node_class names out of CLASS_SPECS.

    A single source, not a duplicated list.
    """
    return frozenset(
        node_class.value for node_class, spec in CLASS_SPECS.items() if spec.category is category
    )


def _piping_classes_of_kind(*kinds: PipingKind) -> frozenset[str]:
    """The piping node_class names whose `ClassSpec.piping_kind` is one of `kinds`."""
    return frozenset(
        node_class.value for node_class, spec in CLASS_SPECS.items() if spec.piping_kind in kinds
    )


def _classes_with_label(*labels: str) -> frozenset[str]:
    """The node_class names whose label chain contains any of `labels` (a family, e.g. `Vessel`)."""
    return frozenset(
        node_class.value
        for node_class, spec in CLASS_SPECS.items()
        if any(label in spec.labels for label in labels)
    )


EQUIPMENT_CLASSES: frozenset[str] = _classes_in_category(NodeCategory.EQUIPMENT)
PIPING_CLASSES: frozenset[str] = _classes_in_category(NodeCategory.PIPING)
# "Valve" = something that opens, closes, checks or relieves flow. Fittings, pipe tees, flow meters
# and spec breaks are piping but not valves: a valve count must not include a pipe tee.
VALVE_CLASSES: frozenset[str] = _piping_classes_of_kind("operated", "check", "safety")
OPERATED_VALVE_CLASSES: frozenset[str] = _piping_classes_of_kind("operated")
FITTING_CLASSES: frozenset[str] = _piping_classes_of_kind("fitting")
JUNCTION_CLASSES: frozenset[str] = _piping_classes_of_kind("junction")
PRIMARY_ELEMENT_CLASSES: frozenset[str] = _piping_classes_of_kind("primary_element")
BREAK_CLASSES: frozenset[str] = _piping_classes_of_kind("break")
# The valve bodies a control loop's actuator may drive: a declared list, not derived (ADR-0044,
# extended from two bodies to six by ADR-0058).
CONTROL_VALVE_BODY_CLASSES: frozenset[str] = frozenset(
    {
        NodeClass.GLOBE_VALVE.value,
        NodeClass.BALL_VALVE.value,
        NodeClass.BUTTERFLY_VALVE.value,
        NodeClass.ANGLE_VALVE.value,
        NodeClass.ANGLE_GLOBE_VALVE.value,
        NodeClass.ANGLE_BALL_VALVE.value,
    }
)
# What can own an agitator: the vessel and heat-exchanger families (pyDEXPI's `agitator` field).
AGITATED_EQUIPMENT_CLASSES: frozenset[str] = _classes_with_label("Vessel", "HeatExchanger")
CONNECTOR_CLASSES: frozenset[str] = _classes_in_category(NodeCategory.CONNECTOR)
# Classes whose nodes may have no printed tag. A connector stub is a drawing symbol, not a tagged
# item. An actuator is drawn as part of its control valve and shares the valve's printed tag
# (ADR-0044: ISA *Control Loop Foundation* Figs. 7-16..7-19; DEXPI C01 example). A pipe tee,
# reducer, flange, coupling and the like are plain pipe parts: a P&ID prints no tag next to them,
# and the spec break and the electrical actuator are untagged like the plain actuator.
UNTAGGED_CLASSES: frozenset[str] = CONNECTOR_CLASSES | frozenset(
    node_class.value
    for node_class in (
        NodeClass.ACTUATING_FUNCTION,
        NodeClass.ACTUATING_ELECTRICAL_FUNCTION,
        NodeClass.PROPERTY_BREAK,
        NodeClass.PIPE_TEE,
        NodeClass.PIPE_REDUCER,
        NodeClass.BLIND_FLANGE,
        NodeClass.LINE_BLIND,
        NodeClass.FLANGE,
        NodeClass.FLANGED_CONNECTION,
        NodeClass.PIPE_COUPLING,
        NodeClass.CLAMPED_FLANGE_COUPLING,
        NodeClass.COMPENSATOR,
        NodeClass.HOSE,
        NodeClass.FUNNEL,
        NodeClass.PENETRATION,
        NodeClass.VENTILATION_DEVICE,
    )
)

# produced only by the generator (equipment + piping component + instrumentation) —
# this is the plant graph's "known class" set, without the connector and structural classes.
# Not among §4.5's named constants, but validation.py needs it —
# so it stays public, not underscored: two modules share it because of the file limit.
GENERATOR_CLASSES: frozenset[str] = (
    EQUIPMENT_CLASSES | PIPING_CLASSES | _classes_in_category(NodeCategory.INSTRUMENTATION)
)
KNOWN_CLASSES: frozenset[str] = frozenset(node_class.value for node_class in NodeClass)

# what a Proteus importer may accept as a node class: the generator's classes, the
# stub classes, plus the fallback with no curated ancestor chain (ADR-0016, §3.1).
# GENERATOR_CLASSES itself is not extended — the generator never produces an unknown class.
IMPORTABLE_CLASSES: frozenset[str] = (
    GENERATOR_CLASSES | CONNECTOR_CLASSES | {NodeClass.GENERIC_ITEM.value}
)

# The `vocabulary` argument of the pyDEXPI adapter and importer: v1's set is the default there, this
# is the v2 one (the allowlist classes plus `GenericItem`, ADR-0058). An alias, not a second list.
V2_IMPORTABLE_CLASSES: frozenset[str] = IMPORTABLE_CLASSES

# v1 pins (ADR-0057): today's exact values as literals, NOT aliases of the live constants above.
# Generator v2 grows the live sets; the v1 generator, its config defaults and the EX01 import read
# these so v1 output stays byte-identical. Never edit them.
V1_EQUIPMENT_CLASSES: frozenset[str] = frozenset(
    {"CentrifugalPump", "Compressor", "Tank", "PressureVessel", "ProcessColumn", "HeatExchanger"}
)
V1_VALVE_CLASSES: frozenset[str] = frozenset({"GlobeValve", "BallValve", "CheckValve"})
V1_OPERATED_VALVE_CLASSES: frozenset[str] = frozenset({"GlobeValve", "BallValve"})
V1_IMPORTABLE_CLASSES: frozenset[str] = frozenset(
    {
        "CentrifugalPump",
        "Compressor",
        "Tank",
        "PressureVessel",
        "ProcessColumn",
        "HeatExchanger",
        "GlobeValve",
        "BallValve",
        "CheckValve",
        "ProcessSignalGeneratingFunction",
        "ProcessInstrumentationFunction",
        "ActuatingFunction",
        "FlowOutPipeOffPageConnector",
        "FlowInPipeOffPageConnector",
        "FlowOutSignalOffPageConnector",
        "FlowInSignalOffPageConnector",
        "GenericItem",
    }
)

#: the importable vocabularies by the name the `--vocabulary` flag and the import record use
IMPORT_VOCABULARIES: dict[str, frozenset[str]] = {
    "v1": V1_IMPORTABLE_CLASSES,
    "v2": V2_IMPORTABLE_CLASSES,
}

# every NodeClass name v1 had: the importable ones plus the 4 structural classes. The CLASS_NAME
# answer prompt lists them, so its text stays byte-identical on v1 corpora while the enum grows.
V1_NODE_CLASSES: frozenset[str] = V1_IMPORTABLE_CLASSES | frozenset(
    {"ProcessPlant", "PlantSection", "DrawingSet", "Sheet"}
)

#: `GenericItem` is allowed at both ends of every topology relation in the schema: validation
#: cannot know the fallback's semantics — that is promotion's job (ADR-0016 rule 4).
_GENERIC_ITEM: frozenset[str] = frozenset({NodeClass.GENERIC_ITEM.value})

# Signal flow: a sensor (PSGF) feeds an indicator or controller (PIF / PCF, which may feed another
# controller in a cascade), which feeds an actuator (AF: a valve's; AEF: a machine's start/stop or
# speed signal).
_SIGNAL_SOURCES: frozenset[str] = frozenset(
    {
        NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
        NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
        NodeClass.PROCESS_CONTROL_FUNCTION.value,
        NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value,
    }
)
_SIGNAL_TARGETS: frozenset[str] = frozenset(
    {
        NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
        NodeClass.PROCESS_CONTROL_FUNCTION.value,
        NodeClass.ACTUATING_FUNCTION.value,
        NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value,
        NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
    }
)
_ACTUATORS: frozenset[str] = frozenset(
    {NodeClass.ACTUATING_FUNCTION.value, NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value}
)
_FLOW_IN_SIGNAL: frozenset[str] = frozenset({NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value})
_FLOW_OUT_SIGNAL: frozenset[str] = frozenset({NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value})

RELATION_ENDPOINTS: dict[Relation, tuple[frozenset[str], frozenset[str]]] = {
    Relation.SEND_TO: (
        EQUIPMENT_CLASSES
        | PIPING_CLASSES
        | _GENERIC_ITEM
        | {NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value},
        EQUIPMENT_CLASSES
        | PIPING_CLASSES
        | _GENERIC_ITEM
        | {NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value},
    ),
    Relation.SEND_SIGNAL_TO: (_SIGNAL_SOURCES | _GENERIC_ITEM, _SIGNAL_TARGETS | _GENERIC_ITEM),
    # an actuator drives a valve body; only an electrical actuator may drive a machine (the pair
    # rule in `validation.py` enforces that: this table only lists the classes allowed per end)
    Relation.CONTROL: (
        _ACTUATORS | _FLOW_IN_SIGNAL | _GENERIC_ITEM,
        CONTROL_VALVE_BODY_CLASSES | EQUIPMENT_CLASSES | _FLOW_OUT_SIGNAL | _GENERIC_ITEM,
    ),
    # a `PropertyBreak` is not a pyDEXPI `SensingLocation`, so no sensor can be located on one
    # (probed on pyDEXPI 1.2.0, design pid-vocabulary section 3.4): it is sent through, never sensed
    Relation.MEASURED_BY: (
        EQUIPMENT_CLASSES | (PIPING_CLASSES - BREAK_CLASSES) | _FLOW_IN_SIGNAL | _GENERIC_ITEM,
        frozenset({NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value})
        | _FLOW_OUT_SIGNAL
        | _GENERIC_ITEM,
    ),
    Relation.HAS_AGITATOR: (
        AGITATED_EQUIPMENT_CLASSES | _GENERIC_ITEM,
        frozenset({NodeClass.AGITATOR.value}) | _GENERIC_ITEM,
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


#: extra Neo4j label on every merged plant item (ADR-0036); no `NodeClass`, so no validator changes
PLANT_ITEM_LABEL = "PlantItem"
#: label of a line end whose continuation was never found; equals `plant_api.model`'s class name
UNRESOLVED_CONNECTOR_LABEL = "UnresolvedOffPageConnector"
#: relationship properties only the plant layer adds, and the model may see
PLANT_EDGE_PROVENANCE_PROPERTIES: frozenset[str] = frozenset({"crossed_sheets"})


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
