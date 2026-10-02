"""A third hand-built, hand-split toy plant, for the six dev-new families (QAR-T3).

Chosen so every reference answer, `k` and `u` in `test_qa_questions_dev2.py` can be counted by
a human. Node id and tag are the same string. `->` is `send_to`; units are in brackets.

    SRC-1[1] -> GV-1[1] -> P-1[1] -> V-1[1] -> CHV-1[1] -> TK-2[2] -> P-2[2] -> E-2[2]
    SRC-2[1] -> BV-1[1] ---------------^
    ISL-1[1]                                 (no edges at all)

    P-1 -measured_by-> FT-1, FT-3;  V-1 -measured_by-> FT-2
    loop FIC-1:  FT-1 -> FIC-1 -> FV-1 -control-> GV-1
    loop FIC-2:  FT-2 -> FIC-2 -> FV-2 -control-> BV-1

`GV-1` and `BV-1` are operated valves, `CHV-1` is a check valve. Every instrument is unit 1.

Hand-chosen sheets and the resulting cut:

    S1: SRC-1 SRC-2 ISL-1 GV-1 BV-1 FV-1 FV-2
    S2: P-1 V-1 CHV-1 FT-1 FT-2 FT-3 FIC-1 FIC-2
    S3: TK-2 P-2 E-2

    cut = {GV-1->P-1, BV-1->V-1, CHV-1->TK-2, FIC-1->FV-1, FIC-2->FV-2}
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import NodeClass, Relation

NC = NodeClass
# (tag, class, unit, sheet)
NODES: list[tuple[str, NodeClass, str, str]] = [
    ("SRC-1", NC.TANK, "1", "S1"),
    ("SRC-2", NC.TANK, "1", "S1"),
    ("ISL-1", NC.TANK, "1", "S1"),
    ("GV-1", NC.GLOBE_VALVE, "1", "S1"),
    ("BV-1", NC.BALL_VALVE, "1", "S1"),
    ("FV-1", NC.ACTUATING_FUNCTION, "1", "S1"),
    ("FV-2", NC.ACTUATING_FUNCTION, "1", "S1"),
    ("P-1", NC.CENTRIFUGAL_PUMP, "1", "S2"),
    ("V-1", NC.PRESSURE_VESSEL, "1", "S2"),
    ("CHV-1", NC.CHECK_VALVE, "1", "S2"),
    ("FT-1", NC.PROCESS_SIGNAL_GENERATING_FUNCTION, "1", "S2"),
    ("FT-2", NC.PROCESS_SIGNAL_GENERATING_FUNCTION, "1", "S2"),
    ("FT-3", NC.PROCESS_SIGNAL_GENERATING_FUNCTION, "1", "S2"),
    ("FIC-1", NC.PROCESS_INSTRUMENTATION_FUNCTION, "1", "S2"),
    ("FIC-2", NC.PROCESS_INSTRUMENTATION_FUNCTION, "1", "S2"),
    ("TK-2", NC.TANK, "2", "S3"),
    ("P-2", NC.CENTRIFUGAL_PUMP, "2", "S3"),
    ("E-2", NC.HEAT_EXCHANGER, "2", "S3"),
]
EQUIPMENT_TAGS = ["SRC-1", "SRC-2", "ISL-1", "P-1", "V-1", "TK-2", "P-2", "E-2"]
UNIT_OF = {tag: unit for tag, _, unit, _ in NODES}

_SEND_TO = [
    ("SRC-1", "GV-1"),
    ("GV-1", "P-1"),
    ("P-1", "V-1"),
    ("SRC-2", "BV-1"),
    ("BV-1", "V-1"),
    ("V-1", "CHV-1"),
    ("CHV-1", "TK-2"),
    ("TK-2", "P-2"),
    ("P-2", "E-2"),
]
_OTHER_EDGES = [
    ("P-1", "FT-1", Relation.MEASURED_BY),
    ("P-1", "FT-3", Relation.MEASURED_BY),
    ("V-1", "FT-2", Relation.MEASURED_BY),
    ("FT-1", "FIC-1", Relation.SEND_SIGNAL_TO),
    ("FIC-1", "FV-1", Relation.SEND_SIGNAL_TO),
    ("FV-1", "GV-1", Relation.CONTROL),
    ("FT-2", "FIC-2", Relation.SEND_SIGNAL_TO),
    ("FIC-2", "FV-2", Relation.SEND_SIGNAL_TO),
    ("FV-2", "BV-1", Relation.CONTROL),
]
CUT_EDGES = frozenset(
    {
        ("GV-1", "P-1"),
        ("BV-1", "V-1"),
        ("CHV-1", "TK-2"),
        ("FIC-1", "FV-1"),
        ("FIC-2", "FV-2"),
    }
)


def build_plant() -> nx.DiGraph[str]:
    """The ground-truth plant."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for tag, node_class, unit, _ in NODES:
        plant.add_node(tag, node_class=node_class.value, tag=tag, unit_id=unit)
    for source, target in _SEND_TO:
        plant.add_edge(source, target, relation=Relation.SEND_TO.value)
    for source, target, relation in _OTHER_EDGES:
        plant.add_edge(source, target, relation=relation.value)
    return plant


def build_sheets(plant: nx.DiGraph[str]) -> list[SheetGraph]:
    """The three hand-chosen sheets."""
    sheet_ids = ["S1", "S2", "S3"]
    return [
        SheetGraph(
            sheet_id=sheet_id,
            graph=plant.subgraph([tag for tag, _, _, sheet in NODES if sheet == sheet_id]).copy(),
        )
        for sheet_id in sheet_ids
    ]


def build_manifest() -> SplitManifest:
    """A manifest recording exactly `CUT_EDGES`."""
    return SplitManifest(
        source="qa_toy_plant_dev2",
        sheet_files=["S1", "S2", "S3"],
        connector_pairs=[
            ConnectorPair(from_key=f"out-{i}", to_key=f"in-{i}", original_edge=edge)
            for i, edge in enumerate(sorted(CUT_EDGES))
        ],
    )
