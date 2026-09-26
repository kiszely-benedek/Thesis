"""Read off-page connector labels from a localized sheet's node attributes.

The resolver may see only what would also be readable on a real drawing: a
connector symbol's own label and the single edge attached to it (design
`kg-construction.md` §5.1). This module never touches the `SheetGraph.connectors`
list — that is the splitter's answer key, already emptied out by `localize()`
(L2 leak, §4.1).

A connector node does not always have its own number and a referenced drawing
number: for an imported file, this DEXPI-reference mapping is still an open
question (`kg-construction.md` §11 OQ1b), and the synthetic `DRAWING_ONLY` dial
only leaves out the partner's own number, not the drawing number. A label with
neither its own number nor a referenced drawing number is therefore not an
error — it comes out as an `UnresolvedConnector`, and never raises.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel

from plantgraph.benchmark.models import ConnectorKind, Direction, UnresolvedConnector
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import CONNECTOR_CLASSES, NodeClass

# node_class -> (direction, kind): the stub's class encodes both at once
# (connectors.py:_connector_class produces the same thing, in the opposite direction).
_CONNECTOR_NODE_CLASSES: dict[str, tuple[Direction, ConnectorKind]] = {
    NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value: (Direction.OUTGOING, ConnectorKind.PIPE),
    NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value: (Direction.INCOMING, ConnectorKind.PIPE),
    NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value: (Direction.OUTGOING, ConnectorKind.SIGNAL),
    NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value: (Direction.INCOMING, ConnectorKind.SIGNAL),
}


class ConnectorLabel(BaseModel):
    """What could be read off an off-page connector symbol on a real drawing.

    This is the shared view between the synthetic splitter and the future
    OPEN100 adapter (`ConnectorObservation -> ConnectorLabel`, Phase 5) — pairing
    (`pairing.py`) only ever sees this, never the source-specific models. A
    missing optional field is not an error: a weaker labelling convention
    (`connector_label_detail=DRAWING_ONLY`) simply does not print the partner's
    own number on the symbol.
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


def read_connector_labels(
    sheet: SheetGraph,
) -> tuple[list[ConnectorLabel], list[UnresolvedConnector]]:
    """Turn every connector node on a localized sheet into a `ConnectorLabel`.

    Returns:
        The labels for which there was enough data, and separately those with
        neither their own number nor a referenced drawing number — these come
        out as `UnresolvedConnector` (see the module docstring), never raising.
    """
    labels: list[ConnectorLabel] = []
    unresolved: list[UnresolvedConnector] = []
    for node_id, attrs in sheet.graph.nodes(data=True):
        if attrs.get("node_class") not in CONNECTOR_CLASSES:
            continue
        label = _read_one_label(sheet, node_id, attrs)
        if label is None:
            from_key = f"{sheet.sheet_id}:{node_id}"
            unresolved.append(UnresolvedConnector(from_key=from_key, reason="no reference label"))
        else:
            labels.append(label)
    return labels, unresolved


def _read_one_label(
    sheet: SheetGraph, node_id: str, attrs: dict[str, Any]
) -> ConnectorLabel | None:
    connector_number = attrs.get("connector_number")
    referenced_drawing_number = attrs.get("referenced_drawing_number")
    if connector_number is None or referenced_drawing_number is None:
        return None
    direction, kind = _CONNECTOR_NODE_CLASSES[attrs["node_class"]]
    edge_attrs = _single_incident_edge_attrs(sheet, node_id)
    return ConnectorLabel(
        key=f"{sheet.sheet_id}:{node_id}",
        sheet_id=sheet.sheet_id,
        direction=direction,
        kind=kind,
        relation=cast("str | None", edge_attrs.get("relation")),
        connector_number=connector_number,
        referenced_drawing_number=referenced_drawing_number,
        referenced_connector_number=attrs.get("referenced_connector_number"),
        line_number=attrs.get("line_number"),
        fluid_code=attrs.get("fluid_code"),
    )


def _single_incident_edge_attrs(sheet: SheetGraph, node_id: str) -> dict[str, Any]:
    """The attributes of the stub's single edge.

    We check both directions, because which one applies depends on which side
    of the cut the sheet landed on (`rejoin.py:82-95` follows the same pattern).

    Raises:
        ValueError: if the node does not have exactly one incident edge — a
            real off-page connector symbol always has a single pipe or signal
            line attached.
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
