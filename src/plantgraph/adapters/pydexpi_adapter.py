"""A pyDEXPI-modellből a séma szerinti `DiGraph`-ot állítja elő (`plant-generator.md` §3.6).

Három lépésben: egy gyors (lineáris idejű) csomópont-gyűjtés, majd pyDEXPI saját
`GraphAbstractor`-a, ami a nyers "minden objektum és minden attribútum" gráfot
(**complete graph**) a lényegi (**conceptual graph**) alakra vonja össze — ezt
az utat futná be egy valódi DEXPI-fájl is, ezért ezen az adapteren át
hasonlítható össze az egylapos alapmérés (`DEXPIEX01.xml`) és a plant-scale
generátor kimenete (§8). A harmadik lépés a mienk: a pyDEXPI-osztályneveket és
él-attribútumokat a `graph.schema` relációira és tulajdonságaira fordítja.

Az így kapott `DiGraph` jellemzőinek összegzését (`summarize_plant`) a
`plant_summary.py` adja — külön modul, mert 400 sor fölé vinné ezt a fájlt, és
a logikája amúgy sem néz pyDEXPI-objektumot, csak a kimenő `DiGraph`-ot.
"""

from __future__ import annotations

import collections
from collections.abc import Mapping

import networkx as nx
import pydexpi.dexpi_classes.pydantic_classes as pydexpi_classes
import pydexpi.toolkits.base_model_utils as base_model_utils
from pydantic import BaseModel, Field
from pydexpi.dexpi_classes.pydantic_classes import DexpiBaseModel, DexpiModel
from pydexpi.loaders.graph_loader import GraphAbstractor, GraphLoader

from plantgraph.adapters.pydexpi_builder import GeneratedPlant
from plantgraph.benchmark.generator_models import GenerationRecord, StreamKind
from plantgraph.graph import schema


class LinearGraphLoader(GraphLoader):
    """pyDEXPI `GraphLoader`, lineáris idejű csomópont-gyűjtéssel.

    A stock `GraphLoader.parse_dexpi_to_graph` a `model_toolkit.get_all_instances_in_model`
    függvényt hívja, ami `obj not in list` dedupliká: ez pydantic `__eq__`
    hívásokban négyzetes (`plant-generator.md` §3.6, mérve: 140 s 250 egységnél,
    lásd §7). Ez az osztály csak a bejárást cseréli objektum-**azonosság**
    (`id(obj)`) szerinti deduplikálásra, a csomópont/él-építést pyDEXPI saját,
    változatlan `_add_nodes`/`_add_edges` metódusaira hagyva — invariáns 11
    ellenőrzi, hogy a kettő ugyanazt a gráfot adja.
    """

    def parse_dexpi_to_graph(self, dexpi_model: DexpiModel) -> nx.MultiDiGraph[str]:
        """A pyDEXPI `GraphLoader` felülírt belépési pontja — lásd az osztály docstringjét."""
        if dexpi_model.conceptualModel is None:
            raise ValueError("dexpi_model.conceptualModel is None; nothing to convert")
        graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
        instances = _collect_instances(dexpi_model.conceptualModel)
        self._add_nodes(graph, instances)
        self._add_edges(graph, instances)
        self.plant_model = dexpi_model
        self.plant_graph = graph
        return graph


def _collect_instances(root: DexpiBaseModel) -> list[DexpiBaseModel]:
    """DFS bejárás a kompozíciós fán, objektum-azonosság szerint deduplikálva."""
    seen: set[int] = set()
    ordered: list[DexpiBaseModel] = []
    stack: list[DexpiBaseModel] = [root]
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        ordered.append(obj)
        stack.extend(reversed(_composition_children(obj)))
    return ordered


def _composition_children(obj: DexpiBaseModel) -> list[DexpiBaseModel]:
    """Egy objektum kompozíciós (tulajdonolt, nem csak hivatkozott) gyermekei."""
    children: list[DexpiBaseModel] = []
    for value in base_model_utils.get_composition_attributes(obj).values():
        if isinstance(value, list):
            children.extend(item for item in value if isinstance(item, DexpiBaseModel))
        elif isinstance(value, DexpiBaseModel):
            children.append(value)
    return children


class ConversionReport(BaseModel):
    """A pyDEXPI -> séma `DiGraph` leképezés lefedettsége — semmi nem tűnik el nyomtalanul."""

    nodes_mapped: int = 0
    nodes_dropped_per_class: dict[str, int] = Field(default_factory=dict)
    edges_mapped_per_relation: dict[str, int] = Field(default_factory=dict)
    edges_dropped_per_label: dict[str, int] = Field(default_factory=dict)
    parent_structure_folded: int = 0
    valve_units_unresolved: int = 0
    parallel_edges_collapsed: int = 0


