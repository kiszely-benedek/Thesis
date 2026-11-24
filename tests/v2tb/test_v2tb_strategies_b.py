"""R6: the two B strategies read the B primer, the B final step and the B corpus (§10.6 (5))."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import pytest
from plants_b import real_corpus

from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.qa.agent.strategies import GraphAgentLines
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.harness.registry import CypherDeps, LlmDeps
from plantgraph.qa.models import AnswerType, Outcome, RetrievalResult
from plantgraph.qa.plant_api.item_graph import build_item_graph
from plantgraph.qa.primer import primer_block
from plantgraph.qa.strategies.cypher_rag_lines import CypherRagLines
from plantgraph.qa.v2tb.answer_b import answer_question_b, run_final_step_b
from plantgraph.qa.v2tb.item_graph_b import build_item_graph_b
from plantgraph.qa.v2tb.primer_b import POSITION_PRIMER
from plantgraph.qa.v2tb.registry_b import build_strategy_b
from plantgraph.qa.v2tb.strategies_b import (
    CYPHER_RAG_LINES_B_NAME,
    GRAPH_AGENT_LINES_B_NAME,
    CypherRagLinesB,
    GraphAgentLinesB,
    _with_b_reading,
)
from plantgraph.qa.v2tb.views_b import NetworkxGraphViewB
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from qa_agent_fakes import DONE, PIN, ScriptedModel, call


def _view_with_positions() -> tuple[NetworkxGraphViewB, str]:
    """The small plant's view with every tagged valve positioned NC; also one such valve's tag."""
    corpus = real_corpus()
    plain = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution)
    valves = [i for i in plain.items() if "Valve" in i.node_class and i.tag is not None]
    positions = {valve.local_key: "NC" for valve in valves}
    view = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution, positions)
    return view, str(valves[0].tag)


def _agent(view: NetworkxGraphViewB, send: ScriptedModel, *, primer: bool) -> GraphAgentLinesB:
    return GraphAgentLinesB(build_item_graph_b(view, line_view=True), PIN, send, primer=primer)


# ---- the agent ---------------------------------------------------------------------------------


def test_a_b_agent_tool_output_for_a_positioned_valve_shows_its_position() -> None:
    view, tag = _view_with_positions()
    send = ScriptedModel([call("find", where={"tag": tag}), DONE])

    context = _agent(view, send, primer=False).retrieve("What is the position of the valve?")

    assert context.context is not None
    assert f"[{OPERATING_POSITION} NC]" in context.context.split("Call:")[1]
    assert context.trace["n_steps"] == 2


def test_the_frozen_agent_prints_no_position_for_the_same_valve() -> None:
    view, tag = _view_with_positions()
    send = ScriptedModel([call("find", where={"tag": tag}), DONE])
    frozen = GraphAgentLines(build_item_graph_b(view, line_view=True), PIN, send)

    context = frozen.retrieve("q")

    assert context.context is not None
    assert OPERATING_POSITION not in context.context  # the gap the B result types close


def test_the_agent_system_prompt_has_the_b_primer_only_when_the_primer_is_on() -> None:
    view, _tag = _view_with_positions()
    graph = build_item_graph_b(view, line_view=True)
    frozen_off = GraphAgentLines(graph, PIN, ScriptedModel([]), primer=False)
    frozen_on = GraphAgentLines(graph, PIN, ScriptedModel([]), primer=True)

    b_off = _agent(view, ScriptedModel([]), primer=False)
    b_on = _agent(view, ScriptedModel([]), primer=True)

    # the view holds positions, so the prompt also carries the one sentence on the two brackets
    assert b_off.system_prompt == _with_b_reading(frozen_off.system_prompt)
    assert POSITION_PRIMER in b_on.system_prompt
    assert b_on.system_prompt == _with_b_reading(
        frozen_on.system_prompt.replace(primer_block(), primer_block() + "\n" + POSITION_PRIMER)
    )


def test_on_a_corpus_without_positions_the_b_agent_reads_what_the_frozen_agent_reads() -> None:
    corpus = real_corpus()
    plain = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution)
    tag = next(i.tag for i in plain.items() if "Pump" in i.node_class and i.tag)
    script = [call("neighbours", of=tag, direction="both", relations="flow"), DONE]
    b_send, a_send = ScriptedModel(script), ScriptedModel(script)

    b_context = _agent(plain, b_send, primer=False).retrieve("q").context
    a_context = GraphAgentLines(build_item_graph(plain, line_view=True), PIN, a_send).retrieve("q")

    assert b_context is not None and a_context.context is not None
    # the only difference is the line number the B edge lines add
    assert re.sub(r" \[line [^\]]*\]", "", b_context) == a_context.context
    assert b_send.requests[0].messages == a_send.requests[0].messages  # same first prompt


# ---- the Cypher strategy -----------------------------------------------------------------------


class _Source:
    def schema_text(self) -> str:
        return "SCHEMA"

    def label_names(self) -> frozenset[str]:
        return frozenset({"Pump", "CorpusNode"})

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        return CypherResult(rows=[{"tag": "X"}], truncated=False)

    def close(self) -> None:
        pass


def _capturing_model(sent: list[ChatRequest]) -> Any:
    def send(request: ChatRequest) -> ChatResponse:
        sent.append(request)
        return ChatResponse(
            text="MATCH (n) RETURN n.tag",
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.0,
            latency_s=0.0,
            provider_response_id="x",
            finish_reason="stop",
            from_cache=False,
            created_at=datetime(2026, 11, 24),
        )

    return send


def test_the_b_cypher_prompt_carries_the_b_primer_and_is_otherwise_the_frozen_prompt() -> None:
    sent_b: list[ChatRequest] = []
    sent_a: list[ChatRequest] = []
    params: dict[str, Any] = {"timeout_s": 5.0, "row_cap": 3}
    b_on = CypherRagLinesB(_Source(), PIN, _capturing_model(sent_b), primer=True, **params)  # type: ignore[arg-type]
    a_on = CypherRagLines(_Source(), PIN, _capturing_model(sent_a), primer=True, **params)  # type: ignore[arg-type]

    b_result = b_on.retrieve("Which pump is P-1?")
    a_on.retrieve("Which pump is P-1?")

    b_prompt, a_prompt = sent_b[0].messages[0].content, sent_a[0].messages[0].content
    assert POSITION_PRIMER in b_prompt and POSITION_PRIMER not in a_prompt
    assert b_prompt.replace("\n" + POSITION_PRIMER, "", 1) == a_prompt
    assert b_result.context is not None and b_on.name == CYPHER_RAG_LINES_B_NAME


def test_the_b_cypher_prompt_with_the_primer_off_is_the_frozen_prompt_byte_for_byte() -> None:
    sent_b: list[ChatRequest] = []
    sent_a: list[ChatRequest] = []
    params: dict[str, Any] = {"timeout_s": 5.0, "row_cap": 3}
    CypherRagLinesB(_Source(), PIN, _capturing_model(sent_b), **params).retrieve("Q P-1")  # type: ignore[arg-type]
    CypherRagLines(_Source(), PIN, _capturing_model(sent_a), **params).retrieve("Q P-1")  # type: ignore[arg-type]

    assert sent_b[0].messages == sent_a[0].messages


# ---- the final step and the registry -----------------------------------------------------------


class _FixedStrategy:
    name = GRAPH_AGENT_LINES_B_NAME

    def retrieve(self, question_text: str) -> RetrievalResult:
        return RetrievalResult(context="CTX", failure=None, trace={"k": 1})


class _Asked:
    question_id = "q1"
    text = "Which valves must be closed?"
    answer_type = AnswerType.VALVE_SET


def test_the_b_final_step_uses_the_b_primer_the_b_format_and_the_b_parser() -> None:
    descriptor = {
        "class": "GateValve",
        "line_number": "6-P-1",
        "next_to": "P-1",
        "side": "upstream",
    }
    reply = json.dumps({"answer": ["GTV-1", descriptor], "not_present": False})
    send = ScriptedModel([reply])

    step = answer_question_b(
        _FixedStrategy(), _Asked(), pin=PIN, wall=None, send=send, primer=True, class_names=None
    )

    prompt = send.requests[0].messages[0].content
    assert POSITION_PRIMER in prompt
    assert "one entry per valve" in prompt  # the B VALVE_SET format sentence
    assert step.outcome is Outcome.ANSWERED and step.final_answer is not None
    assert step.final_answer.answer is not None and len(step.final_answer.answer) == 2
    assert step.trace["retrieval"] == {"k": 1}


def test_run_final_step_b_gives_a_tag_set_the_frozen_request() -> None:
    from plantgraph.qa.final_answer import render_final_answer_request

    send = ScriptedModel(['{"answer": ["A"], "not_present": false}'])

    run_final_step_b(
        pin=PIN,
        context="C",
        question_text="Q",
        answer_type=AnswerType.TAG_SET,
        wall=None,
        send=send,
    )

    frozen = render_final_answer_request(
        pin=PIN, context="C", question_text="Q", answer_type=AnswerType.TAG_SET
    )
    assert send.requests[0] == frozen


def test_the_registry_builds_only_b_strategies_and_names_what_is_missing() -> None:
    view, _tag = _view_with_positions()
    llm = LlmDeps(PIN, ScriptedModel([]), primer=False)

    agent = build_strategy_b(GRAPH_AGENT_LINES_B_NAME, {}, view, llm=llm)
    cypher = build_strategy_b(
        CYPHER_RAG_LINES_B_NAME,
        {"timeout_s": 5, "row_cap": 3},
        view,
        cypher=CypherDeps(_Source(), PIN, ScriptedModel([])),  # type: ignore[arg-type]
    )

    assert isinstance(agent, GraphAgentLinesB) and isinstance(cypher, CypherRagLinesB)
    with pytest.raises(ValueError, match="expected a strategy in"):
        build_strategy_b("graph_agent_lines", {}, view, llm=llm)
    with pytest.raises(ValueError, match="database connection"):
        build_strategy_b(CYPHER_RAG_LINES_B_NAME, {}, view)
    with pytest.raises(ValueError, match="timeout_s"):
        build_strategy_b(
            CYPHER_RAG_LINES_B_NAME,
            {},
            view,
            cypher=CypherDeps(_Source(), PIN, ScriptedModel([])),  # type: ignore[arg-type]
        )
