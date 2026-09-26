"""Produces the schema's `DiGraph` from a pyDEXPI model (`plant-generator.md` §3.6).

In three steps: a fast (linear-time) node collection, then pyDEXPI's own `GraphAbstractor`,
which condenses the raw "every object and every attribute" graph (the **complete graph**)
into its essential form (the **conceptual graph**) — a real DEXPI file goes through this
same path, so this adapter lets the single-sheet baseline (`DEXPIEX01.xml`) be compared
against the plant-scale generator's output (§8). The third step is ours: translating
pyDEXPI class names and edge attributes into `graph.schema`'s relations and properties.

Summary statistics for the resulting `DiGraph` (`summarize_plant`) live in `plant_summary.py`
instead — a separate module, since it would push this file past 400 lines, and its logic
never touches a pyDEXPI object anyway.
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
from plantgraph.benchmark.generator_models import StreamKind
from plantgraph.graph import schema


class LinearGraphLoader(GraphLoader):
    """A pyDEXPI `GraphLoader`, with linear-time node collection.

    The stock `GraphLoader.parse_dexpi_to_graph` calls
    `model_toolkit.get_all_instances_in_model`, which deduplicates with `obj not
    in list`: quadratic in pydantic `__eq__` calls (`plant-generator.md` §3.6,
    measured at 140 s for 250 units, see §7). This class only replaces the
    traversal with deduplication by object **identity** (`id(obj)`), leaving
    node/edge construction to pyDEXPI's own `_add_nodes`/`_add_edges` methods —
    invariant 11 checks that the two produce the same graph.
    """

    def parse_dexpi_to_graph(self, dexpi_model: DexpiModel) -> nx.MultiDiGraph[str]:
        """The pyDEXPI `GraphLoader`'s overridden entry point — see the class docstring."""
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
    """A DFS walk over the composition tree, deduplicated by object identity."""
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
    """An object's composition children (owned, not merely referenced)."""
    children: list[DexpiBaseModel] = []
    for value in base_model_utils.get_composition_attributes(obj).values():
        if isinstance(value, list):
            children.extend(item for item in value if isinstance(item, DexpiBaseModel))
        elif isinstance(value, DexpiBaseModel):
            children.append(value)
    return children


class ConversionReport(BaseModel):
    """Coverage of the pyDEXPI -> schema `DiGraph` mapping — nothing disappears without a trace."""

    nodes_mapped: int = 0
    nodes_dropped_per_class: dict[str, int] = Field(default_factory=dict)
    edges_mapped_per_relation: dict[str, int] = Field(default_factory=dict)
    edges_dropped_per_label: dict[str, int] = Field(default_factory=dict)
    parent_structure_folded: int = 0
    valve_units_unresolved: int = 0
    parallel_edges_collapsed: int = 0


def load_complete_graph(model: DexpiModel) -> nx.MultiDiGraph[str]:
    """The complete graph: every pyDEXPI object and attribute, via the linear loader.

    A separate, public step (§3.6 step 1), so `scale_smoke` (§9 step 7) can time
    this stage on its own with `perf_counter` — without having to import pyDEXPI
    itself (ADR-0003: only `adapters/pydexpi_*.py` may do that).
    """
    return LinearGraphLoader().dexpi_to_graph(model)


def abstract_conceptual_graph(complete: nx.MultiDiGraph[str]) -> nx.MultiDiGraph[str]:
    """The conceptual graph, via pyDEXPI's own consolidation, as a standalone stage (§3.6)."""
    return GraphAbstractor.build_conceptual_graph(complete)


def plant_graph(generated: GeneratedPlant) -> tuple[nx.DiGraph[str], ConversionReport]:
    """Produce the schema's `DiGraph` and the coverage report from a `GeneratedPlant`'s model."""
    complete = load_complete_graph(generated.model)
    conceptual = abstract_conceptual_graph(complete)
    return map_conceptual_graph(conceptual, generated.record.plant_id, generated.record.stream_kind)


