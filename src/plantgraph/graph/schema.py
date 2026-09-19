"""A plant-generator és a splitter közös gráf-sémája.

Fogalmak, mert a kód egy mérnöki szakterületről szól:

- **P&ID**: egy üzem csöveinek és műszereinek műszaki rajza.
- **topológia-réteg**: amit a generátor kienged és a splitter darabol — csak
  "mi köt mihez, milyen fajta élen" (`send_to`, `control`, ...). Ez ennek a
  modulnak a tárgya.
- **struktúra-réteg**: tartalmazás, lapok, lapok közötti feloldás
  (`is_located_in`, `has_sheet`, ...). A gráf-betöltő állítja elő a Neo4j-ban;
  **sosem** él a splitter bemenő gráfjában (lásd a design 4.1. fejezetét: egy
  "unit tartalmazza az elemeit" él tönkretenné a splitter szomszédság-alapú
  klaszterezését).
- **node_class**: pyDEXPI osztálynév (pl. `CentrifugalPump`), a curated
  ős-osztály-lánccal együtt Neo4j címkeként (`labels_for`).

Ez a modul az érvényes csomópont- és éltípusokat, valamint azok kötelező
tulajdonságait tartalmazza — az ezekre épülő `validate_plant_graph` és
`validate_sheet_graph` ellenőrző függvények a testvérmodulban,
`plantgraph.graph.validation`-ben élnek (a 400 soros fájlkorlát miatt kerültek
külön; a design ezt még egy fájlként írta le). Sem ez, sem a testvérmodul nem
importál `pydexpi`-t vagy `plantgraph.benchmark`-ot (`plant-generator.md` §4.5):
ez utóbbi épít ezekre a modulokra, nem fordítva.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class NodeCategory(str, Enum):
    """Egy node_class melyik funkcionális csoportba tartozik (a §4.2 táblázat oszlopa)."""

    EQUIPMENT = "equipment"
    PIPING = "piping"
    INSTRUMENTATION = "instrumentation"
    CONNECTOR = "connector"
    STRUCTURE = "structure"


class NodeClass(str, Enum):
    """A séma összes csomópont-osztálya — pyDEXPI 1.2.0-ban ellenőrzött, curated névlánc.

    12 osztályt a generátor termel, 4 csonk-osztályt a splitter (amikor egy élt
    elvág, a helyére egy off-page connector csonkot tesz mindkét lapra), 4
    struktúra-osztály pedig csak a gráf-tárolóban létezik (`plant-generator.md`
    §4.2).
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


class Relation(str, Enum):
    """A séma összes éltípusa: 4 topológia-reláció és 5 struktúra-reláció (§4.3)."""

    SEND_TO = "send_to"
    SEND_SIGNAL_TO = "send_signal_to"
    CONTROL = "control"
    MEASURED_BY = "measured_by"
    IS_LOCATED_IN = "is_located_in"
    HAS_SHEET = "has_sheet"
    IS_DRAWN_ON = "is_drawn_on"
    CONTINUES_AS = "continues_as"
    SAME_TAGGED_ITEM_AS = "same_tagged_item_as"


class ClassSpec(BaseModel):
    """Egy node_class Neo4j-címkelánca, kategóriája és tag-előtagja — a §4.2 táblázat egy sora."""

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
}


def _classes_in_category(category: NodeCategory) -> frozenset[str]:
    """A CLASS_SPECS-ből szűri ki egy kategória node_class-neveit.

    Egyetlen forrás, nem duplikált lista.
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

# csak a generátor termeli őket (berendezés + csővezeték-elem + műszerezés) —
# ez a plant graph "ismert osztály" halmaza, a connector- és struktúra-osztályok nélkül.
# Nem szerepel a §4.5 nevesített konstansai közt, de a validation.py-nak kell —
# ezért marad publikus, nem alulvonásos: két modul osztozik rajta a fájlkorlát miatt.
GENERATOR_CLASSES: frozenset[str] = (
    EQUIPMENT_CLASSES | VALVE_CLASSES | _classes_in_category(NodeCategory.INSTRUMENTATION)
)
KNOWN_CLASSES: frozenset[str] = frozenset(node_class.value for node_class in NodeClass)

RELATION_ENDPOINTS: dict[Relation, tuple[frozenset[str], frozenset[str]]] = {
    Relation.SEND_TO: (
        EQUIPMENT_CLASSES | VALVE_CLASSES | {NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value},
        EQUIPMENT_CLASSES | VALVE_CLASSES | {NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value},
    ),
    Relation.SEND_SIGNAL_TO: (
        frozenset(
            {
                NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
                NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
                NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        ),
        frozenset(
            {
                NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
                NodeClass.ACTUATING_FUNCTION.value,
                NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        ),
    ),
    Relation.CONTROL: (
        frozenset(
            {NodeClass.ACTUATING_FUNCTION.value, NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value}
        ),
        frozenset(
            {
                NodeClass.GLOBE_VALVE.value,
                NodeClass.BALL_VALVE.value,
                NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        ),
    ),
    Relation.MEASURED_BY: (
        EQUIPMENT_CLASSES | {NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value},
        frozenset(
            {
                NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
                NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
            }
        ),
    ),
}

# a struktúra-relációknak (is_located_in, has_sheet, ...) nincs itt végpont-halmazuk:
# sosem szerepelnek a generátor/splitter gráfjának éleként (lásd a modul docstringjét)
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
    }
)
VISIBLE_EDGE_PROPERTIES: frozenset[str] = frozenset({"relation", "line_number", "fluid_code"})


def labels_for(node_class: str) -> tuple[str, ...]:
    """Egy node_class Neo4j-címkelánca, az ős-osztályokkal együtt (§4.2).

    Raises:
        ValueError: ha node_class nincs a sémában.
    """
    try:
        return CLASS_SPECS[NodeClass(node_class)].labels
    except ValueError:
        raise ValueError(
            f"unknown node_class {node_class!r}; expected one of {sorted(KNOWN_CLASSES)}"
        ) from None
