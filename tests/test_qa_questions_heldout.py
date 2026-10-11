"""The six held-out families on the hand-built toy plant of `qa_toy_plant_heldout.py`.

Every reference answer, evidence and `k` (sheet boundaries crossed by the evidence) is counted
by hand from that module's drawing. A few are also compared with an independent networkx oracle.
"""

from __future__ import annotations

from collections.abc import Callable

import networkx as nx
import pytest

from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.common import send_to_successors
from plantgraph.qa.questions.families_heldout import HELDOUT_GENERATORS, heldout_candidates
from plantgraph.qa.questions.families_heldout_paths import _valve_count_ranges
from qa_toy_plant_heldout import NODES, build_manifest, build_plant, build_sheets

_PLANT = build_plant()
_MANIFEST = build_manifest()
_SHEETS = build_sheets(_PLANT)
F = QuestionFamily


def _make(family: QuestionFamily, seed: int = 0) -> list[Question]:
    generator: Callable[..., list[Question]] = HELDOUT_GENERATORS[family]
    return generator(_PLANT, _MANIFEST, _SHEETS, corpus_id="ho", seed=seed)


def _one(questions: list[Question], *anchors: str) -> Question:
    matching = [q for q in questions if q.anchors == list(anchors)]
    assert len(matching) == 1, (
        f"expected one candidate anchored on {anchors}, found {len(matching)}"
    )
    return matching[0]


def _over_seeds(family: QuestionFamily) -> list[Question]:
    """Candidates of eight seeds together, each question once (one target per bin is random)."""
    by_id = {q.question_id: q for seed in range(8) for q in _make(family, seed)}
    return list(by_id.values())


def _anchors(questions: list[Question]) -> set[tuple[str, ...]]:
    return {tuple(q.anchors) for q in questions}


# --- FIRST_MEETING_POINT ---------------------------------------------------------------------


def test_first_meeting_point_finds_the_one_item_where_two_flows_join() -> None:
    questions = _make(F.FIRST_MEETING_POINT)

    question = _one(questions, "A1", "B1")
    assert question.reference == "M1"
    assert question.answer_type is AnswerType.TAG
    assert question.evidence_tags == sorted(["A1", "GV1", "B1", "CHV1", "M1"])
    assert (question.k, question.k_connector, question.k_identity) == (2, 2, 0)


def test_first_meeting_point_rejects_two_incomparable_meeting_points() -> None:
    # A2 and B2 both feed Z1 and Z2, and neither of those reaches the other
    assert _anchors(_make(F.FIRST_MEETING_POINT)) == {("A1", "B1")}


# --- DOWNSTREAM_ISOLATION --------------------------------------------------------------------


def test_downstream_isolation_stops_at_the_first_operated_valve_and_passes_check_valves() -> None:
    questions = _make(F.DOWNSTREAM_ISOLATION)

    a1 = _one(questions, "A1")
    assert (a1.reference, a1.evidence_tags, a1.k) == (["GV1"], ["A1", "GV1"], 0)
    b1 = _one(questions, "B1")  # CHV1 is a check valve: the walk goes on to BV1
    assert b1.reference == ["BV1"]
    assert b1.evidence_tags == ["B1", "BV1", "CHV1", "M1", "P1"]
    assert b1.k == 1  # CHV1 -> M1 crosses from S1 to S2
    assert _one(questions, "M1").reference == ["BV1"]
    assert _one(questions, "P1").reference == ["BV1"]


def test_downstream_isolation_needs_a_valve_on_every_route() -> None:
    # D1 has a route D1 -> Q1 -> E1 with no operated valve; T2, P2 and the sinks end unvalved
    assert _anchors(_make(F.DOWNSTREAM_ISOLATION)) == {("A1",), ("B1",), ("M1",), ("P1",)}


# --- VALVES_ON_PATH --------------------------------------------------------------------------

# valves strictly between the two items, counted by hand for some pairs that can be asked
_VALVES_BETWEEN = {
    ("A1", "M1"): 1,
    ("A1", "P1"): 1,
    ("A1", "T2"): 2,
    ("B1", "M1"): 1,  # CHV1 is a valve too
    ("B1", "T2"): 2,
    ("M1", "T2"): 1,
    ("A2", "Z1"): 0,
}


def _valve_counts_by_oracle(source: str, target: str) -> set[int]:
    """Valve counts of every shortest path, found by listing them all with networkx."""
    valve_classes = {"GlobeValve", "BallValve", "CheckValve"}
    paths = nx.all_shortest_paths(_PLANT, source, target)
    return {sum(_PLANT.nodes[n]["node_class"] in valve_classes for n in p[1:-1]) for p in paths}


