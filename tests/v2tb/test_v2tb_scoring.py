"""The scorer self-tests of design 5, free and run before freeze E10.

1. the gold descriptors score 1.0 against their own gold;
2. a descriptor with the wrong side, line or class scores 0;
3. tag-only answers score as the frozen scorer does.
"""

from __future__ import annotations

import random

import pytest
from plants_b import LINE, real_plant, series_plant, toy_plant

from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome, Question, QuestionFamily
from plantgraph.qa.scoring import score_answer, score_set
from plantgraph.qa.v2tb.descriptor import (
    Descriptor,
    PlantIndex,
    Side,
    canonical_descriptor,
    encode_descriptor,
)
from plantgraph.qa.v2tb.scoring_b import (
    normalize_position,
    score_answer_b,
    score_position,
    score_valve_set,
)


def _item(class_name: str, line: str, next_to: str, side: Side) -> str:
    return encode_descriptor(
        Descriptor(class_name=class_name, line_number=line, next_to=next_to, side=side)
    )


def _question(answer_type: AnswerType, reference: object, *, answerable: bool = True) -> Question:
    return Question.model_validate(
        {
            "question_id": "q-b",
            "corpus_id": "plant0",
            "family": QuestionFamily.UPSTREAM_ISOLATION,
            "template_id": "t",
            "template_version": "1",
            "text": "x",
            "answer_type": answer_type,
            "answerable": answerable,
            "reference": reference,
            "generator_seed": 0,
        }
    )


GATE_UP_FV = _item("GateValve", LINE, "FV-1", Side.UPSTREAM)  # the toy plant's g1
BALL_UP_FV = _item("BallValve", LINE, "FV-1", Side.UPSTREAM)  # g2
GATE_UP_TANK = _item("GateValve", LINE, "T-1", Side.UPSTREAM)  # g3


def _untagged_valves() -> list[str]:
    plant = real_plant()
    return [n for n, d in plant.nodes(data=True) if not d.get("tag") and "Valve" in d["node_class"]]


# ---- self-test 1: gold scores 1.0 against itself ------------------------------------------------


def test_a_set_of_gold_descriptors_scores_one_against_itself() -> None:
    index = PlantIndex(real_plant())
    named = [canonical_descriptor(index, n) for n in _untagged_valves()]
    gold = [encode_descriptor(d) for d in named if d is not None]
    assert len(gold) > 20
    rng = random.Random(7)
    for _ in range(25):
        sample = rng.sample(gold, k=rng.randint(1, 6))
        score = score_valve_set(index, sample, sample)
        assert score.correct and score.f1 == 1.0 and score.n_unresolved == 0


def test_any_description_that_picks_out_the_right_valves_scores_one() -> None:
    index = PlantIndex(toy_plant())
    # g3 by its upstream tagged neighbour instead, and the pump by a lower-case tag
    other_way = _item("gate valve", LINE, "FV-1", Side.DOWNSTREAM)
    assert score_valve_set(index, [GATE_UP_TANK, "P-1"], [other_way, "p-1"]).correct


# ---- self-test 2: wrong side, line or class scores 0 --------------------------------------------


@pytest.mark.parametrize(
    "wrong",
    [
        _item("GateValve", LINE, "FV-1", Side.DOWNSTREAM),  # that is g3, not g1
        _item("GateValve", "2-P-9999-A1A", "FV-1", Side.UPSTREAM),
        _item("BallValve", LINE, "T-1", Side.UPSTREAM),
    ],
)
def test_a_descriptor_with_the_wrong_side_line_or_class_scores_zero(wrong: str) -> None:
    index = PlantIndex(toy_plant())
    score = score_valve_set(index, [GATE_UP_FV], [wrong])
    assert not score.correct
    assert score.f1 == 0.0


def test_an_item_that_names_no_node_makes_the_answer_wrong() -> None:
    index = PlantIndex(toy_plant())
    score = score_valve_set(index, [GATE_UP_FV], [GATE_UP_FV, "NO-SUCH-TAG"])
    assert not score.correct
    assert score.n_unresolved == 1


def test_an_item_that_names_two_nodes_is_wrong() -> None:
    index = PlantIndex(series_plant())
    # both gate valves of the series have tank T-1 as nearest tagged neighbour upstream
    ambiguous = _item("GateValve", LINE, "T-1", Side.DOWNSTREAM)
    assert score_valve_set(index, ["T-2"], [ambiguous]).n_unresolved == 1


