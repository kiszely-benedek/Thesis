"""A second hand-built, hand-split toy plant, for QA-T7's families.

`qa_toy_plant.py` has no node with two upstream routes and no unit that
receives flow from another unit with a valve in between, so the T7 families
get their own small plant. Topology (`->` is `send_to`, `CHV` a check valve):

    TK-1-1 -> GV-1-1 -----------------> V-1-1 -> TK-2-1
    TK-1-1 -> P-1-1                       ^
    TK-1-2 -> GV-1-2 -> CHV-1-1 ----------+

Everything tagged `-1-` is unit 1; `TK-2-1` is unit 2.

Hand-chosen sheets and the resulting cut (edges whose ends differ in sheet):

    S1: TK-1-1, GV-1-1, TK-1-2, P-1-1
    S2: GV-1-2, CHV-1-1, V-1-1
    S3: TK-2-1

    cut = {GV-1-1->V-1-1, TK-1-2->GV-1-2, V-1-1->TK-2-1}
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import NodeClass, Relation

# (tag, class, unit); the tag doubles as the node id, which keeps the tests readable.
_NODES: list[tuple[str, NodeClass, str]] = [
    ("TK-1-1", NodeClass.TANK, "1"),
    ("GV-1-1", NodeClass.GLOBE_VALVE, "1"),
    ("P-1-1", NodeClass.CENTRIFUGAL_PUMP, "1"),
    ("TK-1-2", NodeClass.TANK, "1"),
    ("GV-1-2", NodeClass.GLOBE_VALVE, "1"),
    ("CHV-1-1", NodeClass.CHECK_VALVE, "1"),
    ("V-1-1", NodeClass.PRESSURE_VESSEL, "1"),
    ("TK-2-1", NodeClass.TANK, "2"),
]
_FLOW_EDGES = [
    ("TK-1-1", "GV-1-1"),
    ("TK-1-1", "P-1-1"),
    ("GV-1-1", "V-1-1"),
    ("TK-1-2", "GV-1-2"),
    ("GV-1-2", "CHV-1-1"),
    ("CHV-1-1", "V-1-1"),
    ("V-1-1", "TK-2-1"),
]
CUT_EDGES = frozenset({("GV-1-1", "V-1-1"), ("TK-1-2", "GV-1-2"), ("V-1-1", "TK-2-1")})
_SHEETS = {
    "S1": ["TK-1-1", "GV-1-1", "TK-1-2", "P-1-1"],
    "S2": ["GV-1-2", "CHV-1-1", "V-1-1"],
    "S3": ["TK-2-1"],
}


def build_plant() -> nx.DiGraph[str]:
    """The ground-truth plant; node id and tag are the same string here."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for tag, node_class, unit_id in _NODES:
        plant.add_node(tag, node_class=node_class.value, tag=tag, unit_id=unit_id)
    for source, target in _FLOW_EDGES:
        plant.add_edge(source, target, relation=Relation.SEND_TO.value)
    return plant


def build_sheets(plant: nx.DiGraph[str]) -> list[SheetGraph]:
    """The three hand-chosen sheets."""
    return [
        SheetGraph(sheet_id=sheet_id, graph=plant.subgraph(ids).copy())
        for sheet_id, ids in _SHEETS.items()
    ]


def build_manifest() -> SplitManifest:
    """A manifest recording exactly `CUT_EDGES`."""
    return SplitManifest(
        source="qa_toy_plant_t7",
        sheet_files=list(_SHEETS),
        connector_pairs=[
            ConnectorPair(from_key=f"out-{i}", to_key=f"in-{i}", original_edge=edge)
            for i, edge in enumerate(sorted(CUT_EDGES))
        ],
    )