def load_complete_graph(model: DexpiModel) -> nx.MultiDiGraph[str]:
    """A teljes (complete) gráf: minden pyDEXPI-objektum és attribútum, lineáris betöltővel.

    Külön, publikus lépés (§3.6 1. lépése), hogy a `scale_smoke` (§9 step 7)
    ezt a szakaszt önmagában, `perf_counter`-rel mérhesse — anélkül, hogy
    pyDEXPI-t kellene importálnia (ADR-0003: csak `adapters/pydexpi_*.py` tehet ilyet).
    """
    return LinearGraphLoader().dexpi_to_graph(model)


def abstract_conceptual_graph(complete: nx.MultiDiGraph[str]) -> nx.MultiDiGraph[str]:
    """A lényegi (conceptual) gráf, pyDEXPI saját összevonásával, önálló szakaszként (§3.6)."""
    return GraphAbstractor.build_conceptual_graph(complete)


def plant_graph(generated: GeneratedPlant) -> tuple[nx.DiGraph[str], ConversionReport]:
    """Előállítja a séma `DiGraph`-ot és a lefedettségi jelentést a `GeneratedPlant` modelljéből."""
    complete = load_complete_graph(generated.model)
    conceptual = abstract_conceptual_graph(complete)
    return map_conceptual_graph(conceptual, generated.record)


def map_conceptual_graph(
    conceptual: nx.MultiDiGraph[str], record: GenerationRecord
) -> tuple[nx.DiGraph[str], ConversionReport]:
    """A pyDEXPI konceptuális gráfot a séma `DiGraph`-jára fordítja (§3.6 3. lépése)."""
    section_code = _section_codes(conceptual)
    mapped_nodes, nodes_dropped = _map_nodes(conceptual, record.plant_id)
    parent_folds = _fold_parent_structure(conceptual, mapped_nodes, section_code)
    chosen_edges, edges_mapped, edges_dropped, collapsed = _map_edges(
        conceptual, mapped_nodes, record.stream_kind
    )

    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id in sorted(mapped_nodes):  # invariáns 14: rendezett beszúrási sorrend
        plant.add_node(node_id, **mapped_nodes[node_id])
    for source, target in sorted(chosen_edges):
        relation, edge_attrs = chosen_edges[(source, target)]
        plant.add_edge(source, target, relation=relation.value, **edge_attrs)

    valve_units_unresolved = _assign_valve_units(plant)
    _assign_loop_tags(plant)

    report = ConversionReport(
        nodes_mapped=len(mapped_nodes),
        nodes_dropped_per_class=nodes_dropped,
        edges_mapped_per_relation=edges_mapped,
        edges_dropped_per_label=edges_dropped,
        parent_structure_folded=parent_folds,
        valve_units_unresolved=valve_units_unresolved,
        parallel_edges_collapsed=collapsed,
    )
    return plant, report


# ---- csomópontok --------------------------------------------------------------------------


def _section_codes(conceptual: nx.MultiDiGraph[str]) -> dict[str, str]:
    """`PlantSection`-csomópont id -> `plantSectionIdentificationCode` ("unit" szám, §4.2)."""
    return {
        node_id: str(attrs.get("plantSectionIdentificationCode"))
        for node_id, attrs in conceptual.nodes(data=True)
        if attrs.get("label") == schema.NodeClass.PLANT_SECTION.value
    }


def _map_nodes(
    conceptual: nx.MultiDiGraph[str], plant_id: str
) -> tuple[dict[str, dict[str, object]], dict[str, int]]:
    """A topológia-osztályú csomópontokat gyűjti; a struktúra- és ismeretlen osztályok kiesnek.

    Ami kiesik, az a `ConversionReport`-ba kerül — a `PlantSection`/`ProcessPlant`
    kiesése szándékos (§4.1: a struktúra-réteg sosem a splitter bemenő gráfjának
    csomópontja), nem hiba.
    """
    mapped: dict[str, dict[str, object]] = {}
    dropped: collections.Counter[str] = collections.Counter()
    for node_id, attrs in conceptual.nodes(data=True):
        label = str(attrs.get("label"))
        node_class = _topology_node_class(label)
        if node_class is None:
            dropped[label] += 1
            continue
        mapped[node_id] = {
            "node_class": node_class,
            "tag": _tag_of(node_class, attrs),
            "plant_id": plant_id,
        }
    return mapped, dict(dropped)


