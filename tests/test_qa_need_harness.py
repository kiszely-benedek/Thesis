"""The harness side of the need layer: registry entry and the oracle classifier (QAR-T4)."""

from __future__ import annotations

from typing import Any

import pytest

from plantgraph.qa.harness.oracle_need import OracleNeedClassifier
from plantgraph.qa.harness.registry import build_strategy
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.need.classifiers import NeedInput
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.strategies.hierarchical_need import NeedAwareHierarchical
from qa_need_toy import ISOLATION_QUESTION, need_toy

_PARAMS: dict[str, Any] = {
    "route_mode": "flow_path",
    "budget_mode": "through_line",
    "sheet_hops": 1,
    "max_context_chars": 10**9,
}


def _question(family: QuestionFamily, text: str, template_id: str = "t") -> Question:
    return Question(
        question_id=f"q-{family.value}",
        corpus_id="c",
        family=family,
        template_id=template_id,
        template_version="1",
        text=text,
        answer_type=AnswerType.TAG_SET,
        answerable=True,
        reference=[],
        generator_seed=0,
    )


def _input(text: str) -> NeedInput:
    return NeedInput(text=text, masked_text=text, n_tag_anchors=0, n_unit_anchors=0)


def test_the_registry_builds_the_rules_variant_and_names_every_missing_parameter() -> None:
    view = need_toy().view()

    built = build_strategy("hierarchical_need_rules", _PARAMS, view)

    assert isinstance(built, NeedAwareHierarchical) and built.name == "hierarchical_need_rules"
    assert built.retrieve(ISOLATION_QUESTION).trace["need_used"] is True
    with pytest.raises(
        ValueError, match=r"hierarchical_need_rules.*\['route_mode', 'sheet_hops'\]"
    ):
        build_strategy(
            "hierarchical_need_rules", {"budget_mode": "drop_rings", "max_context_chars": 1}, view
        )


def test_an_unknown_name_lists_the_need_variant_among_the_known_ones() -> None:
    with pytest.raises(ValueError, match="hierarchical_need_rules"):
        build_strategy("no_such_strategy", {}, need_toy().view())


def test_the_oracle_answers_with_the_gold_label_of_the_text_and_full_confidence() -> None:
    questions = [
        _question(QuestionFamily.UPSTREAM_ISOLATION, "isolate it"),
        _question(QuestionFamily.UNANSWERABLE_TAG, "path to nowhere", "FLOW_PATH"),
    ]
    oracle = OracleNeedClassifier.from_questions(questions)

    isolation = oracle.classify(_input("isolate it"))
    unanswerable = oracle.classify(_input("path to nowhere"))

    assert isolation.label is NeedLabel.UPSTREAM_TO_FIRST_VALVE and isolation.score == 1.0
    assert unanswerable.label is NeedLabel.PATH  # the template the question wraps decides
    assert oracle.name == "oracle" and isolation.classifier == "oracle"


def test_the_oracle_refuses_an_unknown_text_and_an_ambiguous_one() -> None:
    oracle = OracleNeedClassifier.from_questions([_question(QuestionFamily.LOOKUP_TYPE, "what?")])
    with pytest.raises(ValueError, match="a question text the oracle knows"):
        oracle.classify(_input("something else"))

    clash = [
        _question(QuestionFamily.LOOKUP_TYPE, "same words"),
        _question(QuestionFamily.UPSTREAM_ISOLATION, "same words"),
    ]
    with pytest.raises(ValueError, match="one gold need label per question text"):
        OracleNeedClassifier.from_questions(clash)


def test_the_oracle_drives_the_strategy_through_the_same_interface() -> None:
    question = _question(QuestionFamily.UPSTREAM_ISOLATION, ISOLATION_QUESTION)
    oracle = OracleNeedClassifier.from_questions([question])
    strategy = NeedAwareHierarchical(need_toy().view(), oracle, **_PARAMS)

    trace = strategy.retrieve(ISOLATION_QUESTION).trace

    assert strategy.name == "hierarchical_need_oracle"
    assert trace["need_label"] == "UPSTREAM_TO_FIRST_VALVE" and trace["need_score"] == 1.0
