"""`build_plant_graph` — merge by identity, reconnect pair by pair.

Tests in isolation, on hand-built localized sheets (design
`kg-construction.md` §5.4); the full pipeline is exercised by the resolver gate
checks (`test_resolution_resolver.py`).
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, IdentityGroup, MatchRule
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.merge import build_plant_graph

_Edge = tuple[str, str, dict[str, object]]


def _sheet(
    sheet_id: str, nodes: dict[str, dict[str, object]], edges: list[_Edge] | None = None
) -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node_id, attrs in nodes.items():
        graph.add_node(node_id, **attrs)
    for source, target, attrs in edges or []:
        graph.add_edge(source, target, **attrs)
    return SheetGraph(sheet_id=sheet_id, graph=graph)


def test_a_node_takes_the_representatives_own_attributes_not_a_union() -> None:
    home_sheet = _sheet(
        "0", {"eqA": {"node_class": "CentrifugalPump", "tag": "P-1", "plant_id": "u0"}}
    )
    reference_sheet = _sheet(
        "1",
        {
            "eqA-ref": {"node_class": "CentrifugalPump", "tag": "P-1"},
            "eqB": {"node_class": "CentrifugalPump", "tag": "P-2"},
        },
        edges=[("eqA-ref", "eqB", {"relation": "send_to"})],
    )
    groups = [IdentityGroup(tag="P-1", home="0:eqA", references=["1:eqA-ref"])]

    plant, conflicts = build_plant_graph([home_sheet, reference_sheet], pairs=[], groups=groups)

    assert conflicts == 0
    assert set(plant.nodes) == {"0:eqA", "1:eqB"}, "the reference must not remain a separate node"
    assert plant.nodes["0:eqA"] == {"node_class": "CentrifugalPump", "tag": "P-1", "plant_id": "u0"}
    assert ("0:eqA", "1:eqB") in plant.edges, "the local edge connects through the representative"


def test_a_paired_stub_is_dropped_and_the_original_edge_reconnected() -> None:
    edge_attrs = {"relation": "send_to", "line_number": "PL-1"}
    sheet_out = _sheet(
        "0",
        {
            "src": {"node_class": "CentrifugalPump", "tag": "P-1"},
            "stub-out": {
                "node_class": "FlowOutPipeOffPageConnector",
                "connector_number": "OUT-1",
                "referenced_drawing_number": "1",
            },
        },
        edges=[("src", "stub-out", edge_attrs)],
    )
    sheet_in = _sheet(
        "1",
        {
            "stub-in": {
                "node_class": "FlowInPipeOffPageConnector",
                "connector_number": "IN-1",
                "referenced_drawing_number": "0",
            },
            "dst": {"node_class": "CentrifugalPump", "tag": "P-2"},
        },
        edges=[("stub-in", "dst", edge_attrs)],
    )
    pairs = [
        ConnectorPair(from_key="0:stub-out", to_key="1:stub-in", match_rule=MatchRule.LINE_NUMBER)
    ]

    plant, conflicts = build_plant_graph([sheet_out, sheet_in], pairs=pairs, groups=[])

    assert conflicts == 0
    assert "0:stub-out" not in plant.nodes
    assert "1:stub-in" not in plant.nodes
    assert plant.edges["0:src", "1:dst"] == edge_attrs


def test_an_unpaired_stub_stays_as_a_node_with_its_edge() -> None:
    edge_attrs = {"relation": "send_to"}
    sheet_out = _sheet(
        "0",
        {
            "src": {"node_class": "CentrifugalPump", "tag": "P-1"},
            "stub-out": {
                "node_class": "FlowOutPipeOffPageConnector",
                "connector_number": "OUT-1",
                "referenced_drawing_number": "1",
            },
        },
        edges=[("src", "stub-out", edge_attrs)],
    )

    plant, conflicts = build_plant_graph([sheet_out], pairs=[], groups=[])

    assert conflicts == 0
    assert "0:stub-out" in plant.nodes, "an unpaired stub must not silently disappear"
    assert plant.edges["0:src", "0:stub-out"] == edge_attrs


def test_conflicting_edge_attributes_are_counted_and_the_first_by_sheet_id_wins() -> None:
    sheet_0 = _sheet(
        "0",
        {
            "a": {"node_class": "CentrifugalPump", "tag": "P-1"},
            "b": {"node_class": "CentrifugalPump", "tag": "P-2"},
        },
        edges=[("a", "b", {"relation": "send_to", "line_number": "L1"})],
    )
    sheet_1 = _sheet(
        "1",
        {
            "a-ref": {"node_class": "CentrifugalPump", "tag": "P-1"},
            "b-ref": {"node_class": "CentrifugalPump", "tag": "P-2"},
        },
        edges=[("a-ref", "b-ref", {"relation": "send_to", "line_number": "L2"})],
    )
    groups = [
        IdentityGroup(tag="P-1", home="0:a", references=["1:a-ref"]),
        IdentityGroup(tag="P-2", home="0:b", references=["1:b-ref"]),
    ]

    plant, conflicts = build_plant_graph([sheet_0, sheet_1], pairs=[], groups=groups)

    assert conflicts == 1
    assert plant.edges["0:a", "0:b"] == {"relation": "send_to", "line_number": "L1"}, (
        "the attribute set written first (in sheet-id order) stays in effect"
    )
