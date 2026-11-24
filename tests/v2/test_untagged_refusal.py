"""Task T6b, gold side of scope R (design 17.15 S2, S4): one refusal rule for untagged valves.

The plants are hand-built on one sheet: a node has a `tag` only when it prints one, as on a v2.2
plant whose document leaves its manual valves untagged.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.qa.harness.gold import build_gold_scoring
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.common import is_path_item, next_path_items
from plantgraph.qa.questions.families_flow import (
    flow_path_candidates,
    neighbours_downstream_candidates,
)
from plantgraph.qa.questions.families_heldout_paths import valves_on_path_candidates
from plantgraph.qa.questions.untagged import (
    SCOPE_R_UNAVAILABLE_FAMILIES,
    UNTAGGED_MARKER,
    RefusedShare,
    carries_marker,
    printed_name,
    refuse_untagged,
)

_GATE = NodeClass.GATE_VALVE.value
_TEE = NodeClass.PIPE_TEE.value


def _plant(
    nodes: dict[str, tuple[str, str | None]], pipes: list[tuple[str, str]]
) -> nx.DiGraph[str]:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node, (node_class, tag) in nodes.items():
        graph.add_node(node, node_class=node_class, unit_id="1", **({"tag": tag} if tag else {}))
    graph.add_edges_from(pipes, relation=Relation.SEND_TO.value)
    return graph


def _one_sheet(plant: nx.DiGraph[str]) -> tuple[SplitManifest, list[SheetGraph]]:
    manifest = SplitManifest(source="t6b", sheet_files=["S1"], connector_pairs=[])
    return manifest, [SheetGraph(sheet_id="S1", graph=plant)]


def _candidates(plant: nx.DiGraph[str], builder) -> list[Question]:  # type: ignore[no-untyped-def]
    manifest, sheets = _one_sheet(plant)
    return builder(plant, manifest, sheets, corpus_id="T6B", seed=1)


#: pump -> valve -> vessel, the valve printing a tag or not
def _line(valve_tag: str | None) -> nx.DiGraph[str]:
    nodes = {
        "p": (NodeClass.CENTRIFUGAL_PUMP.value, "P-101"),
        "v": (_GATE, valve_tag),
        "k": (NodeClass.PRESSURE_VESSEL.value, "V-101"),
    }
    return _plant(nodes, [("p", "v"), ("v", "k")])


#: two routes from the pump to the vessel, through gate valve `a` or `b`
def _diamond(tag_a: str | None, tag_b: str | None) -> nx.DiGraph[str]:
    nodes = {
        "p": (NodeClass.CENTRIFUGAL_PUMP.value, "P-101"),
        "t1": (_TEE, None),
        "a": (_GATE, tag_a),
        "b": (_GATE, tag_b),
        "t2": (_TEE, None),
        "k": (NodeClass.PRESSURE_VESSEL.value, "V-101"),
    }
    pipes = [("p", "t1"), ("t1", "a"), ("t1", "b"), ("a", "t2"), ("b", "t2"), ("t2", "k")]
    return _plant(nodes, pipes)


# ---- the helper, the filter and the constants ----------------------------------------------------


def test_the_isolation_families_are_pre_registered_unavailable() -> None:
    assert set(SCOPE_R_UNAVAILABLE_FAMILIES) == {
        QuestionFamily.UPSTREAM_ISOLATION,
        QuestionFamily.DOWNSTREAM_ISOLATION,
    }


def test_a_printed_name_is_the_tag_or_the_fixed_marker() -> None:
    plant = _line(None)
    assert printed_name(plant, "p") == "P-101"
    assert printed_name(plant, "v") == UNTAGGED_MARKER


def test_the_refused_share_counts_candidates_and_handles_none() -> None:
    assert RefusedShare(rule="x", candidates=4, refused=2).share == 0.5
    assert RefusedShare(rule="x", candidates=0, refused=0).share == 0.0


def test_the_filter_drops_marked_questions_and_counts_them_per_family() -> None:
    candidates = {
        QuestionFamily.NEIGHBOURS_DOWNSTREAM: _candidates(
            _line(None), neighbours_downstream_candidates
        )
        + _candidates(_line("GTV-1"), neighbours_downstream_candidates),
        QuestionFamily.FLOW_PATH: _candidates(_line("GTV-1"), flow_path_candidates),
    }
    kept, shares = refuse_untagged(candidates)
    neighbours = shares[QuestionFamily.NEIGHBOURS_DOWNSTREAM]
    assert (neighbours.candidates, neighbours.refused) == (
        3,
        1,
    )  # 1 + 2 candidates; the untagged line's pump is refused
    assert shares[QuestionFamily.FLOW_PATH].refused == 0
    assert kept[QuestionFamily.FLOW_PATH] == candidates[QuestionFamily.FLOW_PATH]
    assert not any(carries_marker(q) for qs in kept.values() for q in qs)


def test_a_plant_with_no_untagged_node_loses_nothing() -> None:
    candidates = {
        QuestionFamily.FLOW_PATH: _candidates(_diamond("GTV-1", "GTV-2"), flow_path_candidates)
    }
    kept, shares = refuse_untagged(candidates)
    assert kept == candidates and shares[QuestionFamily.FLOW_PATH].refused == 0


# ---- behaviour of the families (criterion 4) -----------------------------------------------------


def test_an_untagged_valve_on_the_route_is_counted_by_valves_on_path() -> None:
    questions = _candidates(_line(None), valves_on_path_candidates)
    assert [(q.anchors, q.reference) for q in questions] == [(["P-101", "V-101"], 1)]
    assert not carries_marker(questions[0])


def test_an_untagged_valve_directly_downstream_refuses_the_candidate() -> None:
    plant = _line(None)
    (pump,) = [
        q for q in _candidates(plant, neighbours_downstream_candidates) if q.anchors == ["P-101"]
    ]
    # the valve is the pump's neighbour; it is not looked through to the vessel behind it
    assert pump.reference == [UNTAGGED_MARKER]
    kept, _ = refuse_untagged({QuestionFamily.NEIGHBOURS_DOWNSTREAM: [pump]})
    assert kept[QuestionFamily.NEIGHBOURS_DOWNSTREAM] == []


def test_a_flow_path_whose_reference_holds_an_untagged_valve_is_refused() -> None:
    questions = _candidates(_line(None), flow_path_candidates)
    assert questions and all(carries_marker(q) for q in questions)
    kept, shares = refuse_untagged({QuestionFamily.FLOW_PATH: questions})
    assert kept[QuestionFamily.FLOW_PATH] == []
    assert shares[QuestionFamily.FLOW_PATH].refused == len(questions)


def test_two_equal_length_fully_tagged_routes_do_not_refuse_the_pair() -> None:
    questions = _candidates(_diamond("GTV-1", "GTV-2"), flow_path_candidates)
    kept, _ = refuse_untagged({QuestionFamily.FLOW_PATH: questions})
    assert questions and kept[QuestionFamily.FLOW_PATH] == questions


def test_an_untagged_valve_stays_a_path_item_and_stops_the_walk() -> None:
    plant = _line(None)
    assert is_path_item(plant, "v")
    assert [hop.item_id for hop in next_path_items(plant, "p")] == ["v"]


# ---- the harness gold ---------------------------------------------------------------------------


class _NoConnectors:
    """A graph view with no items: the gold's connector tags come out empty."""

    def items(self) -> list[object]:
        return []


