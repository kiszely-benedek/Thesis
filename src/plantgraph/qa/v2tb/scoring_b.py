"""Scoring the two V2T-B answer types, `VALVE_SET` and `POSITION` (design 5).

A `VALVE_SET` answer lists tags and descriptors (`descriptor.py`). Each item is **resolved** to the
plant nodes it names, and the answer is right iff the resolved node set equals the gold node set.
So any description that picks out exactly the right valve counts, not only the canonical string:
the scorer judges identification, not phrasing.

An item that resolves to no node, or to two or more, is wrong, and makes the whole answer wrong.
Every other answer type goes to the frozen `qa/scoring.py` unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome, Question
from plantgraph.qa.scoring import ScoredAnswer, normalize_scalar, score_answer
from plantgraph.qa.v2tb.descriptor import PlantIndex, decode_item, resolve_descriptor
from plantgraph.qa.v2tb.visible import POSITION_CODES

#: Plain-language spellings of the six position codes, folded like tags.
_POSITION_WORDS = {
    "NORMALLY OPEN": "NO",
    "NORMALLY CLOSED": "NC",
    "LOCKED OPEN": "LO",
    "LOCKED CLOSED": "LC",
    "CAR SEALED OPEN": "CSO",
    "CAR-SEALED OPEN": "CSO",
    "CAR SEALED CLOSED": "CSC",
    "CAR-SEALED CLOSED": "CSC",
}


class ValveSetScore(BaseModel):
    """The verdict on one `VALVE_SET` answer, with the numbers a report needs."""

    model_config = ConfigDict(frozen=True)

    correct: bool
    #: Set F1 over resolved nodes; an item that did not resolve to one node counts as spurious.
    f1: float
    #: Answered items that resolved to zero nodes, or to two or more.
    n_unresolved: int


def normalize_position(value: str) -> str | None:
    """The position code a string stands for (`NO`, `normally open`, ...), else `None`."""
    word = normalize_scalar(value)
    if word in POSITION_CODES:
        return word
    return _POSITION_WORDS.get(word)


def score_position(reference: str, answer: str) -> bool:
    """Exact match on the position code; an unreadable answer is wrong, not an error.

    Raises:
        ValueError: `reference` is not one of the six codes (the generator always writes one).
    """
    expected = normalize_position(reference)
    if expected is None:
        raise ValueError(f"expected a POSITION reference in {POSITION_CODES}, found {reference!r}")
    return expected == normalize_position(answer)


def resolve_item(index: PlantIndex, item: str) -> frozenset[str]:
    """The plant nodes one answer item names; a malformed descriptor names none."""
    try:
        decoded = decode_item(item)
    except ValueError:
        return frozenset()
    if isinstance(decoded, str):
        return index.nodes_with_tag(decoded)
    return resolve_descriptor(index, decoded)


def reference_nodes(index: PlantIndex, reference: Iterable[str]) -> frozenset[str]:
    """The gold node set of a reference list.

    Raises:
        ValueError: a gold item does not resolve to exactly one node (a bug on the gold side).
    """
    nodes: set[str] = set()
    for item in reference:
        found = resolve_item(index, item)
        if len(found) != 1:
            raise ValueError(
                f"expected the gold item {item!r} to name one node, found {len(found)}"
            )
        nodes |= found
    return frozenset(nodes)


def score_valve_set(
    index: PlantIndex, reference: Iterable[str], answer: Iterable[str]
) -> ValveSetScore:
    """Compare the node set the answer names with the gold node set."""
    gold = reference_nodes(index, reference)
    named: set[str] = set()
    n_unresolved = 0
    for item in answer:
        found = resolve_item(index, item)
        if len(found) == 1:
            named |= found
        else:
            n_unresolved += 1
    correct = named == gold and n_unresolved == 0
    return ValveSetScore(
        correct=correct,
        f1=_f1(len(gold & named), len(gold), len(named) + n_unresolved),
        n_unresolved=n_unresolved,
    )


def _f1(true_positives: int, n_gold: int, n_answered: int) -> float:
    if n_gold == 0 and n_answered == 0:
        return 1.0  # nothing to find and nothing spurious, as `score_set` rules
    if true_positives == 0:
        return 0.0
    precision = true_positives / n_answered
    recall = true_positives / n_gold
    return 2 * precision * recall / (precision + recall)


def score_answer_b(
    question: Question,
    outcome: Outcome,
    final_answer: FinalAnswer | None,
    index: PlantIndex,
    *,
    connector_tags: Iterable[str] = (),
    valid_edges: Iterable[tuple[str, str]] = (),
) -> ScoredAnswer:
    """`score_answer` for every type, with the two B types scored here.

    Raises:
        ValueError: an ANSWERED outcome without a final answer, or a malformed reference.
    """
    if question.answer_type not in (AnswerType.VALVE_SET, AnswerType.POSITION):
        return score_answer(
            question, outcome, final_answer, connector_tags=connector_tags, valid_edges=valid_edges
        )
    if outcome is not Outcome.ANSWERED:
        return ScoredAnswer(correct=False, f1=None)
    if final_answer is None:
        raise ValueError(f"expected a final answer for ANSWERED question {question.question_id!r}")
    if not question.answerable:  # the right call is to abstain
        return ScoredAnswer(correct=final_answer.not_present, f1=None)
    if final_answer.not_present:  # a false abstention is always wrong
        return ScoredAnswer(correct=False, f1=None)
    return _score_present_b(question, final_answer, index)


def _score_present_b(
    question: Question, final_answer: FinalAnswer, index: PlantIndex
) -> ScoredAnswer:
    reference, answer = question.reference, final_answer.answer
    if question.answer_type is AnswerType.POSITION:
        if not isinstance(reference, str) or not isinstance(answer, str):
            raise ValueError(
                f"expected string POSITION reference and answer, got {reference!r}, {answer!r}"
            )
        return ScoredAnswer(correct=score_position(reference, answer), f1=None)
    if not isinstance(reference, list) or not isinstance(answer, list):
        raise ValueError(
            f"expected list VALVE_SET reference and answer, got {reference!r}, {answer!r}"
        )
    score = score_valve_set(index, reference, answer)
    return ScoredAnswer(correct=score.correct, f1=score.f1)