def _topology_node_class(label: str) -> str | None:
    """A pyDEXPI osztálynevet a séma egy topológia-osztályára fordítja, ős-osztályokon át (§6).

    A generátor mindig pontos névtalálatot ad; az ős-osztály ág az EXP-0001
    útvonalhoz kell, ahol egy valódi DEXPI-fájl finomabb alosztályokat használ
    (pl. `ReciprocatingPump`), amiknek nincs saját sémabeli neve.
    """
    if label in schema.GENERATOR_CLASSES:
        return label
    dexpi_class = getattr(pydexpi_classes, label, None)
    if dexpi_class is None:
        return None
    for ancestor in base_model_utils.get_inheritance_from_dexpi_class(dexpi_class):
        if ancestor.__name__ in schema.GENERATOR_CLASSES:
            return ancestor.__name__
    return None


def _tag_of(node_class: str, attrs: Mapping[str, object]) -> str | None:
    """Egy csomópont tagje a `GraphLoader` már belapított attribútumaiból (§3.6 "Node rules")."""
    if node_class in schema.EQUIPMENT_CLASSES:
        return _as_str(attrs.get("tagName"))
    if node_class in schema.VALVE_CLASSES:
        return _as_str(attrs.get("pipingComponentNumber"))
    if node_class == schema.NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value:
        return _as_str(attrs.get("processSignalGeneratingFunctionNumber"))
    if node_class == schema.NodeClass.ACTUATING_FUNCTION.value:
        return _as_str(attrs.get("actuatingFunctionNumber"))
    if node_class == schema.NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value:
        category = _as_str(attrs.get("processInstrumentationFunctionCategory")) or ""
        modifier = _as_str(attrs.get("processInstrumentationFunctionModifier")) or ""
        number = _as_str(attrs.get("processInstrumentationFunctionNumber")) or ""
        return f"{category}{modifier}-{number}"
    return None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _fold_parent_structure(
    conceptual: nx.MultiDiGraph[str],
    mapped_nodes: dict[str, dict[str, object]],
    section_code: dict[str, str],
) -> int:
    """A `parentStructure` élt a forrás `unit_id` mezőjébe olvasztja, nem élként veszi át (§4.1)."""
    folded = 0
    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") != "parentStructure" or target not in section_code:
            continue
        if source in mapped_nodes:
            mapped_nodes[source]["unit_id"] = section_code[target]
            folded += 1
    return folded


# ---- élek ----------------------------------------------------------------------------------

#: egy rendezett csomópont-pár még el nem döntött jelöltje: reláció és él-tulajdonságok
_EdgeCandidate = tuple[tuple[str, str], schema.Relation, dict[str, object]]
#: a végleges, párhuzamos-él-ütközés nélküli leképezés rendezett pár -> (reláció, tulajdonságok)
_ChosenEdges = dict[tuple[str, str], tuple[schema.Relation, dict[str, object]]]

_PIPE_LABELS = frozenset({"Pipe", "DirectPipingConnection"})
_SIGNAL_LABELS = frozenset(
    {"MeasuringLineFunction", "SignalLineFunction", "SignalConveyingFunction"}
)
#: melyik reláció győz, ha két pyDEXPI-él ugyanarra a rendezett csomópont-párra esne (§6)
_RELATION_PRIORITY = (
    schema.Relation.SEND_TO,
    schema.Relation.SEND_SIGNAL_TO,
    schema.Relation.CONTROL,
    schema.Relation.MEASURED_BY,
)


def _relation_of(attrs: Mapping[str, object]) -> tuple[schema.Relation, bool] | None:
    """Egy pyDEXPI konceptuális él sémabeli relációja, és hogy az irányát meg kell-e fordítani."""
    label, attr_name = attrs.get("label"), attrs.get("attr_name")
    if label in _PIPE_LABELS:
        return schema.Relation.SEND_TO, False
    if label in _SIGNAL_LABELS:
        return schema.Relation.SEND_SIGNAL_TO, False
    if label == "OperatedValveReference":
        return schema.Relation.CONTROL, False
    if label == "reference" and attr_name == "sensingLocation":
        # a PSGF hivatkozik az érzékelt helyre, de a sémában equipment -> PSGF a mérés iránya
        return schema.Relation.MEASURED_BY, True
    return None


def _edge_properties(
    relation: schema.Relation, attrs: Mapping[str, object], stream_kind: Mapping[str, StreamKind]
) -> dict[str, object]:
    """A `send_to` él tulajdonságai; a többi relációnak a sémában nincs saját él-tulajdonsága."""
    if relation is not schema.Relation.SEND_TO:
        return {}
    line_number = attrs.get("lineNumber")
    properties: dict[str, object] = {
        "line_number": line_number,
        "fluid_code": attrs.get("fluidCode"),
    }
    if isinstance(line_number, str) and line_number in stream_kind:
        properties["stream_kind"] = stream_kind[line_number].value
    return properties


