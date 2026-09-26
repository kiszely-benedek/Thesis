"""Lapokból egyetlen üzemgráf: azonosság szerint egyesít, csatlakozóparonként visszaköt.

A design `kg-construction.md` §5.4 három dolgot ír elő: egy csomópont a
reprezentánsa (az azonosság-csoport home-ja) attribútumait kapja, sosem az
uniót; egy párosított csatlakozó-csonk eltűnik, és a helyén a valódi él áll
vissza; egy párosítatlan csonk viszont megmarad — ez a jele annak a gate-en,
hogy egy pár elveszett.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import CONNECTOR_CLASSES


def build_plant_graph(
    sheets: Sequence[SheetGraph], pairs: Sequence[ConnectorPair], groups: Sequence[IdentityGroup]
) -> tuple[nx.DiGraph[str], int]:
    """Egyesíti a lapokat: azonosság-csoportok reprezentánsra vonva, csatlakozópárok visszakötve.

    Returns:
        Az egyesített gráf, és az élattribútum-ütközések száma (§5.4) — egy
        ütközés sosem dob kivételt, csak megszámolódik, és az elsőként
        beírt (lap-id sorrendben legkorábbi) attribútumhalmaz marad érvényben.
    """
    representative_of = _representative_of(groups)
    sheets_by_id = {sheet.sheet_id: sheet for sheet in sheets}
    paired_stub_keys = {pair.from_key for pair in pairs} | {pair.to_key for pair in pairs}
    ordered_sheets = sorted(sheets, key=lambda sheet: sheet.sheet_id)

    plant: nx.DiGraph[str] = nx.DiGraph()
    _add_representative_nodes(plant, ordered_sheets, representative_of, paired_stub_keys)
    conflicts = _add_intra_sheet_edges(plant, ordered_sheets, representative_of, paired_stub_keys)
    conflicts += _add_reconnected_edges(plant, sheets_by_id, pairs, representative_of)
    return plant, conflicts


def _representative_of(groups: Sequence[IdentityGroup]) -> dict[str, str]:
    """Minden reference helyi kulcsát a saját csoportja home-jára képezi; a home önmagára képez."""
    mapping: dict[str, str] = {}
    for group in groups:
        for reference in group.references:
            mapping[reference] = group.home
    return mapping


def _add_representative_nodes(
    plant: nx.DiGraph[str],
    sheets: Sequence[SheetGraph],
    representative_of: dict[str, str],
    paired_stub_keys: set[str],
) -> None:
    """Minden nem-csonk csomópontot felvesz a reprezentánsa saját attribútumaival, sosem unióval."""
    attrs_by_key = _non_connector_attrs_by_key(sheets)
    representative_keys = {representative_of.get(key, key) for key in attrs_by_key}
    for representative_key in sorted(representative_keys):
        plant.add_node(representative_key, **attrs_by_key[representative_key])
    _add_unpaired_stub_nodes(plant, sheets, paired_stub_keys)


def _non_connector_attrs_by_key(sheets: Sequence[SheetGraph]) -> dict[str, dict[str, Any]]:
    return {
        f"{sheet.sheet_id}:{node_id}": attrs
        for sheet in sheets
        for node_id, attrs in sheet.graph.nodes(data=True)
        if attrs.get("node_class") not in CONNECTOR_CLASSES
    }


def _add_unpaired_stub_nodes(
    plant: nx.DiGraph[str], sheets: Sequence[SheetGraph], paired_stub_keys: set[str]
) -> None:
    """A párba nem került csonkok csomópontként megmaradnak — a hiány így látszik a gate-en."""
    for sheet in sheets:
        for node_id, attrs in sheet.graph.nodes(data=True):
            if attrs.get("node_class") not in CONNECTOR_CLASSES:
                continue
            local_key = f"{sheet.sheet_id}:{node_id}"
            if local_key not in paired_stub_keys:
                plant.add_node(local_key, **attrs)


def _add_intra_sheet_edges(
    plant: nx.DiGraph[str],
    sheets: Sequence[SheetGraph],
    representative_of: dict[str, str],
    paired_stub_keys: set[str],
) -> int:
    """Lapon belüli éleket köt be a reprezentánsok közt; egy párosított csonk élét eldobja.

    Az utóbbit a `_add_reconnected_edges` pótolja a valódi, visszakötött éllel.
    """
    conflicts = 0
    for sheet in sheets:
        for source, target, attrs in sheet.graph.edges(data=True):
            source_key = _endpoint_or_none(sheet, source, representative_of, paired_stub_keys)
            target_key = _endpoint_or_none(sheet, target, representative_of, paired_stub_keys)
            if source_key is None or target_key is None:
                continue
            conflicts += _add_edge_tracking_conflicts(plant, source_key, target_key, attrs)
    return conflicts


def _endpoint_or_none(
    sheet: SheetGraph, node_id: str, representative_of: dict[str, str], paired_stub_keys: set[str]
) -> str | None:
    """A csomópont reprezentáns-kulcsa; `None`, ha egy párosított csonk (az éle máshonnan jön)."""
    local_key = f"{sheet.sheet_id}:{node_id}"
    if sheet.graph.nodes[node_id].get("node_class") in CONNECTOR_CLASSES:
        return None if local_key in paired_stub_keys else local_key
    return representative_of.get(local_key, local_key)


def _add_reconnected_edges(
    plant: nx.DiGraph[str],
    sheets_by_id: dict[str, SheetGraph],
    pairs: Sequence[ConnectorPair],
    representative_of: dict[str, str],
) -> int:
    """Minden párra visszaköti az eredeti élt: a kimenő csonk elődje -> a bejövő csonk utódja."""
    conflicts = 0
    for pair in sorted(pairs, key=lambda p: (p.from_key, p.to_key)):
        pred_key, edge_attrs = _stub_predecessor(sheets_by_id, pair.from_key)
        succ_key, _ = _stub_successor(sheets_by_id, pair.to_key)
        source = representative_of.get(pred_key, pred_key)
        target = representative_of.get(succ_key, succ_key)
        conflicts += _add_edge_tracking_conflicts(plant, source, target, edge_attrs)
    return conflicts


def _stub_predecessor(sheets_by_id: dict[str, SheetGraph], key: str) -> tuple[str, dict[str, Any]]:
    """A kimenő csonk elődje: az él, amelyen az anyag a csonkba lép a saját lapján belül."""
    sheet_id, node_id = key.split(":", 1)
    edges = list(sheets_by_id[sheet_id].graph.in_edges(node_id, data=True))
    if len(edges) != 1:
        raise ValueError(
            f"outgoing stub {key!r} has {len(edges)} incoming edges on its sheet; expected one"
        )
    source, _, attrs = edges[0]
    return f"{sheet_id}:{source}", attrs


def _stub_successor(sheets_by_id: dict[str, SheetGraph], key: str) -> tuple[str, dict[str, Any]]:
    """A bejövő csonk utódja: az él, amelyen az anyag a csonkból tovább lép a saját lapján belül."""
    sheet_id, node_id = key.split(":", 1)
    edges = list(sheets_by_id[sheet_id].graph.out_edges(node_id, data=True))
    if len(edges) != 1:
        raise ValueError(
            f"incoming stub {key!r} has {len(edges)} outgoing edges on its sheet; expected one"
        )
    _, target, attrs = edges[0]
    return f"{sheet_id}:{target}", attrs


def _add_edge_tracking_conflicts(
    plant: nx.DiGraph[str], source: str, target: str, attrs: dict[str, Any]
) -> int:
    """Felveszi az élt, vagy — ha már más attribútummal létezik — megszámolja az ütközést.

    A hívók mindig lap-id (illetve pár-kulcs) sorrendben dolgoznak, ezért az
    itt már meglévő attribútumhalmaz mindig a korábbi — pont az, amit a §5.4
    "keep the first" szabálya megkövetel.
    """
    if not plant.has_edge(source, target):
        plant.add_edge(source, target, **attrs)
        return 0
    if plant.edges[source, target] != attrs:
        return 1
    return 0
