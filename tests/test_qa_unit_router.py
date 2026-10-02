"""The router fallback and the registry entry for Hierarchical (H-T2; design §3.1 step 2, §3.5).

The fallback goes through the fake transport: `FakeTransport.requests` proves
how many calls reached the (fake) network, and none leaves the machine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.llm.openrouter_settings import OpenRouterSettings
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.harness.registry import LlmDeps, build_strategy
from plantgraph.qa.models import AnswerType, Outcome, Question, QuestionFamily
from plantgraph.qa.strategies.base import answer_question
from plantgraph.qa.strategies.hierarchical import Hierarchical
from plantgraph.qa.unit_router import UnitRouter, UnitRouterError, build_plant_map, parse_units
from qa_harness_toy import pin
from qa_hierarchical_toy import UNLIMITED, strategy
from qa_routing_toy import ToyCorpus

_ANSWER = '{"answer": "Pump", "not_present": false}'


def _toy() -> ToyCorpus:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA", unit_id="7")
    toy.item("S1", "b", "TB", unit_id="7")
    toy.item("S2", "c", "TC", unit_id="8")
    toy.item("S3", "d", "TD", unit_id="9")
    return toy


def _send(fake: FakeTransport, tmp_path: Path) -> SendChatRequest:
    client = ChatClient.for_openrouter(
        OpenRouterSettings.model_validate({"api_key": "sk-test"}),
        cache=SqliteCache(tmp_path / "cache.sqlite", "live"),
        calls_log_path=tmp_path / "calls.jsonl",
        allow_network=True,
        http_client=fake.as_httpx_client(),
    )

    def send(request: ChatRequest) -> ChatResponse:
        return client.complete(request, run_id="test")

    return send


def _routed(reply: str, tmp_path: Path) -> tuple[Hierarchical, FakeTransport]:
    fake = FakeTransport(default_reply=ScriptedReply(text=reply))
    toy = _toy()
    router = UnitRouter(toy.view(), pin(), _send(fake, tmp_path))
    return strategy(toy, unit_router=router), fake


def test_the_plant_map_has_one_line_per_unit_with_its_sorted_tags() -> None:
    assert build_plant_map(_toy().view()) == "7: TA, TB\n8: TC\n9: TD"


def test_no_anchor_makes_one_counted_call_and_routes_to_the_chosen_units(tmp_path: Path) -> None:
    hierarchical, fake = _routed('{"units": ["8", "99"]}', tmp_path)

    result = hierarchical.retrieve("How many pumps are there?")

    assert result.failure is None
    assert len(fake.requests) == 1
    assert result.trace["fallback_needed"] is True and result.trace["fallback_used"] is True
    assert result.trace["router_units"] == ["8"] and result.trace["router_unknown_units"] == ["99"]
    assert result.trace["routed_sheets"] == ["S2"]
    assert result.trace["router_call"]["prompt_tokens"] == 10
    prompt = json.loads(fake.requests[0].content)["messages"][0]["content"]
    assert "7: TA, TB" in prompt and "How many pumps are there?" in prompt
    assert "<<" not in prompt  # every placeholder was filled


def test_the_fallback_is_used_only_without_anchors_and_is_counted_per_question(
    tmp_path: Path,
) -> None:
    hierarchical, fake = _routed('{"units": ["7"]}', tmp_path)
    questions = ["How many pumps?", "What is TA?", "Which unit is largest?"]

    used = [hierarchical.retrieve(q).trace["fallback_used"] for q in questions]

    assert used == [True, False, True]
    assert len(fake.requests) == 2  # the anchored question made no call


def test_a_fenced_reply_is_accepted_and_unit_ids_match_case_insensitively(tmp_path: Path) -> None:
    hierarchical, _ = _routed('```json\n{"units": ["7", "7"]}\n```', tmp_path)

    trace = hierarchical.retrieve("How many pumps?").trace

    assert trace["router_units"] == ["7"]  # a repeated id is one unit
    assert trace["routed_sheets"] == ["S1"]


def test_a_reply_that_is_not_the_requested_json_is_a_retrieval_error(tmp_path: Path) -> None:
    hierarchical, fake = _routed("Units 7 and 8, I think.", tmp_path)

    result = hierarchical.retrieve("How many pumps?")

    assert result.failure is Outcome.RETRIEVAL_ERROR and result.context is None
    assert "expected a JSON object" in result.trace["retrieval_error"]
    assert result.trace["fallback_used"] is True and len(fake.requests) == 1  # the call was made


def test_a_reply_naming_no_known_unit_gives_an_empty_context_not_a_guess(tmp_path: Path) -> None:
    hierarchical, _ = _routed('{"units": ["99"]}', tmp_path)

    result = hierarchical.retrieve("How many pumps?")

    assert result.failure is None
    assert result.trace["routed_sheets"] == [] and result.trace["serialized_keys"] == []


def test_without_a_router_a_question_with_no_anchor_fails_with_the_reason() -> None:
    result = strategy(_toy()).retrieve("How many pumps?")

    assert result.failure is Outcome.RETRIEVAL_ERROR
    assert result.trace["fallback_needed"] is True and result.trace["fallback_used"] is False
    assert "no router configured" in result.trace["retrieval_error"]


def test_a_corpus_without_unit_ids_cannot_use_the_fallback(tmp_path: Path) -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    fake = FakeTransport()
    router = UnitRouter(toy.view(), pin(), _send(fake, tmp_path))

    result = strategy(toy, unit_router=router).retrieve("How many pumps?")

    assert result.failure is Outcome.RETRIEVAL_ERROR and not fake.requests
    assert "no unit ids" in result.trace["retrieval_error"]


def test_parse_units_names_what_it_expected() -> None:
    assert parse_units('{"units": [7, "8"]}') == ["7", "8"]
    with pytest.raises(UnitRouterError, match="'units' list"):
        parse_units('{"unit": ["7"]}')


def test_a_routed_question_still_goes_through_the_shared_final_step(tmp_path: Path) -> None:
    fake = FakeTransport(default_reply=ScriptedReply(text='{"units": ["7"]}'))
    hierarchical = strategy(
        _toy(), unit_router=UnitRouter(_toy().view(), pin(), _send(fake, tmp_path))
    )
    question = Question(
        question_id="q1",
        corpus_id="toy",
        family=QuestionFamily.LOOKUP_TYPE,
        template_id="t",
        template_version="1",
        text="How many pumps are there?",
        answer_type=AnswerType.CLASS_NAME,
        answerable=True,
        reference="Pump",
        generator_seed=0,
    )
    fake_final = FakeTransport(default_reply=ScriptedReply(text=_ANSWER))

    result = answer_question(
        hierarchical, question, pin=pin(), wall=None, send=_send(fake_final, tmp_path)
    )

    assert result.outcome is Outcome.ANSWERED
    assert len(fake.requests) == 1 and len(fake_final.requests) == 1
    assert result.trace["retrieval"]["fallback_used"] is True


_PARAMS = {
    "route_mode": "flow_path",
    "budget_mode": "through_line",
    "sheet_hops": 1,
    "max_context_chars": 5000,
}


def test_registry_builds_hierarchical_and_names_every_missing_parameter(tmp_path: Path) -> None:
    view = _toy().view()
    deps = LlmDeps(pin(), _send(FakeTransport(), tmp_path))

    built = build_strategy("hierarchical", _PARAMS, view, None, deps)

    assert built.name == "hierarchical" and isinstance(built, Hierarchical)
    with pytest.raises(ValueError, match=r"\['route_mode', 'sheet_hops'\]"):
        build_strategy("hierarchical", {"budget_mode": "drop_rings", "max_context_chars": 1}, view)
    with pytest.raises(ValueError, match="hierarchical"):
        build_strategy("no_such_strategy", {}, view)


def test_registry_without_llm_deps_builds_a_retrieval_only_strategy() -> None:
    built = build_strategy(
        "hierarchical", {**_PARAMS, "max_context_chars": UNLIMITED}, _toy().view()
    )

    assert built.retrieve("What is TA?").failure is None
    assert built.retrieve("How many?").failure is Outcome.RETRIEVAL_ERROR
