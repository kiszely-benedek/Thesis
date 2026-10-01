"""QA-T7 families on the hand-built toy plant of `qa_toy_plant_t7.py`: reference answers and k."""

from __future__ import annotations

import re

import networkx as nx

from plantgraph.qa.models import Question
from plantgraph.qa.questions.families_abstain import (
    no_path_candidates,
    unanswerable_tag_candidates,
)
from plantgraph.qa.questions.families_aggregate import (
    class_plural,
    count_in_unit_candidates,
    cross_unit_candidates,
)
from plantgraph.qa.questions.families_isolation import upstream_isolation_candidates
from qa_toy_plant_t7 import build_manifest, build_plant, build_sheets

_CORPUS = "toy7"
_PLANT = build_plant()
_MANIFEST = build_manifest()
_SHEETS = build_sheets(_PLANT)
_WELL_FORMED_TAG = re.compile(r"^[A-Z]+-\d+-\d+$")


def _by_anchors(questions: list[Question], *anchors: str) -> Question:
    matching = [q for q in questions if q.anchors == list(anchors)]
    assert len(matching) == 1, f"expected one candidate anchored on {anchors}"
    return matching[0]


def test_upstream_isolation_passes_check_valves_and_stops_at_operated_ones() -> None:
    questions = upstream_isolation_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=0)
    vessel = _by_anchors(questions, "V-1-1")

    # Upstream of V-1-1: GV-1-1 (operated, stop) and CHV-1-1 (check valve, pass
    # through) then GV-1-2 (operated, stop).
    assert vessel.reference == ["GV-1-1", "GV-1-2"]
    # Walked edges: GV-1-1->V-1-1 (cut), CHV-1-1->V-1-1, GV-1-2->CHV-1-1: k=1.
    assert vessel.k == 1


def test_upstream_isolation_skips_items_with_a_route_that_has_no_valve() -> None:
    questions = upstream_isolation_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=0)
    anchored_on = {q.anchors[0] for q in questions}

    # P-1-1 is fed straight from TK-1-1 (no valve); TK-1-1 and TK-1-2 have no upstream at all.
    assert not anchored_on & {"P-1-1", "TK-1-1", "TK-1-2"}
    # TK-2-1 is fed through V-1-1, whose own routes all have an operated valve.
    assert _by_anchors(questions, "TK-2-1").reference == ["GV-1-1", "GV-1-2"]


def test_cross_unit_lists_receiving_units_and_counts_the_cut_edge() -> None:
    questions = cross_unit_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=0)

    # Only unit 1 sends flow to another unit (V-1-1 -> TK-2-1, a cut edge);
    # unit 2 sends nowhere, so its empty answer is not a candidate.
    assert [q.anchors for q in questions] == [["1"]]
    assert questions[0].reference == ["2"]
    assert questions[0].k == 1


def test_count_in_unit_counts_by_class_and_k_counts_cut_edges_inside_the_unit() -> None:
    questions = count_in_unit_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=0)

    tanks = _by_anchors(questions, "1", "Tank")
    assert tanks.reference == 2
    assert tanks.text == "How many tanks are in unit 1?"
    # Unit-1 send_to edges that are cut: GV-1-1->V-1-1 and TK-1-2->GV-1-2
    # (V-1-1->TK-2-1 leaves the unit, so it is not inside it): k=2.
    assert tanks.k == 2

    assert _by_anchors(questions, "1", "GlobeValve").reference == 2
    # Unit 2 holds one tank and no edge at all.
    unit_two = _by_anchors(questions, "2", "Tank")
    assert (unit_two.reference, unit_two.k) == (1, 0)


def test_class_plural_splits_camel_case() -> None:
    assert class_plural("HeatExchanger") == "heat exchangers"
    assert class_plural("Tank") == "tanks"


def test_unanswerable_tags_are_well_formed_absent_and_have_no_k() -> None:
    questions = unanswerable_tag_candidates(_PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=0)
    plant_tags = {data["tag"] for _, data in _PLANT.nodes(data=True)}

    assert questions
    for question in questions:
        absent = question.anchors[-1]
        assert _WELL_FORMED_TAG.match(absent)
        assert absent not in plant_tags
        assert (question.answerable, question.reference, question.k) == (False, None, None)
    # Every (prefix, unit) group gets its next tag: the unit-1 tank group gives TK-1-3.
    assert "TK-1-3" in {q.anchors[-1] for q in questions}


def test_unanswerable_tags_depend_on_the_seed_only() -> None:
    def ids(seed: int) -> list[str]:
        found = unanswerable_tag_candidates(
            _PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=seed, max_tags=2
        )
        return [q.question_id for q in found]

    assert ids(3) == ids(3)


def test_no_path_pairs_are_present_and_truly_unreachable() -> None:
    questions = no_path_candidates(
        _PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=0, pairs_per_source=100
    )
    flow = nx.DiGraph(_PLANT.edges)

    assert questions
    for question in questions:
        source, target = question.anchors
        assert source in _PLANT and target in _PLANT
        assert not nx.has_path(flow, source, target)
        assert (question.answerable, question.k) == (False, None)
    # TK-2-1 is a sink, so it cannot reach TK-1-1; the reverse path exists and is not a question.
    pairs = {tuple(q.anchors) for q in questions}
    assert ("TK-2-1", "TK-1-1") in pairs
    assert ("TK-1-1", "TK-2-1") not in pairs
