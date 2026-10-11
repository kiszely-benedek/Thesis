"""A hand-built, hand-split toy plant for the six held-out families (QAR-T10).

Node id and tag are the same string. `->` is `send_to`; units are in brackets.
Classes: TK tank, V vessel, P pump, E heat exchanger (equipment); GV globe and BV ball valve
(operated valves); CHV check valve (not operated).

    chain, units 1 -> 2 -> 3:
    A1[1] -> GV1[1] -> M1[1] -> P1[2] -> BV1[2] -> T2[3] -> P2[3] -> E2[3]
    B1[1] -> CHV1[1] -> M1[1]

    two flows meeting at TWO incomparable points (unit 4 into unit 5):
    A2[4] -> Z1[5], A2[4] -> Z2[5], B2[4] -> Z1[5], B2[4] -> Z2[5]

    a diamond with a different valve count on each side (unit 5):
    D1[5] -> BV2[5] -> E1[5]      D1[5] -> Q1[5] -> E1[5]

Sheets, chosen so that exactly three edges cross a sheet boundary:

    S1: everything except S2 and S3        S2: M1 P1 BV1        S3: T2 P2 E2
    cut = {GV1->M1, CHV1->M1, BV1->T2}
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import NodeClass, Relation

NC = NodeClass
# (tag, class, unit, sheet)
NODES: list[tuple[str, NodeClass, str, str]] = [
    ("A1", NC.TANK, "1", "S1"),
    ("B1", NC.TANK, "1", "S1"),
    ("GV1", NC.GLOBE_VALVE, "1", "S1"),
    ("CHV1", NC.CHECK_VALVE, "1", "S1"),
    ("M1", NC.PRESSURE_VESSEL, "1", "S2"),
    ("P1", NC.CENTRIFUGAL_PUMP, "2", "S2"),
    ("BV1", NC.BALL_VALVE, "2", "S2"),
    ("T2", NC.TANK, "3", "S3"),
    ("P2", NC.CENTRIFUGAL_PUMP, "3", "S3"),
    ("E2", NC.HEAT_EXCHANGER, "3", "S3"),
    ("A2", NC.TANK, "4", "S1"),
    ("B2", NC.TANK, "4", "S1"),
    ("Z1", NC.PRESSURE_VESSEL, "5", "S1"),
    ("Z2", NC.PRESSURE_VESSEL, "5", "S1"),
    ("D1", NC.TANK, "5", "S1"),
    ("BV2", NC.BALL_VALVE, "5", "S1"),
    ("Q1", NC.CENTRIFUGAL_PUMP, "5", "S1"),
    ("E1", NC.PRESSURE_VESSEL, "5", "S1"),
]
SEND_TO = [
    ("A1", "GV1"),
    ("GV1", "M1"),
    ("B1", "CHV1"),
    ("CHV1", "M1"),
    ("M1", "P1"),
    ("P1", "BV1"),
    ("BV1", "T2"),
    ("T2", "P2"),
    ("P2", "E2"),
    ("A2", "Z1"),
    ("A2", "Z2"),
    ("B2", "Z1"),
    ("B2", "Z2"),
    ("D1", "BV2"),
    ("BV2", "E1"),
    ("D1", "Q1"),
    ("Q1", "E1"),
]
CUT_EDGES = frozenset({("GV1", "M1"), ("CHV1", "M1"), ("BV1", "T2")})
SHEET_IDS = ["S1", "S2", "S3"]


def build_plant() -> nx.DiGraph[str]:
    """The ground-truth plant."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for tag, node_class, unit, _ in NODES:
        plant.add_node(tag, node_class=node_class.value, tag=tag, unit_id=unit)
    for source, target in SEND_TO:
        plant.add_edge(source, target, relation=Relation.SEND_TO.value)
    return plant


def build_sheets(plant: nx.DiGraph[str]) -> list[SheetGraph]:
    """The three hand-chosen sheets."""
    return [
        SheetGraph(
            sheet_id=sheet_id,
            graph=plant.subgraph([tag for tag, _, _, sheet in NODES if sheet == sheet_id]).copy(),
        )
        for sheet_id in SHEET_IDS
    ]


def build_manifest() -> SplitManifest:
    """A manifest recording exactly `CUT_EDGES`."""
    return SplitManifest(
        source="qa_toy_plant_heldout",
        sheet_files=SHEET_IDS,
        connector_pairs=[
            ConnectorPair(from_key=f"out-{i}", to_key=f"in-{i}", original_edge=edge)
            for i, edge in enumerate(sorted(CUT_EDGES))
        ],
    )
