"""`Question`, `FinalAnswer`, `Outcome`, `QuestionResult`, `CorpusRecord`, `RunConfig` (§4).

Plain Pydantic models, no I/O: every test is a pure in-memory round trip.
"""

from __future__ import annotations

from datetime import datetime

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.llm.models import ModelPin
from plantgraph.qa.models import (
    AnswerType,
    CorpusRecord,
    FinalAnswer,
    Outcome,
    Question,
    QuestionFamily,
    QuestionResult,
    RunConfig,
)


def _question(**overrides: object) -> Question:
    defaults: dict[str, object] = {
        "question_id": "q-0001",
        "corpus_id": "plant0",
        "family": QuestionFamily.LOOKUP_TYPE,
        "template_id": "lookup_type.v1",
        "template_version": "1",
        "text": "What type of item is P-101?",
        "answer_type": AnswerType.CLASS_NAME,
        "answerable": True,
        "reference": "Pump",
        "generator_seed": 0,
    }
    defaults.update(overrides)
    return Question.model_validate(defaults)


def _pin() -> ModelPin:
    return ModelPin(backend="openrouter", model_id="openai/gpt-5-mini", max_output_tokens=512)


def test_question_round_trips_through_json() -> None:
    question = _question(evidence_tags=["P-101"], evidence_sheets=["S1"], k=0, anchors=["P-101"])

    restored = Question.model_validate_json(question.model_dump_json())

    assert restored == question


def test_question_k_is_none_for_an_unanswerable_question() -> None:
    # design qa-system.md §9: unanswerable questions have k = None, never 0.
    question = _question(
        family=QuestionFamily.UNANSWERABLE_TAG,
        answer_type=AnswerType.TAG,
        answerable=False,
        reference=None,
    )

    assert question.k is None


def test_question_reference_accepts_every_answer_shape() -> None:
    assert _question(reference="P-101").reference == "P-101"
    assert _question(answer_type=AnswerType.COUNT, reference=3).reference == 3
    assert _question(answer_type=AnswerType.TAG_SET, reference=["P-101", "V-1"]).reference == [
        "P-101",
        "V-1",
    ]
    assert _question(answerable=False, reference=None).reference is None


def test_question_has_no_field_a_strategy_may_read_besides_text() -> None:
    # The fairness rule (§7): retrieval sees only `question.text`. This does not
    # enforce the rule by itself, but it documents which fields exist to leak.
    gold_fields = {"answerable", "reference", "evidence_tags", "evidence_sheets", "k", "anchors"}
    assert gold_fields.issubset(Question.model_fields.keys())


def test_final_answer_round_trips_through_json() -> None:
    answer = FinalAnswer(answer=["P-101", "V-1"], not_present=False)

    assert FinalAnswer.model_validate_json(answer.model_dump_json()) == answer


def test_outcome_has_exactly_the_six_values_the_design_lists() -> None:
    assert {member.value for member in Outcome} == {
        "ANSWERED",
        "DID_NOT_FIT",
        "PARSE_FAILURE",
        "RETRIEVAL_ERROR",
        "PROVIDER_ERROR",
        "TIMED_OUT",  # cascade v2 (CV2-T2)
    }


def test_question_result_round_trips_and_allows_a_missing_final_answer() -> None:
    result = QuestionResult(
        run_id="run-1",
        question_id="q-0001",
        strategy="context_rag",
        repeat=0,
        outcome=Outcome.PARSE_FAILURE,
        final_answer=None,
        correct=False,
        f1=None,
        prompt_tokens=120,
        completion_tokens=0,
        cost_usd=None,
        latency_s=0.4,
        context_chars=2048,
    )

    assert QuestionResult.model_validate_json(result.model_dump_json()) == result


def test_corpus_record_keeps_store_and_plant_node_counts_apart() -> None:
    record = CorpusRecord(
        corpus_id="plant0",
        role="test",
        generator_config=GeneratorConfig(),
        split_config=SplitConfig(),
        n_sheets=10,
        n_store_nodes=430,
        n_connector_pairs_predicted=12,
        n_plant_nodes=400,
        n_plant_edges=420,
        source_graph_hash="deadbeef",
        stage_seconds={"generate": 0.1, "split": 0.05},
    )

    # The store's occurrence graph also holds connector stub nodes, so it is
    # never the same count as the ground-truth plant graph (§2.1).
    assert record.n_store_nodes != record.n_plant_nodes


def test_run_config_is_not_reported_by_default() -> None:
    config = RunConfig(
        run_id="run-1",
        experiment="EXP-0002",
        reported=False,
        corpora=["plant0"],
        strategies={"context_rag": {}},
        answer_pin=_pin(),
        question_set_sha256="a" * 64,
        git_commit="abc1234",
        git_dirty=False,
        created_at=datetime(2026, 9, 26, 12, 0, 0),
    )

    assert config.reported is False
    assert config.context_wall is None  # not measured yet, allowed before freeze
    assert config.allow_paid_calls is False  # never on by default (§6)
