"""A splitter inverze: lapokból és a megoldókulcsból visszaállítja az eredeti üzemgráfot.

Csak a tesztek használják — annak ellenőrzésére, hogy split() nem veszít és nem
told hozzá semmit (splitter.md 4. fejezet, "round-trip invariant"). Két dolgot
kell visszacsinálnia: az off-page connector csonkokat vissza kell kötni a
tényleges élre, és az azonosság-csoportok reference-előfordulásait a home
csomópontba kell olvasztani, mielőtt a gráfok összehasonlíthatók.
"""

from __future__ import annotations

from typing import cast

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.splitter import SheetGraph


def rejoin(sheets: list[SheetGraph], manifest: SplitManifest) -> nx.DiGraph[str]:
    """Visszaállítja az eredeti gráfot a lapokból és a megoldókulcsból.

    Két lépésben: leszedi az OPC-csonkokat és visszaköti a vágott éleket,
    majd egyesíti az azonosság-csoportok reference-előfordulásait a home
    csomópontba (lásd a modul docstringjét).
    """
    stub_keys = {connector.key for sheet in sheets for connector in sheet.connectors}
    reference_keys = {
        reference for group in manifest.identity_groups for reference in group.references
    }

    merged: nx.DiGraph[str] = nx.DiGraph()
    for sheet in sheets:
        _copy_sheet_into(merged, sheet, stub_keys, reference_keys)
    for pair in manifest.connector_pairs:
        _reconnect(merged, sheets, pair)
    return merged


def _copy_sheet_into(
    merged: nx.DiGraph[str], sheet: SheetGraph, stub_keys: set[str], reference_keys: set[str]
) -> None:
    """Egy lap csomópontjait/éleit átteszi a közös gráfba, kihagyva az OPC-csonkokat.

    A reference-csomópont attribútumait szándékosan nem másoljuk át: azok
    csak a rajzon látszó, csonkolt adatok, az igazi attribútumokat a home
    előfordulás adja. Az élei viszont valódiak, azokat átvesszük.
    """
    for node_id, attrs in sheet.graph.nodes(data=True):
        key = f"{sheet.sheet_id}:{node_id}"
        if key in stub_keys:
            continue
        if key in reference_keys:
            merged.add_node(node_id)  # a teljes attribútumokat a home előfordulás adja majd
            continue
        merged.add_node(node_id, **attrs)

    for source, target, attrs in sheet.graph.edges(data=True):
        source_key = f"{sheet.sheet_id}:{source}"
        target_key = f"{sheet.sheet_id}:{target}"
        if source_key in stub_keys or target_key in stub_keys:
            continue  # az elvágott él egyik fele — a _reconnect állítja helyre a valódi élt
        merged.add_edge(source, target, **attrs)


def _reconnect(merged: nx.DiGraph[str], sheets: list[SheetGraph], pair: ConnectorPair) -> None:
    """Egy off-page connector pár helyére visszateszi az eredeti élt.

    Az attribútumokat a csonk-él őrizte meg, ezért innen olvassuk vissza.
    """
    original_edge = pair.original_edge
    if original_edge is None:
        raise ValueError(
            f"connector pair {pair.from_key} -> {pair.to_key} has no original_edge; "
            "only synthetic pairs can be rejoined"
        )
    attrs = _stub_edge_attrs(sheets, pair.from_key)
    source, target = original_edge
    merged.add_edge(source, target, **attrs)


def _stub_edge_attrs(sheets: list[SheetGraph], key: str) -> dict[str, object]:
    """Megkeresi egy csonk-csomópont egyetlen élét.

    Mindkét oldali csonk ugyanazt az eredeti-él adatot hordozza, ezért bármelyiket olvashatjuk.
    """
    sheet_id, node_id = key.split(":", 1)
    sheet = next(candidate for candidate in sheets if candidate.sheet_id == sheet_id)
    # egy csonknak pontosan egy éle van; az irány (be- vagy kimenő) attól függ,
    # melyik oldalára esett a vágásnak — ezért nézzük mindkét irányt
    for _, _, attrs in sheet.graph.out_edges(node_id, data=True):
        return cast(dict[str, object], attrs)
    for _, _, attrs in sheet.graph.in_edges(node_id, data=True):
        return cast(dict[str, object], attrs)
    raise ValueError(f"stub node {key!r} has no incident edge in its sheet graph — insertion bug")
