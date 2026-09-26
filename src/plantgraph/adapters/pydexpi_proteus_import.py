"""Betölt egy önálló Proteus XML rajzot egyetlen `SheetGraph`-ként (`kg-construction.md` §3, T1).

Ez a modul köti össze az EXP-0001 (egylapos) és EXP-0002 (plant-scale) kart: mindkettőnek
ugyanazon az ajtón — `SheetGraph` → `localize` → `resolve` — kell belépnie, különben egy
eltérés a kettő közt csővezeték-különbség lenne, nem skálahatás (ADR-0009 indoklása). A
generátor a saját `plant_graph`-ján át lép be; ez a modul ugyanezt egy külső fájlra teszi meg.

**Miért nem tűnhet el semmi csendben.** Egy valódi rajz (pl. `data/external/C01V04-VER.EX01.xml`)
olyan pyDEXPI-osztályokat is tartalmaz, amikre a séma (`graph.schema`) nincs curated névvel
felkészítve (`PipeTee`, `BlindFlange`, egy dugattyús szivattyú, ...). ADR-0016 óta ezek sem
esnek ki: a `pydexpi_generic` fallback `GenericItem`-mé alakítja őket, a pyDEXPI-osztályukat
megőrizve (§3.1) — ez a modul csak a hívási sorrendet adja, és jelenti, ha mégis maradna
nyomtalanul elveszett csomópont vagy él.
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
    """Az importálás lefedettségi jelentése: honnan jött a lap-azonosító, mi veszett el, hol."""

    source_file: str
    sha256: str
    sheet_id: str
    sheet_id_source: Literal["drawing_number", "file_stem", "argument"]
    drawing_name: str | None
    plant_id: str
    conceptual_nodes: int
    conceptual_edges: int
    conversion: ConversionReport
    #: kulcs "SourceClass->TargetClass" — az az él, aminek legalább az egyik vége nem
    #: térképezett osztály, ezért `ConversionReport.edges_dropped_per_label` nem látja
    edges_lost_to_unmapped_endpoints: dict[str, int] = Field(default_factory=dict)
    #: minden térképezett csomópont a valódi pyDEXPI-osztálya szerint, ismert és
    #: `GenericItem` egyaránt — a fallback saját lefedettségi számlálója (ADR-0016 §3.1 rule 6)
    nodes_per_dexpi_class: dict[str, int] = Field(default_factory=dict)
    #: hány, egyébként `related_to`-vá váló él ütközött egy már meglévő éllel a pár közt
    #: (ugyanaz a csomópont-pár, ADR-0016 §3.1 rule 5) — ilyenkor nem lesz duplikátum él
    related_to_collapsed: int = 0
    violations: list[SchemaViolation] = Field(default_factory=list)


@dataclass
class ImportedSheet:
    """Egy importált Proteus rajz: a lap gráfja plusz a hozzá tartozó jelentés."""

    sheet: SheetGraph
    report: ImportReport


def import_proteus_sheet(
    path: Path, *, sheet_id: str | None = None, plant_id: str | None = None
) -> ImportedSheet:
    """Betölt egy Proteus XML-t, és a séma `DiGraph`-jára fordítva egyetlen `SheetGraph`-ot ad.

    A csomópontok a pyDEXPI-belső konceptuális azonosítójukról a `proteusId`-jukra kapnak új
    nevet: az utóbbi stabil két betöltés között, az előbbi nem (§2 mérve) — az importnak ezért
    determinisztikusnak kell lennie a `proteusId`-n, nem a konceptuális gráf saját id-jén.

    A visszaadott lapnak nincsenek off-page connectorai (`sheet.connectors == []`): a DEXPI
    csatlakozó-hivatkozások séma-osztályokra fordítása még nyitott kérdés (§11), EX01 pedig
    egyetlen lap, tehát ezt egyelőre nem is igényli.
    """
    model = load_proteus(path.parent, path.name)
    conceptual = _load_conceptual_graph(model)

    resolved_plant_id = plant_id if plant_id is not None else path.stem
    resolved_sheet_id, sheet_id_source = _resolve_sheet_id(sheet_id, model, path)
    _check_no_colon(resolved_sheet_id, "sheet_id")

    # generikus fallback (ADR-0016, §3.1): a séma-ismeretlen osztályokat GenericItem-mé
    # címkézi egy másolaton, mielőtt az adapter eldobná őket
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
    """A teljes -> konceptuális gráf két lépése egy helyen (§3.6, mint a generátornál)."""
    complete = load_complete_graph(model)
    return abstract_conceptual_graph(complete)


def _resolve_sheet_id(
    sheet_id: str | None, model: DexpiModel, path: Path
) -> tuple[str, Literal["drawing_number", "file_stem", "argument"]]:
    """A lap-azonosító forrása: átadott érték > nyomtatott rajzszám > fájlnév (§3 "Rules")."""
    if sheet_id is not None:
        return sheet_id, "argument"
    drawing_number = _drawing_number(model)
    if drawing_number:
        return drawing_number, "drawing_number"
    return path.stem, "file_stem"


def _drawing_number(model: DexpiModel) -> str | None:
    """A `MetaData.drawingNumber` — a rajzon ténylegesen nyomtatott azonosító, ha van ilyen elem."""
    metadata = model.conceptualModel.metaData if model.conceptualModel is not None else None
    return metadata.drawingNumber if metadata is not None else None


def _drawing_name(model: DexpiModel) -> str | None:
    """A `MetaData.drawingName` — csak tájékoztató mező a jelentésben, semmi nem épül rá."""
    metadata = model.conceptualModel.metaData if model.conceptualModel is not None else None
    return metadata.drawingName if metadata is not None else None


def _check_no_colon(sheet_id: str, field_name: str) -> None:
    """A `:` a resolver kulcs-elválasztója (`localize.py`, `OffPageConnector.key`) — tiltott."""
    if ":" in sheet_id:
        raise ValueError(
            f"{field_name} {sheet_id!r} must not contain ':', the resolver's key separator"
        )


def _edges_lost_to_unmapped_endpoints(
    conceptual: nx.MultiDiGraph[str], mapped_ids: set[str]
) -> dict[str, int]:
    """A konceptuális élek, amiket a `ConversionReport` nem számol: az egyik végük nem térképezett.

    `_map_edges` (`pydexpi_adapter.py`) ezeket némán átlépi, mert csak a mindkét végén térképezett
    éleket nézi — ez a függvény pótolja a hiányzó számlálást (§2, mérve: 23/39 EX01-en).
    """
    lost: collections.Counter[str] = collections.Counter()
    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") == "parentStructure":
            continue  # a struktúra-élt a _fold_parent_structure oldja fel, nem topológia-él
        if source in mapped_ids and target in mapped_ids:
            continue
        source_label = conceptual.nodes[source].get("label")
        target_label = conceptual.nodes[target].get("label")
        lost[f"{source_label}->{target_label}"] += 1
    return dict(lost)


def _relabel_to_proteus_ids(
    plant: nx.DiGraph[str], conceptual: nx.MultiDiGraph[str], mapped_ids: set[str]
) -> nx.DiGraph[str]:
    """A térképezett gráfot a konceptuális id-król a stabil `proteusId`-ra nevezi át.

    Rendezett beszúrási sorrendben építi újra (mint a generátor `map_conceptual_graph`-ja),
    hogy két import ugyanazt a fájlt byte-azonos sorrendben adja vissza.
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
    """Konceptuális id -> `proteusId` leképezés a térképezett csomópontokra, egyediséget nézve."""
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
    """A fájl tartalmának hash-e — a jelentés így önmagában rögzíti, melyik bájtokból készült."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