def _map_edges(
    conceptual: nx.MultiDiGraph[str],
    mapped_nodes: dict[str, dict[str, object]],
    stream_kind: Mapping[str, StreamKind],
) -> tuple[_ChosenEdges, dict[str, int], dict[str, int], int]:
    """A topológia-éleket gyűjti és párhuzamos-él prioritással egy `DiGraph`-ra oldja fel.

    Visszaadja a végleges (rendezett pár -> reláció, tulajdonságok) leképezést,
    a végleges (győztes) élek relációnkénti darabszámát, az el nem fogadott
    él-fajták darabszámát, és hány párhuzamos élet nyelt el a prioritás.
    """
    candidates: list[_EdgeCandidate] = []
    dropped: collections.Counter[str] = collections.Counter()

    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") == "parentStructure":
            continue  # már feloldva unit_id-ra (_fold_parent_structure)
        if source not in mapped_nodes or target not in mapped_nodes:
            continue  # az egyik végpont struktúra- vagy ismeretlen osztály — nem topológia-él
        mapped = _relation_of(attrs)
        if mapped is None:
            dropped[f"{attrs.get('label')}/{attrs.get('attr_name')}"] += 1
            continue
        relation, reversed_direction = mapped
        pair = (target, source) if reversed_direction else (source, target)
        candidates.append((pair, relation, _edge_properties(relation, attrs, stream_kind)))

    chosen, collapsed = _resolve_parallel_edges(candidates)
    mapped_counts = collections.Counter(relation.value for relation, _ in chosen.values())
    return chosen, dict(mapped_counts), dict(dropped), collapsed


def _resolve_parallel_edges(candidates: list[_EdgeCandidate]) -> tuple[_ChosenEdges, int]:
    """Ha két él ugyanarra a rendezett párra esik, csak a magasabb prioritásút tartja meg."""
    chosen: _ChosenEdges = {}
    collapsed = 0
    for pair, relation, edge_attrs in candidates:
        current = chosen.get(pair)
        if current is not None:
            collapsed += 1
            if _RELATION_PRIORITY.index(relation) >= _RELATION_PRIORITY.index(current[0]):
                continue  # a jelenlegi magasabb (vagy egyenlő) prioritású, marad
        chosen[pair] = (relation, edge_attrs)
    return chosen, collapsed


def _assign_valve_units(plant: nx.DiGraph[str]) -> int:
    """A szelepnek nincs DEXPI `parentStructure`-je; a forrás felé sétálva örökli az `unit_id`-t.

    (§3.6: "owned by the source's unit")
    """
    unresolved = 0
    for node_id in sorted(plant.nodes):
        if plant.nodes[node_id]["node_class"] not in schema.VALVE_CLASSES:
            continue
        owner = _walk_to_owning_equipment(plant, node_id)
        if owner is None:
            unresolved += 1
            continue
        plant.nodes[node_id]["unit_id"] = plant.nodes[owner]["unit_id"]
    return unresolved


def _walk_to_owning_equipment(plant: nx.DiGraph[str], node_id: str) -> str | None:
    """Visszafelé lépked a `send_to` láncon egy szelepről, amíg berendezéshez nem ér."""
    current = node_id
    while plant.nodes[current]["node_class"] in schema.VALVE_CLASSES:
        upstream = [
            source
            for source, _, attrs in plant.in_edges(current, data=True)
            if attrs["relation"] == schema.Relation.SEND_TO.value
        ]
        if len(upstream) != 1:
            return None
        current = upstream[0]
    return current


_INSTRUMENT_CLASSES = frozenset(
    {
        schema.NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
        schema.NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
        schema.NodeClass.ACTUATING_FUNCTION.value,
    }
)


def _assign_loop_tags(plant: nx.DiGraph[str]) -> None:
    """A PIF saját tag-jét ráírja önmagára és a PSGF/AF szomszédaira, `loop_tag`-ként (§3.6)."""
    pif_class = schema.NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value
    for node_id in sorted(plant.nodes):
        if plant.nodes[node_id]["node_class"] != pif_class:
            continue
        loop_tag = plant.nodes[node_id]["tag"]
        variable = loop_tag[0] if loop_tag else None
        members = [node_id, *plant.predecessors(node_id), *plant.successors(node_id)]
        for member in members:
            if plant.nodes[member]["node_class"] in _INSTRUMENT_CLASSES:
                plant.nodes[member]["loop_tag"] = loop_tag
                plant.nodes[member]["measured_variable"] = variable