def map_conceptual_graph(
    conceptual: nx.MultiDiGraph[str], plant_id: str, stream_kind: Mapping[str, StreamKind]
) -> tuple[nx.DiGraph[str], ConversionReport]:
    """Translate the pyDEXPI conceptual graph to the schema's `DiGraph` (§3.6 step 3).

    `plant_id` and `stream_kind` are separate parameters, not a `GenerationRecord`:
    an imported file has no answer key, and passing a fabricated one would smuggle
    gold-standard data into the import.
    """
    section_code = _section_codes(conceptual)
    mapped_nodes, nodes_dropped = _map_nodes(conceptual, plant_id)
    parent_folds = _fold_parent_structure(conceptual, mapped_nodes, section_code)
    chosen_edges, edges_mapped, edges_dropped, collapsed = _map_edges(
        conceptual, mapped_nodes, stream_kind
    )

    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id in sorted(mapped_nodes):  # invariant 14: sorted insertion order
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


# ---- nodes --------------------------------------------------------------------------


def _section_codes(conceptual: nx.MultiDiGraph[str]) -> dict[str, str]:
    """`PlantSection` node id -> `plantSectionIdentificationCode` (the "unit" number, §4.2)."""
    return {
        node_id: str(attrs.get("plantSectionIdentificationCode"))
        for node_id, attrs in conceptual.nodes(data=True)
        if attrs.get("label") == schema.NodeClass.PLANT_SECTION.value
    }


def _map_nodes(
    conceptual: nx.MultiDiGraph[str], plant_id: str
) -> tuple[dict[str, dict[str, object]], dict[str, int]]:
    """Collect nodes of a topology class; structural and unknown classes are dropped.

    Whatever is dropped goes into the `ConversionReport` — dropping
    `PlantSection`/`ProcessPlant` is deliberate (§4.1: the structural layer is
    never a node in the splitter's input graph), not a bug.
    """
    mapped: dict[str, dict[str, object]] = {}
    dropped: collections.Counter[str] = collections.Counter()
    for node_id, attrs in conceptual.nodes(data=True):
        label = str(attrs.get("label"))
        node_class = topology_node_class(label)
        if node_class is None:
            dropped[label] += 1
            continue
        mapped[node_id] = {
            "node_class": node_class,
            "tag": _tag_of(node_class, attrs),
            "plant_id": plant_id,
        }
    return mapped, dict(dropped)


def topology_node_class(label: str) -> str | None:
    """Translate a pyDEXPI class name to one of the schema's topology classes, via ancestors (§6).

    The generator always gives an exact name match; the ancestor-class branch is needed
    for the EXP-0001 path, where a real DEXPI file uses finer-grained subclasses (e.g.
    `ReciprocatingPump`) with no name of their own in the schema.
    """
    if label in schema.IMPORTABLE_CLASSES:
        return label
    dexpi_class = getattr(pydexpi_classes, label, None)
    if dexpi_class is None:
        return None
    for ancestor in base_model_utils.get_inheritance_from_dexpi_class(dexpi_class):
        if ancestor.__name__ in schema.IMPORTABLE_CLASSES:
            return ancestor.__name__
    return None


def _tag_of(node_class: str, attrs: Mapping[str, object]) -> str | None:
    """A node's tag, from attributes the `GraphLoader` flattened onto it (§3.6 "Node rules")."""
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
    """Fold the `parentStructure` edge into the source's `unit_id` field, not as an edge (§4.1)."""
    folded = 0
    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") != "parentStructure" or target not in section_code:
            continue
        if source in mapped_nodes:
            mapped_nodes[source]["unit_id"] = section_code[target]
            folded += 1
    return folded


# ---- edges ----------------------------------------------------------------------------------

#: an as-yet-undecided candidate for an ordered node pair: relation and edge properties
_EdgeCandidate = tuple[tuple[str, str], schema.Relation, dict[str, object]]
#: the final mapping, free of parallel-edge conflicts: ordered pair -> (relation, properties)
_ChosenEdges = dict[tuple[str, str], tuple[schema.Relation, dict[str, object]]]