def test_extra_and_missing_valves_make_the_set_wrong() -> None:
    index = PlantIndex(toy_plant())
    assert not score_valve_set(index, [GATE_UP_FV, BALL_UP_FV], [GATE_UP_FV]).correct
    assert not score_valve_set(index, [GATE_UP_FV], [GATE_UP_FV, BALL_UP_FV]).correct


def test_a_gold_item_that_names_no_single_node_is_a_gold_bug() -> None:
    index = PlantIndex(toy_plant())
    with pytest.raises(ValueError, match="expected the gold item"):
        score_valve_set(index, ["NO-SUCH-TAG"], [])


# ---- self-test 3: tag-only answers score as the frozen scorer does -------------------------------


def test_tag_only_answers_score_like_the_frozen_tag_set_scorer() -> None:
    plant = real_plant()
    index = PlantIndex(plant)
    tags = sorted({str(d["tag"]) for _n, d in plant.nodes(data=True) if d.get("tag")})
    unique = [t for t in tags if len(index.nodes_with_tag(t)) == 1]  # a repeated tag is a gold bug
    assert len(unique) > 30
    rng = random.Random(11)
    for _ in range(60):
        reference = rng.sample(unique, k=rng.randint(1, 5))
        answer = list(reference) if rng.random() < 0.4 else rng.sample(unique, k=rng.randint(0, 5))
        frozen = score_set(reference, answer)
        mine = score_valve_set(index, reference, answer)
        assert mine.correct == frozen.correct
        assert mine.f1 == pytest.approx(frozen.f1)


def test_other_answer_types_go_to_the_frozen_scorer_unchanged() -> None:
    index = PlantIndex(toy_plant())
    question = _question(AnswerType.TAG_SET, ["P-1", "T-1"])
    final = FinalAnswer(answer=["t-1", "P-1"], not_present=False)
    assert score_answer_b(question, Outcome.ANSWERED, final, index) == score_answer(
        question, Outcome.ANSWERED, final
    )


# ---- the wrapper: outcomes, abstention, POSITION ------------------------------------------------


def test_abstention_and_outcomes_follow_the_frozen_rules() -> None:
    index = PlantIndex(toy_plant())
    question = _question(AnswerType.VALVE_SET, [GATE_UP_FV])
    abstain = FinalAnswer(answer=None, not_present=True)
    assert not score_answer_b(question, Outcome.ANSWERED, abstain, index).correct
    assert not score_answer_b(question, Outcome.PARSE_FAILURE, None, index).correct
    unanswerable = _question(AnswerType.VALVE_SET, None, answerable=False)
    assert score_answer_b(unanswerable, Outcome.ANSWERED, abstain, index).correct
    with pytest.raises(ValueError, match="expected a final answer"):
        score_answer_b(question, Outcome.ANSWERED, None, index)


def test_a_valve_set_answer_is_scored_through_the_wrapper() -> None:
    index = PlantIndex(toy_plant())
    question = _question(AnswerType.VALVE_SET, [GATE_UP_FV, "FV-1"])
    right = FinalAnswer(answer=["fv-1", GATE_UP_FV], not_present=False)
    wrong = FinalAnswer(answer=[GATE_UP_FV], not_present=False)
    assert score_answer_b(question, Outcome.ANSWERED, right, index).correct
    assert not score_answer_b(question, Outcome.ANSWERED, wrong, index).correct


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ("NO", "NO"),
        (" nc ", "NC"),
        ("normally open", "NO"),
        ("Car-sealed closed", "CSC"),
        ("open", None),
    ],
)
def test_position_words_read_as_codes(answer: str, code: str | None) -> None:
    assert normalize_position(answer) == code


def test_position_scores_by_code() -> None:
    index = PlantIndex(toy_plant())
    question = _question(AnswerType.POSITION, "NC")
    closed = FinalAnswer(answer="normally closed", not_present=False)
    open_ = FinalAnswer(answer="NO", not_present=False)
    assert score_answer_b(question, Outcome.ANSWERED, closed, index).correct
    assert not score_answer_b(question, Outcome.ANSWERED, open_, index).correct
    with pytest.raises(ValueError, match="expected a POSITION reference"):
        score_position("open", "NO")
