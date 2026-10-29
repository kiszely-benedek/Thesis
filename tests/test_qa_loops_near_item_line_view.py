"""LOOPS_NEAR_ITEM looks through untagged fittings, and is unchanged where there are none."""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import EQUIPMENT_CLASSES, VALVE_CLASSES, NodeClass, Relation
from plantgraph.qa.questions.common import nodes_of_classes, previous_path_items
from plantgraph.qa.questions.families_dev2_local import (
    _adjacent_valves,
    loops_near_item_candidates,
)
from qa_toy_plant_dev2 import build_manifest, build_plant, build_sheets


def _with_tee_between_src1_and_gv1() -> nx.DiGraph[str]:
    """The toy plant with an untagged tee on the SRC-1 -> GV-1 pipe."""
    plant = build_plant()
    plant.remove_edge("SRC-1", "GV-1")
    plant.add_node("TEE-1", node_class=NodeClass.PIPE_TEE.value)
    plant.add_edge("SRC-1", "TEE-1", relation=Relation.SEND_TO.value)
    plant.add_edge("TEE-1", "GV-1", relation=Relation.SEND_TO.value)
    return plant


def _old_adjacent_valves(plant: nx.DiGraph[str], item_id: str) -> set[tuple[str, tuple[str, str]]]:
    """The rule before the line view: valves exactly one `send_to` edge away."""
    found = {(v, (item_id, v)) for v in plant.successors(item_id)}
    found |= {(v, (v, item_id)) for v in plant.predecessors(item_id)}
    return {
        (v, edge)
        for v, edge in found
        if plant.edges[edge]["relation"] == Relation.SEND_TO.value
        and plant.nodes[v]["node_class"] in VALVE_CLASSES
    }


def test_on_a_plant_without_fittings_the_rule_equals_the_old_one() -> None:
    plant = build_plant()
    for item_id in nodes_of_classes(plant, EQUIPMENT_CLASSES):
        new = {(v, edges[0]) for v, edges in _adjacent_valves(plant, item_id)}
        assert all(len(edges) == 1 for _, edges in _adjacent_valves(plant, item_id))
        assert new == _old_adjacent_valves(plant, item_id), item_id


def test_a_tee_between_item_and_valve_does_not_hide_the_valve() -> None:
    plant = _with_tee_between_src1_and_gv1()

    valves = _adjacent_valves(plant, "SRC-1")

    assert valves == [("GV-1", [("SRC-1", "TEE-1"), ("TEE-1", "GV-1")])]


def test_previous_path_items_lists_the_item_upstream_of_a_tee_in_flow_order() -> None:
    plant = _with_tee_between_src1_and_gv1()

    hops = previous_path_items(plant, "GV-1")

    assert [(h.item_id, h.via) for h in hops] == [("SRC-1", ("TEE-1",))]


def test_the_question_survives_the_tee_and_its_evidence_counts_the_fitting() -> None:
    plant = _with_tee_between_src1_and_gv1()
    sheets = [
        SheetGraph(
            sheet_id=s.sheet_id,
            graph=plant.subgraph(
                [*s.graph.nodes, *(["TEE-1"] if s.sheet_id == "S1" else [])]
            ).copy(),
        )
        for s in build_sheets(build_plant())
    ]

    questions = loops_near_item_candidates(plant, build_manifest(), sheets, corpus_id="toy", seed=0)

    src1 = [q for q in questions if q.anchors == ["SRC-1"]]
    assert len(src1) == 1 and src1[0].reference == ["FIC-1"]
