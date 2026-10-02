"""The six dev-new families on the hand-built toy plant of `qa_toy_plant_dev2.py`.

Every reference answer, `k` (sheet boundaries crossed by the evidence) and `u` (unit boundaries)
below is counted by hand from that module's drawing.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.availability import KBin, k_bin_of
from plantgraph.qa.questions.families_dev2_local import (
    instruments_of_item_candidates,
    loops_near_item_candidates,
    same_unit_candidates,
)
from plantgraph.qa.questions.families_dev2_reach import (
    connected_candidates,
    downstream_in_unit_candidates,
    upstream_sources_candidates,
)
from plantgraph.qa.questions.sample import draw_bin
from qa_toy_plant_dev2 import EQUIPMENT_TAGS, UNIT_OF, build_manifest, build_plant, build_sheets

_CORPUS = "dev2"
_PLANT = build_plant()
_MANIFEST = build_manifest()
_SHEETS = build_sheets(_PLANT)

Generator = Callable[..., list[Question]]
_ALL_GENERATORS: list[Generator] = [
    connected_candidates,
    downstream_in_unit_candidates,
    instruments_of_item_candidates,
    upstream_sources_candidates,
    same_unit_candidates,
    loops_near_item_candidates,
]


def _make(generator: Generator) -> list[Question]:
    return generator(_PLANT, _MANIFEST, _SHEETS, corpus_id=_CORPUS, seed=0)


def _one(questions: list[Question], *anchors: str) -> Question:
    matching = [q for q in questions if q.anchors == list(anchors)]
    assert len(matching) == 1, (
        f"expected one candidate anchored on {anchors}, found {len(matching)}"
    )
    return matching[0]


def _summary(questions: list[Question]) -> dict[str, tuple[object, int | None, int | None]]:
    """First anchor -> (reference, k, u), for families with one candidate per first anchor."""
    assert len({q.anchors[0] for q in questions}) == len(questions)
    return {q.anchors[0]: (q.reference, q.k, q.u) for q in questions}


# --- CONNECTED --------------------------------------------------------------------------------

_REACHES = {
    "SRC-1": {"GV-1", "P-1", "V-1", "CHV-1", "TK-2", "P-2", "E-2"},
    "SRC-2": {"BV-1", "V-1", "CHV-1", "TK-2", "P-2", "E-2"},
    "P-1": {"V-1", "CHV-1", "TK-2", "P-2", "E-2"},
    "V-1": {"CHV-1", "TK-2", "P-2", "E-2"},
    "TK-2": {"P-2", "E-2"},
    "P-2": {"E-2"},
    "E-2": set(),
    "ISL-1": set(),
}


def test_connected_reference_is_yes_exactly_when_the_target_is_downstream() -> None:
    questions = _make(connected_candidates)

    for question in questions:
        source, target = question.anchors
        expected = "yes" if target in _REACHES[source] else "no"
        assert question.reference == expected, question.text
        assert question.answer_type is AnswerType.BOOLEAN
        assert target in EQUIPMENT_TAGS and target != source
    assert len(questions) == 17  # 9 yes (one per source and k-bin) + 8 no (one per source)
    assert sum(q.reference == "yes" for q in questions) == 9


def test_connected_text_names_target_then_source() -> None:
    question = _make(connected_candidates)[0]
    source, target = question.anchors

    assert question.text == f"Can process flow reach {target} from {source}?"


def test_connected_yes_evidence_is_the_shortest_path_and_counts_its_crossings() -> None:
    questions = _make(connected_candidates)
    yes = [q for q in questions if q.anchors[0] == "SRC-1" and q.reference == "yes"]

    # SRC-1 -> GV-1 -> P-1 crosses once (bin 1); every farther equipment item crosses twice (bin 2)
    assert sorted(q.k for q in yes if q.k is not None) == [1, 2]
    two = next(q for q in yes if q.k == 2)
    assert two.anchors[1] in {"TK-2", "P-2", "E-2"}


def test_connected_no_evidence_is_the_whole_walk_from_the_source() -> None:
    questions = _make(connected_candidates)
    no = next(q for q in questions if q.anchors[0] == "SRC-1" and q.reference == "no")

    assert no.anchors[1] in {"SRC-2", "ISL-1"}  # the only equipment SRC-1 cannot reach
    assert no.evidence_tags == sorted(
        ["SRC-1", "GV-1", "P-1", "V-1", "CHV-1", "TK-2", "P-2", "E-2"]
    )
    # tree edges GV-1->P-1 and CHV-1->TK-2 cross sheets; only CHV-1->TK-2 crosses units
    assert (no.k, no.k_connector, no.k_identity, no.u) == (2, 2, 0, 1)


def test_connected_source_with_no_downstream_has_only_a_no_question_with_k_zero() -> None:
    questions = _make(connected_candidates)
    lone = [q for q in questions if q.anchors[0] == "E-2"]

    assert [(q.reference, q.k, q.evidence_tags) for q in lone] == [("no", 0, ["E-2"])]


# --- DOWNSTREAM_IN_UNIT -----------------------------------------------------------------------


def test_downstream_in_unit_stops_at_the_unit_boundary() -> None:
    questions = _make(downstream_in_unit_candidates)

    assert _summary(questions) == {
        # SRC-1 -> GV-1 -> P-1 -> V-1 -> CHV-1; CHV-1 -> TK-2 leaves unit 1 and is not walked
        "SRC-1": (["CHV-1", "GV-1", "P-1", "V-1"], 1, 0),
        "SRC-2": (["BV-1", "CHV-1", "V-1"], 1, 0),
        "P-1": (["CHV-1", "V-1"], 0, 0),
        "V-1": (["CHV-1"], 0, 0),
        "TK-2": (["E-2", "P-2"], 0, 0),
        "P-2": (["E-2"], 0, 0),
    }


def test_downstream_in_unit_text_and_anchors_name_the_own_unit_of_the_item() -> None:
    question = _one(_make(downstream_in_unit_candidates), "SRC-1", "1")

    assert question.text == (
        "Which equipment items and valves in unit 1 receive flow from SRC-1, "
        "directly or indirectly?"
    )
    assert question.answer_type is AnswerType.TAG_SET


# --- INSTRUMENTS_OF_ITEM ----------------------------------------------------------------------


def test_instruments_of_item_lists_the_measuring_sensors() -> None:
    questions = _make(instruments_of_item_candidates)

    assert _summary(questions) == {
        "P-1": (["FT-1", "FT-3"], 0, 0),
        "V-1": (["FT-2"], 0, 0),
    }
    assert _one(questions, "P-1").text == "Which instruments measure P-1?"


# --- UPSTREAM_SOURCES -------------------------------------------------------------------------


def test_upstream_sources_keeps_only_ancestors_nothing_flows_into() -> None:
    questions = _make(upstream_sources_candidates)

    # k counts the breadth-first tree's cut edges; u is 1 once CHV-1 -> TK-2 is in the tree
    assert _summary(questions) == {
        "P-1": (["SRC-1"], 1, 0),
        "V-1": (["SRC-1", "SRC-2"], 2, 0),
        "TK-2": (["SRC-1", "SRC-2"], 3, 1),
        "P-2": (["SRC-1", "SRC-2"], 3, 1),
        "E-2": (["SRC-1", "SRC-2"], 3, 1),
    }


# --- SAME_UNIT --------------------------------------------------------------------------------


def test_same_unit_gives_each_item_one_yes_and_one_no_partner() -> None:
    questions = _make(same_unit_candidates)

    assert len(questions) == 16
    for tag in EQUIPMENT_TAGS:
        answers = sorted(str(q.reference) for q in questions if q.anchors[0] == tag)
        assert answers == ["no", "yes"], tag


def test_same_unit_reference_matches_the_units_and_evidence_is_the_two_items() -> None:
    for question in _make(same_unit_candidates):
        first, second = question.anchors
        assert question.reference == ("yes" if UNIT_OF[first] == UNIT_OF[second] else "no")
        assert first != second
        assert question.evidence_tags == sorted([first, second])
        assert (question.k, question.u) == (0, 0)


# --- LOOPS_NEAR_ITEM --------------------------------------------------------------------------


def test_loops_near_item_follows_valve_actuator_controller() -> None:
    questions = _make(loops_near_item_candidates)

    assert _summary(questions) == {
        "SRC-1": (["FIC-1"], 1, 0),  # FIC-1 -> FV-1 crosses
        "P-1": (["FIC-1"], 2, 0),  # plus GV-1 -> P-1
        "SRC-2": (["FIC-2"], 1, 0),
        "V-1": (["FIC-2"], 2, 0),  # CHV-1 beside V-1 has no loop; BV-1 has FIC-2
    }
    assert _one(questions, "P-1").text == (
        "Which control loops act on valves directly connected to P-1?"
    )


# --- sampling, determinism --------------------------------------------------------------------


def test_the_sampler_alternates_yes_and_no_inside_a_bin() -> None:
    questions = _make(connected_candidates)
    in_bin_zero = [q for q in questions if k_bin_of(q) is KBin.K0]
    assert sum(q.reference == "yes" for q in in_bin_zero) == 3  # fewer yes than no here
    assert sum(q.reference == "no" for q in in_bin_zero) == 4

    for seed in range(10):
        drawn = draw_bin({QuestionFamily.CONNECTED: in_bin_zero}, 6, random.Random(seed))
        assert sum(q.reference == "yes" for q in drawn) == 3, seed
        assert sum(q.reference == "no" for q in drawn) == 3, seed


def test_the_same_seed_gives_identical_candidates_in_every_family() -> None:
    for generator in _ALL_GENERATORS:
        first = [q.model_dump_json() for q in _make(generator)]
        second = [q.model_dump_json() for q in _make(generator)]
        assert first == second, generator.__name__


def test_question_ids_are_unique_within_each_family() -> None:
    for generator in _ALL_GENERATORS:
        ids = [q.question_id for q in _make(generator)]
        assert len(ids) == len(set(ids)), generator.__name__
