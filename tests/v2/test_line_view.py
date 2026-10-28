"""The line view: flow folded through untagged pipe parts, and its agreement with the gold."""

from __future__ import annotations

import networkx as nx
import pytest
from corpus_v2 import corpus

from plantgraph.graph.line_view import (
    NO_INFLOW_MARK,
    NO_OUTFLOW_MARK,
    LineEdge,
    fold_line_edges,
    kind_of,
    line_ends,
)
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.line_view_fidelity import (
    compare_line_views,
    gold_line_view,
    system_line_view,
)
from plantgraph.qa.plant_api.item_graph import build_item_graph

# tank -> tee -> {valve, pump}; valve -> strainer (tagged) -> flange -> drum
_CLASSES = {
    "tank": "Tank",
    "tee": "PipeTee",
    "valve": "GateValve",
    "pump": "CentrifugalPump",
    "str": "ConicalStrainer",
    "flange": "Flange",
    "drum": "PressureVessel",
}
_TAGS: dict[str, str | None] = {
    "tank": "TK-1",
    "tee": None,
    "valve": "GTV-1",
    "pump": "P-1",
    "str": "STR-1",
    "flange": None,
    "drum": "V-1",
}
_FLOW = [
    ("tank", "tee"),
    ("tee", "valve"),
    ("tee", "pump"),
    ("valve", "str"),
    ("str", "flange"),
    ("flange", "drum"),
]


def test_flow_through_a_tee_becomes_one_line_edge_per_item() -> None:
    edges = fold_line_edges(_CLASSES, _TAGS, _FLOW)
    assert LineEdge(source="tank", target="valve", n_fittings=1) in edges
    assert LineEdge(source="tank", target="pump", n_fittings=1) in edges


def test_a_tagged_inline_component_is_named_and_an_untagged_one_counted() -> None:
    edges = fold_line_edges(_CLASSES, _TAGS, _FLOW)
    assert LineEdge(source="valve", target="drum", via_tags=("STR-1",), n_fittings=1) in edges


def test_a_line_walk_stops_at_the_first_line_item() -> None:
    sources = {(e.source, e.target) for e in fold_line_edges(_CLASSES, _TAGS, _FLOW)}
    assert ("tank", "drum") not in sources


def test_line_ends_mark_where_a_line_starts_and_stops() -> None:
    edges = fold_line_edges(_CLASSES, _TAGS, _FLOW)
    ends = line_ends(["tank", "valve", "pump", "drum"], edges)
    assert ends.marks_of("tank") == (NO_INFLOW_MARK,)
    assert ends.marks_of("drum") == (NO_OUTFLOW_MARK,)
    assert ends.marks_of("valve") == ()


def test_a_flow_edge_with_an_unknown_node_is_refused() -> None:
    with pytest.raises(ValueError, match="node class"):
        fold_line_edges({"a": "Tank"}, {"a": "T"}, [("a", "ghost")])


def test_a_recycle_through_fittings_does_not_list_the_start_item() -> None:
    classes = {"a": "Tank", "t": "PipeTee"}
    edges = fold_line_edges(classes, {"a": "T-1", "t": None}, [("a", "t"), ("t", "a")])
    assert edges == []


@pytest.mark.parametrize(
    ("node_class", "kind"),
    [
        ("CentrifugalPump", "equipment"),
        ("GateValve", "valve"),
        ("ActuatingFunction", "actuator"),
        ("ProcessControlFunction", "instrument"),
        ("FlowOutPipeOffPageConnector", "connector"),
        ("PipeTee", "inline"),
        ("ConicalStrainer", "inline"),
    ],
)
def test_kind_of_names_what_a_question_calls_the_item(node_class: str, kind: str) -> None:
    assert kind_of(node_class) == kind


def test_kind_of_refuses_a_structural_class() -> None:
    with pytest.raises(ValueError, match="node class"):
        kind_of("Sheet")


def _plant() -> nx.DiGraph[str]:
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class in _CLASSES.items():
        tag = _TAGS[node_id]
        plant.add_node(node_id, node_class=node_class, **({"tag": tag} if tag else {}))
    for source, target in _FLOW:
        plant.add_edge(source, target, relation="send_to")
    return plant


def test_the_fold_equals_the_gold_walk_on_a_hand_built_plant() -> None:
    edges = fold_line_edges(_CLASSES, _TAGS, _FLOW)
    line_items = {"TK-1", "GTV-1", "P-1", "V-1"}  # the strainer and the tee are passed through
    line_edges = {
        (str(_TAGS[e.source]), str(_TAGS[e.target])): e.n_fittings + len(e.via_tags) for e in edges
    }
    assert compare_line_views("toy", (line_items, line_edges), gold_line_view(_plant())).passed


def test_the_system_line_view_equals_the_gold_on_a_generated_v2_corpus() -> None:
    built = corpus()
    view = NetworkxGraphView("T", built.localized_sheets, built.resolution)
    system = system_line_view(build_item_graph(view))
    result = compare_line_views("T", system, gold_line_view(built.plant))
    assert result.passed, result
    assert result.n_edges_gold > 0