def test_a_path_answer_that_skips_an_untagged_valve_is_invalid() -> None:
    # a tee on each side of the valve, so the edges run through unnamed fittings
    nodes = {
        "p": (NodeClass.CENTRIFUGAL_PUMP.value, "P-101"),
        "t1": (_TEE, None),
        "v": (_GATE, None),
        "t2": (_TEE, None),
        "k": (NodeClass.PRESSURE_VESSEL.value, "V-101"),
    }
    plant = _plant(nodes, [("p", "t1"), ("t1", "v"), ("v", "t2"), ("t2", "k")])
    edges = build_gold_scoring(plant, _NoConnectors()).valid_edges  # type: ignore[arg-type]
    assert ("P-101", "V-101") not in edges and edges == frozenset()


def test_a_fully_tagged_route_is_valid() -> None:
    nodes = {
        "p": (NodeClass.CENTRIFUGAL_PUMP.value, "P-101"),
        "t1": (_TEE, None),
        "v": (_GATE, "GTV-1"),
        "t2": (_TEE, None),
        "k": (NodeClass.PRESSURE_VESSEL.value, "V-101"),
    }
    plant = _plant(nodes, [("p", "t1"), ("t1", "v"), ("v", "t2"), ("t2", "k")])
    edges = build_gold_scoring(plant, _NoConnectors()).valid_edges  # type: ignore[arg-type]
    assert edges == frozenset({("P-101", "GTV-1"), ("GTV-1", "V-101")})