_PIPE_LABELS = frozenset({"Pipe", "DirectPipingConnection"})
_SIGNAL_LABELS = frozenset(
    {"MeasuringLineFunction", "SignalLineFunction", "SignalConveyingFunction"}
)
#: which relation wins if two pyDEXPI edges would fall on the same ordered node pair (§6)
_RELATION_PRIORITY = (
    schema.Relation.SEND_TO,
    schema.Relation.SEND_SIGNAL_TO,
    schema.Relation.CONTROL,
    schema.Relation.MEASURED_BY,
)


def _relation_of(attrs: Mapping[str, object]) -> tuple[schema.Relation, bool] | None:
    """A pyDEXPI conceptual edge's schema relation, and whether its direction must be reversed."""
    label, attr_name = attrs.get("label"), attrs.get("attr_name")
    if label in _PIPE_LABELS:
        return schema.Relation.SEND_TO, False
    if label in _SIGNAL_LABELS:
        return schema.Relation.SEND_SIGNAL_TO, False
    if label == "OperatedValveReference":
        return schema.Relation.CONTROL, False
    if label == "reference" and attr_name == "sensingLocation":
        # the PSGF references the sensed location; equipment -> PSGF is the measurement direction
        return schema.Relation.MEASURED_BY, True
    return None


def _edge_properties(
    relation: schema.Relation, attrs: Mapping[str, object], stream_kind: Mapping[str, StreamKind]
) -> dict[str, object]:
    """The `send_to` edge's properties; every other relation has no edge properties of its own."""
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
    """Collect the topology edges and resolve them onto a `DiGraph` by parallel-edge priority.

    Returns the final (ordered pair -> relation, properties) mapping, the count of
    winning edges per relation, the count of rejected edge kinds, and how many
    parallel edges the priority rule collapsed.
    """
    candidates: list[_EdgeCandidate] = []
    dropped: collections.Counter[str] = collections.Counter()

    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") == "parentStructure":
            continue  # already resolved into unit_id (_fold_parent_structure)
        if source not in mapped_nodes or target not in mapped_nodes:
            continue  # one endpoint is a structural or unknown class — not a topology edge
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
    """If two edges fall on the same ordered pair, keep only the higher-priority one."""
    chosen: _ChosenEdges = {}
    collapsed = 0
    for pair, relation, edge_attrs in candidates:
        current = chosen.get(pair)
        if current is not None:
            collapsed += 1
            if _RELATION_PRIORITY.index(relation) >= _RELATION_PRIORITY.index(current[0]):
                continue  # the current one has higher (or equal) priority, so it stays
        chosen[pair] = (relation, edge_attrs)
    return chosen, collapsed


def _assign_valve_units(plant: nx.DiGraph[str]) -> int:
    """A valve has no DEXPI `parentStructure`; it inherits `unit_id` by walking towards its source.

    (§3.6: "owned by the source's unit")
    """
    unresolved = 0
    for node_id in sorted(plant.nodes):
        if plant.nodes[node_id]["node_class"] not in schema.VALVE_CLASSES:
            continue
        owner = _walk_to_owning_equipment(plant, node_id)
        if owner is None or "unit_id" not in plant.nodes[owner]:
            # the owner has no unit_id either, on a file without a PlantSection (imported EX01,
            # kg-construction.md §2) — this too is an unresolved case, not a KeyError
            unresolved += 1
            continue
        plant.nodes[node_id]["unit_id"] = plant.nodes[owner]["unit_id"]
    return unresolved


def _walk_to_owning_equipment(plant: nx.DiGraph[str], node_id: str) -> str | None:
    """Walk backward along the `send_to` chain from a valve until it reaches equipment."""
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
    """Write the PIF's own tag onto itself and its PSGF/AF neighbours, as `loop_tag` (§3.6)."""
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
