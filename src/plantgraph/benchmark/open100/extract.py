"""Locate the off-page connectors' positions from the PID2Graph annotation files.

Background: the PID2Graph dataset supplies a GraphML file for every drawing, a
machine-readable description of it. That description is purely geometric,
though — every node just says "there is a valve here, at these coordinates".
**It contains no text at all**: no equipment tag, no label.

That means a connector's label (which says which sheet it points to) cannot be
read from the GraphML — only from the image. This module therefore only finds
where the connectors are; reading them happens on the crops, see crops.py.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from plantgraph.benchmark.models import BoundingBox, ConnectorObservation, Side

GRAPHML_NS = {"g": "http://graphml.graphdrawing.org/xmlns"}

#: The node class PID2Graph uses for connectors on the sheet edge.
#: Careful: there is also a class called 'connector', but it means something
#: entirely different — an in-sheet node marker, with 2408 of them across the
#: 12 sheets. Matching on that would give noise, not off-page connectors.
CONNECTOR_LABEL = "inlet/outlet"

_BBOX_KEYS = ("xmin", "ymin", "xmax", "ymax")


def _attribute_names(root: ET.Element) -> dict[str, str]:
    """Resolve GraphML's attribute abbreviations.

    GraphML does not name attributes directly, it refers to them by key: near
    the top of the file it declares that 'd0' = 'label', 'd1' = 'xmin', and so
    on. This function returns that lookup dictionary.
    """
    return {
        key.get("id", ""): key.get("attr.name", "") for key in root.findall("g:key", GRAPHML_NS)
    }


def _node_data(node: ET.Element, names: dict[str, str]) -> dict[str, str]:
    """Turn a node's XML children into a plain {attribute name: value} dictionary."""
    return {
        names[d.get("key", "")]: (d.text or "")
        for d in node.findall("g:data", GRAPHML_NS)
        if d.get("key", "") in names
    }


def _to_bbox(data: dict[str, str]) -> BoundingBox | None:
    """Build a bounding box, or return None if the node's coordinates are incomplete."""
    if not all(k in data for k in _BBOX_KEYS):
        return None
    return BoundingBox(**{k: float(data[k]) for k in _BBOX_KEYS})


def _side_of(bbox: BoundingBox, image_width: int) -> Side:
    """Say whether the symbol belongs to the sheet's left or right edge.

    This only looks at the position on the image. Deliberately does not infer
    direction from it: incoming connectors are conventionally drawn on the
    left, but that is a convention, not a rule — the real direction comes from
    the label.
    """
    return Side.LEFT if bbox.centre_x < image_width / 2 else Side.RIGHT


def connectors_in_sheet(graphml_path: Path, image_width: int) -> list[ConnectorObservation]:
    """Collect every off-page connector on one sheet.

    Args:
        graphml_path: the PID2Graph annotation file for this sheet.
        image_width: the drawing's width in pixels; determines the left/right side.

    Returns:
        One observation per connector, with geometry only for now — their
        labels are still empty.

    Raises:
        ValueError: if the file has no <graph> element, i.e. is not what we expect.
    """
    root = ET.parse(graphml_path).getroot()
    graph = root.find("g:graph", GRAPHML_NS)
    if graph is None:
        raise ValueError(f"no <graph> element in {graphml_path}")

    names = _attribute_names(root)
    stem = graphml_path.stem
    found: list[ConnectorObservation] = []

    for node in graph.findall("g:node", GRAPHML_NS):
        data = _node_data(node, names)
        if data.get("label") != CONNECTOR_LABEL:
            continue
        bbox = _to_bbox(data)
        if bbox is None:
            continue
        found.append(
            ConnectorObservation(
                sheet_file=stem,
                node_id=node.get("id", ""),
                bbox=bbox,
                side=_side_of(bbox, image_width),
            )
        )
    return found


def label_counts(graphml_path: Path) -> dict[str, int]:
    """Count how many elements of each type appear on the sheet.

    A quick sanity check: if the numbers on a new dataset don't resemble what we
    expect, either we are reading the wrong files or the format has changed.
    """
    root = ET.parse(graphml_path).getroot()
    graph = root.find("g:graph", GRAPHML_NS)
    if graph is None:
        raise ValueError(f"no <graph> element in {graphml_path}")

    names = _attribute_names(root)
    counts: dict[str, int] = {}
    for node in graph.findall("g:node", GRAPHML_NS):
        label = _node_data(node, names).get("label", "?")
        counts[label] = counts.get(label, 0) + 1
    return counts