def test_valves_on_path_counts_match_the_hand_table_and_the_oracle() -> None:
    asked = {
        (q.anchors[0], q.anchors[1]): q.reference
        for seed in range(8)
        for q in _make(F.VALVES_ON_PATH, seed)
    }

    for pair, count in _VALVES_BETWEEN.items():
        assert asked[pair] == count, pair
    for (source, target), reference in asked.items():
        assert {reference} == _valve_counts_by_oracle(source, target), (source, target)


def test_valves_on_path_rejects_a_pair_whose_shortest_paths_differ() -> None:
    # D1 -> BV2 -> E1 holds one valve, D1 -> Q1 -> E1 none: no question may ask about D1 and E1
    successors = {n: send_to_successors(_PLANT, n) for n in _PLANT.nodes}
    ranges = _valve_count_ranges(_PLANT, successors, "D1")
    assert ranges["E1"] == (0, 1)
    for seed in range(8):
        assert ("D1", "E1") not in _anchors(_make(F.VALVES_ON_PATH, seed))


def test_valves_on_path_evidence_is_the_shortest_path() -> None:
    questions = _over_seeds(F.VALVES_ON_PATH)

    a1_t2 = next(q for q in questions if q.anchors == ["A1", "T2"])
    assert a1_t2.evidence_tags == sorted(["A1", "GV1", "M1", "P1", "BV1", "T2"])
    assert a1_t2.k == 2  # GV1 -> M1 and BV1 -> T2


# --- FEEDING_UNITS ---------------------------------------------------------------------------


def test_feeding_units_lists_the_units_that_send_flow_in() -> None:
    questions = _make(F.FEEDING_UNITS)

    assert {q.anchors[0]: q.reference for q in questions} == {
        "2": ["1"],
        "3": ["2"],
        "5": ["4"],
    }  # unit 1 receives nothing from another unit, so it has no question
    assert _one(questions, "3").k == 1  # BV1 -> T2 is cut
    assert _one(questions, "2").k == 0
    assert all(q.answer_type is AnswerType.UNIT_SET for q in questions)


# --- UNITS_REACHED ---------------------------------------------------------------------------


def test_units_reached_counts_other_units_downstream() -> None:
    questions = _make(F.UNITS_REACHED)

    expected = {
        "A1": 2,
        "B1": 2,
        "M1": 2,
        "P1": 1,
        "T2": 0,
        "P2": 0,
        "A2": 1,
        "B2": 1,
        "D1": 0,
        "Q1": 0,
    }
    assert {q.anchors[0]: q.reference for q in questions} == expected
    assert _one(questions, "A1").k == 2  # GV1 -> M1 and BV1 -> T2 are in the BFS tree
    assert _one(questions, "T2").k == 0
    assert (("E2",)) not in _anchors(questions)  # no descendant: not a candidate


# --- ROUTE_AVOIDING --------------------------------------------------------------------------


def test_route_avoiding_says_yes_when_a_detour_exists() -> None:
    question = _one(_over_seeds(F.ROUTE_AVOIDING), "D1", "E1", "BV2")

    assert question.reference == "yes"  # D1 -> Q1 -> E1 avoids BV2
    assert question.answer_type is AnswerType.BOOLEAN
    assert question.evidence_tags == ["D1", "E1", "Q1"]
    assert question.k == 0


def test_route_avoiding_says_no_with_the_whole_walk_as_evidence() -> None:
    question = _one(_over_seeds(F.ROUTE_AVOIDING), "A1", "M1", "GV1")

    assert question.reference == "no"
    assert question.evidence_tags == ["A1"]  # without GV1, A1 reaches nothing


@pytest.mark.parametrize("seed", range(8))
def test_route_avoiding_agrees_with_an_independent_oracle(seed: int) -> None:
    questions = _make(F.ROUTE_AVOIDING, seed)
    assert {q.reference for q in questions} == {"yes", "no"}
    for question in questions:
        source, target, removed = question.anchors
        cut_plant = _PLANT.copy()
        cut_plant.remove_node(removed)
        reachable = nx.has_path(cut_plant, source, target)
        assert question.reference == ("yes" if reachable else "no"), question.anchors
        assert removed in nx.shortest_path(_PLANT, source, target)[1:-1]


# --- all six ---------------------------------------------------------------------------------


def test_every_heldout_question_is_answerable_with_an_existing_answer_type() -> None:
    candidates = heldout_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id="ho", seed=0)

    assert set(candidates) == set(HELDOUT_GENERATORS)
    for family, questions in candidates.items():
        assert questions, family
        for question in questions:
            assert question.answerable and question.k is not None and question.u is not None
            assert question.reference is not None
            assert question.family is family


def test_candidates_are_byte_identical_for_the_same_seed() -> None:
    first = heldout_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id="ho", seed=5)
    second = heldout_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id="ho", seed=5)

    assert {f: [q.model_dump_json() for q in qs] for f, qs in first.items()} == {
        f: [q.model_dump_json() for q in qs] for f, qs in second.items()
    }
    assert len(NODES) == len(_PLANT)  # the toy is what the drawing says
