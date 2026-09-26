"""Csatlakozó-feliratok kiolvasása egy lokalizált lap csomópont-attribútumaiból.

A resolver csak azt láthatja, ami egy valódi rajzon is olvasható lenne: a
csatlakozó szimbólum saját feliratát és a hozzá kötött egyetlen élét (design
`kg-construction.md` §5.1). Ez a modul sosem nyúl a `SheetGraph.connectors`
listához — az a splitter válaszkulcsa, amit `localize()` már kiürített (L2
szivárgás, §4.1).
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel

from plantgraph.benchmark.models import ConnectorKind, Direction
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import CONNECTOR_CLASSES, NodeClass

# node_class -> (irány, fajta): a csonk osztálya egyszerre kódolja mindkettőt
# (connectors.py:_connector_class ugyanezt gyártja, csak ellenkező irányban).
_CONNECTOR_NODE_CLASSES: dict[str, tuple[Direction, ConnectorKind]] = {
    NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value: (Direction.OUTGOING, ConnectorKind.PIPE),
    NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value: (Direction.INCOMING, ConnectorKind.PIPE),
    NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value: (Direction.OUTGOING, ConnectorKind.SIGNAL),
    NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value: (Direction.INCOMING, ConnectorKind.SIGNAL),
}


class ConnectorLabel(BaseModel):
    """Amit egy off-page connector szimbólumról egy valódi rajzon le lehetne olvasni.

    Ez a közös nézet a szintetikus splitter és a majdani OPEN100-adapter
    (`ConnectorObservation -> ConnectorLabel`, Phase 5) között — a párosítás
    (`pairing.py`) csak ezt látja, sosem a forrás-specifikus modelleket. Az
    opcionális mezők hiánya nem hiba: egy gyengébb feliratozási konvenció
    (`connector_label_detail=DRAWING_ONLY`) egyszerűen nem írja rá a partner
    saját számát a szimbólumra.
    """

    key: str
    sheet_id: str
    direction: Direction
    kind: ConnectorKind | None
    relation: str | None
    connector_number: str
    referenced_drawing_number: str
    referenced_connector_number: str | None = None
    line_number: str | None = None
    fluid_code: str | None = None


def read_connector_labels(sheet: SheetGraph) -> list[ConnectorLabel]:
    """Egy lokalizált lap összes csatlakozó-csomópontját `ConnectorLabel`-lé alakítja."""
    return [
        _read_one_label(sheet, node_id, attrs)
        for node_id, attrs in sheet.graph.nodes(data=True)
        if attrs.get("node_class") in CONNECTOR_CLASSES
    ]


def _read_one_label(sheet: SheetGraph, node_id: str, attrs: dict[str, Any]) -> ConnectorLabel:
    direction, kind = _CONNECTOR_NODE_CLASSES[attrs["node_class"]]
    edge_attrs = _single_incident_edge_attrs(sheet, node_id)
    return ConnectorLabel(
        key=f"{sheet.sheet_id}:{node_id}",
        sheet_id=sheet.sheet_id,
        direction=direction,
        kind=kind,
        relation=cast("str | None", edge_attrs.get("relation")),
        connector_number=attrs["connector_number"],
        referenced_drawing_number=attrs["referenced_drawing_number"],
        referenced_connector_number=attrs.get("referenced_connector_number"),
        line_number=attrs.get("line_number"),
        fluid_code=attrs.get("fluid_code"),
    )


def _single_incident_edge_attrs(sheet: SheetGraph, node_id: str) -> dict[str, Any]:
    """A csonk egyetlen élének attribútumai.

    Mindkét irányt megnézzük, mert az attól függ, a lap melyik oldalára esett
    a vágás (`rejoin.py:82-95` ugyanezt a mintát követi).

    Raises:
        ValueError: ha a csomóponthoz nem pontosan egy él kapcsolódik — egy
            valódi off-page connector szimbólumnak mindig egyetlen csöve vagy
            jelvezetéke van.
    """
    out_edges = [attrs for _, _, attrs in sheet.graph.out_edges(node_id, data=True)]
    in_edges = [attrs for _, _, attrs in sheet.graph.in_edges(node_id, data=True)]
    incident = out_edges + in_edges
    if len(incident) != 1:
        raise ValueError(
            f"connector node {node_id!r} on sheet {sheet.sheet_id!r} has {len(incident)} "
            "incident edges; a real off-page connector stub has exactly one"
        )
    return incident[0]
