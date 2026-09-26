"""Load a standalone Proteus XML drawing as a single `SheetGraph` (`kg-construction.md` §3, T1).

This module is the link between the EXP-0001 (single-sheet) and EXP-0002
(plant-scale) experiment arms: both must enter through the same door —
`SheetGraph` -> `localize` -> `resolve` — otherwise a difference between the
two would be a piping difference, not a scale effect (ADR-0009's rationale).
The generator enters via its own `plant_graph`; this module does the same for
an external file.

**Why nothing may silently disappear.** A real drawing (e.g.
`data/external/C01V04-VER.EX01.xml`) also contains pyDEXPI classes the schema
(`graph.schema`) has no curated name for (`PipeTee`, `BlindFlange`, a
reciprocating pump, ...). Since ADR-0016, these are not dropped either: the
`pydexpi_generic` fallback converts them to `GenericItem`, preserving their
pyDEXPI class (§3.1) — this module only supplies the call order, and reports
if a node or edge would still be lost without a trace.
"""

from __future__ import annotations

import collections
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from plantgraph.adapters.pydexpi_adapter import (
    ConversionReport,
    abstract_conceptual_graph,
    load_complete_graph,
    map_conceptual_graph,
)
from plantgraph.adapters.pydexpi_generic import (
    add_related_to_edges,
    annotate_generic,
    count_nodes_per_dexpi_class,
    prepare_generic,
)
from plantgraph.adapters.pydexpi_io import load_proteus
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.validation import SchemaViolation, validate_sheet_graph


class ImportReport(BaseModel):
    """The import's coverage report: where the sheet id came from, what was lost, and where."""

    source_file: str
    sha256: str
    sheet_id: str
    sheet_id_source: Literal["drawing_number", "file_stem", "argument"]
    drawing_name: str | None
    plant_id: str
    conceptual_nodes: int
    conceptual_edges: int
    conversion: ConversionReport
    #: key "SourceClass->TargetClass" — an edge with at least one endpoint of an
    #: unmapped class, so `ConversionReport.edges_dropped_per_label` never sees it
    edges_lost_to_unmapped_endpoints: dict[str, int] = Field(default_factory=dict)
    #: every mapped node by its real pyDEXPI class, known and `GenericItem` alike
    #: — the fallback's own coverage counter (ADR-0016 §3.1 rule 6)
    nodes_per_dexpi_class: dict[str, int] = Field(default_factory=dict)
    #: how many edges that would otherwise become `related_to` collided with an
    #: existing edge on the same pair (same node pair, ADR-0016 §3.1 rule 5) — no
    #: duplicate edge results in that case
    related_to_collapsed: int = 0
    violations: list[SchemaViolation] = Field(default_factory=list)


@dataclass
class ImportedSheet:
    """An imported Proteus drawing: the sheet's graph plus its matching report."""

    sheet: SheetGraph
    report: ImportReport


def import_proteus_sheet(
    path: Path, *, sheet_id: str | None = None, plant_id: str | None = None
) -> ImportedSheet:
    """Load a Proteus XML file, and produce a single `SheetGraph`, in the schema's `DiGraph` form.

    Nodes are renamed from their internal pyDEXPI conceptual identifier to their
    `proteusId`: the latter is stable across two loads, the former is not
    (verified §2) — so the import must be deterministic on `proteusId`, not on
    the conceptual graph's own id.

    The returned sheet has no off-page connectors (`sheet.connectors == []`):
    translating DEXPI connector references into schema classes is still an open
    question (§11), and EX01 is a single sheet, so it doesn't need this yet.
    """
    model = load_proteus(path.parent, path.name)
    conceptual = _load_conceptual_graph(model)

    resolved_plant_id = plant_id if plant_id is not None else path.stem
    resolved_sheet_id, sheet_id_source = _resolve_sheet_id(sheet_id, model, path)
    _check_no_colon(resolved_sheet_id, "sheet_id")

    # generic fallback (ADR-0016, §3.1): relabels schema-unknown classes to GenericItem
    # on a copy, before the adapter would otherwise drop them
    prepared, generic_infos = prepare_generic(conceptual)
    plant, conversion = map_conceptual_graph(prepared, resolved_plant_id, stream_kind={})
    annotate_generic(plant, generic_infos, conceptual)
    _related_to_added, related_to_collapsed = add_related_to_edges(plant, conceptual)

    mapped_ids = set(plant.nodes)
    # the one piece of a file's own data this importer keeps — equipment/datasheet data is
    # out of scope (ADR-0021); the generator path never calls this, so a generated sheet gains
    # nothing from it
    _copy_piping_component_names(plant, conceptual, mapped_ids)
    lost_edges = _edges_lost_to_unmapped_endpoints(conceptual, mapped_ids)
    nodes_per_class = count_nodes_per_dexpi_class(conceptual, mapped_ids)

    localized_plant = _relabel_to_proteus_ids(plant, conceptual, mapped_ids)
    violations = validate_sheet_graph(localized_plant)

    report = ImportReport(
        source_file=str(path),
        sha256=_sha256_of_file(path),
        sheet_id=resolved_sheet_id,
        sheet_id_source=sheet_id_source,
        drawing_name=_drawing_name(model),
        plant_id=resolved_plant_id,
        conceptual_nodes=conceptual.number_of_nodes(),
        conceptual_edges=conceptual.number_of_edges(),
        conversion=conversion,
        edges_lost_to_unmapped_endpoints=lost_edges,
        nodes_per_dexpi_class=nodes_per_class,
        related_to_collapsed=related_to_collapsed,
        violations=violations,
    )
    sheet = SheetGraph(sheet_id=resolved_sheet_id, graph=localized_plant, connectors=[])
    return ImportedSheet(sheet=sheet, report=report)


