"""QT-5: the V2T final-answer template, picked by strategy name, and F1's left untouched."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.qa.agent.strategies import GRAPH_AGENT_LINES_NAME
from plantgraph.qa.final_answer import render_final_answer_request, template_sha256
from plantgraph.qa.final_answer_variants import (
    V2T_STRATEGY_NAMES,
    V2T_TEMPLATE_PATH,
    template_path_for,
)
from plantgraph.qa.models import AnswerType, RetrievalResult
from plantgraph.qa.strategies.base import answer_question
from plantgraph.qa.strategies.cypher_rag import LINES_NAME, OCCURRENCE_NAME, PLANT_NAME
from qa_agent_fakes import PIN

#: sha256 of `prompts/final_answer.txt` at the commit before QT-5: F1's text must not move.
_F1_TEMPLATE_SHA256 = "f9e22b901e45f7a38dfd85f307bf742dc6f3e4f9303ef48db77841ddf4912baf"
_RULES_HEADER = "Three rules about what an answer may contain:"


@dataclass
class _Question:
    question_id: str = "q1"
    text: str = "Which items does P-101 feed?"
    answer_type: AnswerType = AnswerType.TAG_SET


class _Strategy:
    def __init__(self, name: str) -> None:
        self.name = name

    def retrieve(self, question_text: str) -> RetrievalResult:
        return RetrievalResult(context="the context", failure=None)


def _prompt_sent_by(strategy_name: str) -> str:
    sent: list[ChatRequest] = []

    def send(request: ChatRequest) -> ChatResponse:
        sent.append(request)
        return ChatResponse(
            text='{"answer": [], "not_present": false}',
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.0,
            latency_s=0.0,
            provider_response_id="r",
            finish_reason="stop",
            from_cache=False,
            created_at=datetime(2026, 10, 28),
        )

    answer_question(_Strategy(strategy_name), _Question(), pin=PIN, wall=None, send=send)
    return sent[0].messages[0].content


def test_f1s_template_is_byte_identical_to_the_sealed_one() -> None:
    assert template_sha256() == _F1_TEMPLATE_SHA256


def test_the_v2t_strategy_names_are_the_two_tuned_strategies() -> None:
    assert V2T_STRATEGY_NAMES == {LINES_NAME, GRAPH_AGENT_LINES_NAME}


@pytest.mark.parametrize("name", sorted(V2T_STRATEGY_NAMES))
def test_a_v2t_strategy_gets_the_three_rules(name: str) -> None:
    prompt = _prompt_sent_by(name)

    assert _RULES_HEADER in prompt
    assert "list only equipment items and valves" in prompt
    assert "is not part of its own answer" in prompt
    assert "answer not present" in prompt
    assert "the context" in prompt and "Which items does P-101 feed?" in prompt


@pytest.mark.parametrize("name", [OCCURRENCE_NAME, PLANT_NAME, "graph_agent", "context_rag"])
def test_every_other_strategy_gets_f1s_prompt(name: str) -> None:
    prompt = _prompt_sent_by(name)

    assert _RULES_HEADER not in prompt
    request = render_final_answer_request(
        pin=PIN,
        context="the context",
        question_text=_Question().text,
        answer_type=AnswerType.TAG_SET,
    )
    assert prompt == request.messages[0].content
    assert template_path_for(name) is None


def test_the_v2t_template_is_f1s_text_plus_the_rules_block() -> None:
    f1 = (V2T_TEMPLATE_PATH.parent / "final_answer.txt").read_text(encoding="utf-8")
    v2t = V2T_TEMPLATE_PATH.read_text(encoding="utf-8")

    start = v2t.index("\n" + _RULES_HEADER)
    end = v2t.index("\n", v2t.index("3. If the description")) + 1  # end of rule 3's line
    assert v2t[:start] + v2t[end:] == f1
