"""ContextRAG and the `Strategy` runner (`qa-system.md` §18 QA-T9).

Only the fake transport is used: `FakeTransport.requests` proves how many
calls reached the (fake) network.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import ChatRequest, ChatResponse, ContextWall, ModelPin
from plantgraph.llm.openrouter_settings import OpenRouterSettings
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.models import AnswerType, Outcome, Question, QuestionFamily, RetrievalResult
from plantgraph.qa.strategies.base import Strategy, answer_question
from plantgraph.qa.strategies.context_rag import ContextRag
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.resolver import resolve

_CORPUS_ID = "acme-plant-01"
_ANSWER_JSON = '{"answer": "pump", "not_present": false}'


def _corpus() -> tuple[NetworkxGraphView, OccurrenceMap]:
    generator_config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    sheets, _manifest = split(builder.graph, SplitConfig(sheet_equipment_budget=2, seed=7))
    localized, occurrence_map = localize(sheets)
    return NetworkxGraphView(_CORPUS_ID, localized, resolve(localized)), occurrence_map


def _pin() -> ModelPin:
    return ModelPin(
        backend="openrouter",
        model_id="openai/gpt-5-mini",
        route_provider="openai",
        temperature=0.0,
        seed=1,
        max_output_tokens=64,
    )


def _wall(min_rejected_chars: int) -> ContextWall:
    return ContextWall(
        pin_hash="pin",
        max_ok_chars=1,
        min_rejected_chars=min_rejected_chars,
        measured_at=datetime(2026, 10, 2),
        probe_corpus_ids=["D10"],
    )


def _question(**overrides: object) -> Question:
    fields: dict[str, object] = {
        "question_id": "q1",
        "corpus_id": _CORPUS_ID,
        "family": QuestionFamily.LOOKUP_TYPE,
        "template_id": "t",
        "template_version": "1",
        "text": "What class of item is P-101?",
        "answer_type": AnswerType.CLASS_NAME,
        "answerable": True,
        "reference": "pump",
        "generator_seed": 0,
    }
    fields.update(overrides)
    return Question.model_validate(fields)


def _send_through_fake(
    fake: FakeTransport, tmp_path: Path
) -> Callable[[ChatRequest], ChatResponse]:
    """A real `ChatClient` whose HTTP layer is the fake: no socket is ever opened."""
    client = ChatClient.for_openrouter(
        OpenRouterSettings.model_validate({"api_key": "sk-test"}),
        cache=SqliteCache(tmp_path / "cache.sqlite", "live"),
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
        http_client=fake.as_httpx_client(),
    )
    return lambda request: client.complete(request, run_id="test")


def _fake() -> FakeTransport:
    return FakeTransport(default_reply=ScriptedReply(text=_ANSWER_JSON))


def test_small_corpus_is_answered(tmp_path: Path) -> None:
    view, _map = _corpus()
    fake = _fake()
    result = answer_question(
        ContextRag(view),
        _question(),
        pin=_pin(),
        wall=None,
        send=_send_through_fake(fake, tmp_path),
    )
    assert result.outcome is Outcome.ANSWERED
    assert result.final_answer is not None and result.final_answer.answer == "pump"
    assert len(fake.requests) == 1


def test_prompt_over_min_rejected_chars_makes_no_call(tmp_path: Path) -> None:
    view, _map = _corpus()
    fake = _fake()
    result = answer_question(
        ContextRag(view),
        _question(),
        pin=_pin(),
        wall=_wall(min_rejected_chars=100),
        send=_send_through_fake(fake, tmp_path),
    )
    assert result.outcome is Outcome.DID_NOT_FIT
    assert fake.requests == []


def test_retrieval_ignores_everything_but_the_text(tmp_path: Path) -> None:
    """Questions that differ only in family, answer type, k or evidence give one prompt."""
    view, _map = _corpus()
    plain = _question()
    decorated = _question(
        family=QuestionFamily.FLOW_PATH,
        k=3,
        evidence_tags=["P-101"],
        evidence_sheets=["S1"],
        reference="pump",
    )
    prompts = []
    for question in (plain, decorated):
        fake = _fake()
        answer_question(
            ContextRag(view),
            question,
            pin=_pin(),
            wall=None,
            send=_send_through_fake(fake, tmp_path / question.family.value),
        )
        prompts.append(fake.requests[0].content)
    assert prompts[0] == prompts[1]


def test_prompt_holds_no_gold_key_uid_or_corpus_id(tmp_path: Path) -> None:
    view, occurrence_map = _corpus()
    fake = _fake()
    answer_question(
        ContextRag(view),
        _question(),
        pin=_pin(),
        wall=None,
        send=_send_through_fake(fake, tmp_path),
    )
    prompt = json.loads(fake.requests[0].content)["messages"][0]["content"]
    # `uid` as a whole word: "fluid" or "liquid" in the prompt text are fine
    assert re.search(r"uid", prompt) is None and _CORPUS_ID not in prompt
    for original_key in occurrence_map.local_to_original.values():
        assert original_key.partition(":")[2] not in prompt


def test_failed_retrieval_returns_its_outcome_without_a_call(tmp_path: Path) -> None:
    class Failing:
        name = "failing"

        def retrieve(self, question_text: str) -> RetrievalResult:
            return RetrievalResult(context=None, failure=Outcome.RETRIEVAL_ERROR)

    strategy: Strategy = Failing()
    fake = _fake()
    result = answer_question(
        strategy, _question(), pin=_pin(), wall=None, send=_send_through_fake(fake, tmp_path)
    )
    assert result.outcome is Outcome.RETRIEVAL_ERROR
    assert fake.requests == []
