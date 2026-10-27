"""The CLASS_NAME vocabulary of a corpus: own-class counting, v1/v2 choice, prompt text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from corpus_v2 import SEED, corpus

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.graph import schema
from plantgraph.ingest.headline_v2 import HeadlinePresetV2
from plantgraph.llm.models import ChatRequest, ChatResponse, ModelPin
from plantgraph.qa.class_vocabulary import answer_class_names, own_class_names
from plantgraph.qa.final_answer import _answer_format_instruction, render_final_answer_request
from plantgraph.qa.models import AnswerType, RetrievalResult
from plantgraph.qa.strategies.base import answer_question
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

#: The text a v1 corpus must keep, character for character (ADR-0057, ADR-0058 Q3).
_V1_LIST = (
    "ActuatingFunction, BallValve, CentrifugalPump, CheckValve, Compressor, DrawingSet, "
    "FlowInPipeOffPageConnector, FlowInSignalOffPageConnector, FlowOutPipeOffPageConnector, "
    "FlowOutSignalOffPageConnector, GenericItem, GlobeValve, HeatExchanger, PlantSection, "
    "PressureVessel, ProcessColumn, ProcessInstrumentationFunction, ProcessPlant, "
    "ProcessSignalGeneratingFunction, Sheet, Tank"
)
_STRUCTURAL = {"ProcessPlant", "PlantSection", "DrawingSet", "Sheet"}


def _v2_plan() -> tuple[LoadPlan, set[str]]:
    """The load plan of the small v2 corpus, and the item classes drawn on its sheets."""
    synthetic = corpus()
    plan = build_load_plan("X30g2", synthetic.localized_sheets, synthetic.resolution)
    drawn = {
        str(attrs["node_class"])
        for sheet in synthetic.localized_sheets
        for _, attrs in sheet.graph.nodes(data=True)
    }
    return plan, drawn


def test_an_ancestor_label_is_not_an_own_class() -> None:
    counts = {"CentrifugalPump": 2, "Pump": 2, "Equipment": 2, "Tank": 1, "Vessel": 1}

    assert own_class_names(counts) == ("CentrifugalPump", "Tank")


def test_a_class_that_is_also_an_ancestor_counts_when_it_has_own_nodes() -> None:
    counts = {"CentrifugalPump": 2, "Pump": 5}  # three of the five are plain Pumps

    assert own_class_names(counts) == ("CentrifugalPump", "Pump")


def test_labels_that_do_not_follow_the_schema_chains_are_refused() -> None:
    with pytest.raises(ValueError, match="at least its descendants"):
        own_class_names({"CentrifugalPump": 3, "Pump": 1})


def test_a_v2_corpus_lists_the_classes_drawn_in_it_and_the_structural_ones() -> None:
    plan, drawn = _v2_plan()

    names = answer_class_names(HeadlinePresetV2().generator_config(1, SEED), plan)

    assert names is not None
    assert set(names) - _STRUCTURAL == drawn
    assert len(names) > len(schema.V1_NODE_CLASSES)  # the v2 vocabulary is the larger one


def test_a_v1_corpus_and_a_proteus_import_keep_the_pinned_list() -> None:
    plan, _ = _v2_plan()  # the plan is never read on the v1 path

    assert answer_class_names(GeneratorConfig(), plan) is None
    assert answer_class_names(None, plan) is None


def test_no_class_list_gives_exactly_the_v1_text() -> None:
    expected = f"Answer with one of these class names, exactly as written: {_V1_LIST}."

    assert _answer_format_instruction(AnswerType.CLASS_NAME) == expected
    assert _answer_format_instruction(AnswerType.CLASS_NAME, None) == expected


def test_a_corpus_list_replaces_the_v1_list_in_the_class_name_prompt() -> None:
    pin = ModelPin(backend="local", model_id="m", max_output_tokens=10)

    request = render_final_answer_request(
        pin=pin,
        context="ctx",
        question_text="What kind of item is V-1?",
        answer_type=AnswerType.CLASS_NAME,
        class_names=["Tank", "GateValve"],
    )

    text = request.messages[0].content
    assert "exactly as written: GateValve, Tank." in text
    assert "CentrifugalPump" not in text


def test_the_other_answer_types_ignore_the_class_list() -> None:
    with_list = _answer_format_instruction(AnswerType.COUNT, ["Tank"])

    assert with_list == _answer_format_instruction(AnswerType.COUNT)


class _FixedContext:
    name = "stub"

    def retrieve(self, question_text: str) -> RetrievalResult:
        return RetrievalResult(context="ctx", failure=None)


@dataclass(frozen=True)
class _Asked:
    question_id: str = "q1"
    text: str = "What kind of item is V-1?"
    answer_type: AnswerType = AnswerType.CLASS_NAME


def _prompt_sent_for(class_names: tuple[str, ...] | None) -> str:
    """Run one question through `answer_question` and return the prompt the model would get."""
    sent: list[str] = []

    def send(request: ChatRequest) -> ChatResponse:
        sent.append(request.messages[0].content)
        return ChatResponse(
            text='{"answer": "Tank", "not_present": false}',
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=None,
            latency_s=0.0,
            provider_response_id=None,
            finish_reason="stop",
            from_cache=False,
            created_at=datetime.now(UTC),
        )

    pin = ModelPin(backend="local", model_id="m", max_output_tokens=10)
    answer_question(
        _FixedContext(), _Asked(), pin=pin, wall=None, send=send, class_names=class_names
    )
    return sent[0]


def test_answer_question_hands_the_corpus_list_to_the_prompt() -> None:
    assert "exactly as written: GateValve, Tank." in _prompt_sent_for(("Tank", "GateValve"))
    assert _V1_LIST in _prompt_sent_for(None)