def _copy_piping_component_names(
    plant: nx.DiGraph[str], conceptual: nx.MultiDiGraph[str], mapped_ids: set[str]
) -> None:
    """Copies each piping component's printed name onto its node, e.g. valve "66KL21".

    This is the one piece of a real file's own data this importer keeps: it is an identifier
    (ChatP&ID's flow-path answers name valves by it), not equipment/datasheet data — the rest of
    a file's own attributes (lengths, powers, pressures, ...) is out of scope, not part of this
    thesis (ADR-0021).
    """
    for node_id in mapped_ids:
        name = conceptual.nodes[node_id].get("pipingComponentName")
        if isinstance(name, str):
            plant.nodes[node_id]["piping_component_name"] = name


def _load_conceptual_graph(model: DexpiModel) -> nx.MultiDiGraph[str]:
    """The complete -> conceptual graph's two steps in one place (§3.6, same as the generator's)."""
    complete = load_complete_graph(model)
    return abstract_conceptual_graph(complete)


def _resolve_sheet_id(
    sheet_id: str | None, model: DexpiModel, path: Path
) -> tuple[str, Literal["drawing_number", "file_stem", "argument"]]:
    """The sheet id's source: given value > printed drawing number > file name (§3 "Rules")."""
    if sheet_id is not None:
        return sheet_id, "argument"
    drawing_number = _drawing_number(model)
    if drawing_number:
        return drawing_number, "drawing_number"
    return path.stem, "file_stem"


def _drawing_number(model: DexpiModel) -> str | None:
    """`MetaData.drawingNumber` — the identifier actually printed on the drawing, if present."""
    metadata = model.conceptualModel.metaData if model.conceptualModel is not None else None
    return metadata.drawingNumber if metadata is not None else None


def _drawing_name(model: DexpiModel) -> str | None:
    """`MetaData.drawingName` — an informational field in the report only; nothing depends on it."""
    metadata = model.conceptualModel.metaData if model.conceptualModel is not None else None
    return metadata.drawingName if metadata is not None else None


def _check_no_colon(sheet_id: str, field_name: str) -> None:
    """`:` is the resolver's key separator (`localize.py`, `OffPageConnector.key`) — forbidden."""
    if ":" in sheet_id:
        raise ValueError(
            f"{field_name} {sheet_id!r} must not contain ':', the resolver's key separator"
        )


def _edges_lost_to_unmapped_endpoints(
    conceptual: nx.MultiDiGraph[str], mapped_ids: set[str]
) -> dict[str, int]:
    """Conceptual edges the `ConversionReport` doesn't count: one of their ends is unmapped.

    `_map_edges` (`pydexpi_adapter.py`) silently skips these, since it only looks
    at edges mapped on both ends — this function supplies the missing count (§2,
    measured: 23/39 on EX01).
    """
    lost: collections.Counter[str] = collections.Counter()
    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") == "parentStructure":
            continue  # resolved by _fold_parent_structure instead; not a topology edge
        if source in mapped_ids and target in mapped_ids:
            continue
        source_label = conceptual.nodes[source].get("label")
        target_label = conceptual.nodes[target].get("label")
        lost[f"{source_label}->{target_label}"] += 1
    return dict(lost)


def _relabel_to_proteus_ids(
    plant: nx.DiGraph[str], conceptual: nx.MultiDiGraph[str], mapped_ids: set[str]
) -> nx.DiGraph[str]:
    """Rename the mapped graph from its conceptual ids to the stable `proteusId`.

    Rebuilt in sorted insertion order (like the generator's `map_conceptual_graph`),
    so two imports of the same file return it in byte-identical order.
    """
    id_map = _proteus_id_map(conceptual, mapped_ids)
    renamed = nx.relabel_nodes(plant, id_map, copy=True)
    ordered: nx.DiGraph[str] = nx.DiGraph()
    for node_id in sorted(renamed.nodes):
        ordered.add_node(node_id, **renamed.nodes[node_id])
    for source, target in sorted(renamed.edges):
        ordered.add_edge(source, target, **renamed.edges[source, target])
    return ordered


def _proteus_id_map(conceptual: nx.MultiDiGraph[str], mapped_ids: set[str]) -> dict[str, str]:
    """Map conceptual id -> `proteusId` for the mapped nodes, checking uniqueness."""
    id_map: dict[str, str] = {}
    seen: set[str] = set()
    for node_id in mapped_ids:
        proteus_id = conceptual.nodes[node_id].get("proteusId")
        if not isinstance(proteus_id, str) or not proteus_id:
            label = conceptual.nodes[node_id].get("label")
            raise ValueError(f"node {node_id} ({label}) has no proteusId; cannot relabel it")
        if proteus_id in seen:
            raise ValueError(f"proteusId {proteus_id!r} is not unique across mapped nodes")
        seen.add(proteus_id)
        id_map[node_id] = proteus_id
    return id_map


def _sha256_of_file(path: Path) -> str:
    """A hash of the file's contents — lets the report record which bytes it came from."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
