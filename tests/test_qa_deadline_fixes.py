"""Three fixes to the question deadline found by the CV2-P1-D100 pilot (cascade v2, ADR-0048).

1. a step may not eat the final answer's reserve; 2. a TIMED_OUT row keeps the agent trace;
3. a TIMED_OUT row's `latency_s` is the final call's share, so the cascade total is the deadline.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from plantgraph.llm.models import (
    ChatRequest,
    ChatResponse,
    QuestionDeadline,
    RequestTimedOut,
    keeping_in_reserve,
    reserved_for_final_s,
)
from plantgraph.qa.agent.loop import run_agent_loop
from plantgraph.qa.agent.models import AgentParams
from plantgraph.qa.cascade.signals import extract_signals
from plantgraph.qa.harness.attempt import Answered, WorkItem, attempt
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.models import (
    AnswerType,
    Outcome,
    Question,
    QuestionFamily,
    RetrievalResult,
    RunConfig,
)
from plantgraph.qa.plant_api.primitives import PlantApi
from qa_agent_fakes import PIN, ScriptedModel, call
from qa_harness_toy import CORPUS_ID, build_toy, make_config
from qa_plant_api_toy import toy_graph

_DEADLINE_S = 120.0
_RESERVE_S = 30.0


def _response(latency_s: float, text: str = "x") -> ChatResponse:
    return ChatResponse(
        text=text,
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=0.0,
        latency_s=latency_s,
        provider_response_id=None,
        finish_reason="stop",
        from_cache=True,
        created_at=datetime(2026, 10, 10),
    )


# --- 1. a step keeps the reserve ----------------------------------------------------------


def test_a_step_gets_the_budget_minus_the_reserve_and_the_final_call_gets_all_of_it() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=_DEADLINE_S)
    meter.begin("q")
    budgets: list[float | None] = []

    def call_(timeout_s: float | None) -> ChatResponse:
        budgets.append(timeout_s)
        return _response(10.0)

    with keeping_in_reserve(_RESERVE_S):
        meter.timed_call(call_, is_final=False)
        meter.timed_call(call_, is_final=True)  # the final call ignores the reserve

    assert budgets == [90.0, 110.0]
    assert reserved_for_final_s() == 0.0  # the reserve ends with the block


def test_a_step_with_no_room_left_over_the_reserve_is_refused_without_a_call() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=_DEADLINE_S)
    meter.begin("q")
    meter.timed_call(lambda _t: _response(90.0), is_final=False)  # 30 s left = the reserve

    with keeping_in_reserve(_RESERVE_S), pytest.raises(QuestionDeadline):
        meter.timed_call(lambda _t: _response(0.0), is_final=False)


def test_without_a_deadline_the_reserve_changes_nothing() -> None:
    meter = UsageMeter(SpendGuard(None))
    meter.begin("q")
    budgets: list[float | None] = []

    def call_(timeout_s: float | None) -> ChatResponse:
        budgets.append(timeout_s)
        return _response(1.0)

    with keeping_in_reserve(_RESERVE_S):
        meter.timed_call(call_, is_final=False)

    assert budgets == [None]


def test_a_step_that_hits_its_cap_ends_the_loop_and_the_final_answer_keeps_its_reserve() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=_DEADLINE_S)
    meter.begin("q")
    model = ScriptedModel([call("find", limit=1), call("find", limit=1)])

    def hang_on_second_step(request: ChatRequest) -> ChatResponse:
        def one_call(timeout_s: float | None) -> ChatResponse:
            if len(model.requests) == 1:  # the second step hangs until its budget is gone
                raise RequestTimedOut("abandoned", latency_s=timeout_s or 0.0)
            return model(request)

        return meter.timed_call(one_call, is_final=False)

    run = run_agent_loop(
        pin=PIN,
        send=hang_on_second_step,
        api=PlantApi(toy_graph()),
        system_prompt="sys",
        first_user_message="q",
        params=AgentParams(final_reserve_s=_RESERVE_S),
        remaining_s=lambda: meter.remaining_s,
    )
    final_budgets: list[float | None] = []
    meter.timed_call(lambda t: final_budgets.append(t) or _response(1.0), is_final=True)

    assert run.stop_reason == "deadline" and len(run.gathered) == 1
    # step 1 took 0.5 s, step 2 was cut at 119.5 - 30 s: exactly the reserve is left
    assert final_budgets == [pytest.approx(_RESERVE_S)]


# --- 2 and 3. the TIMED_OUT row -----------------------------------------------------------


class _AgentLikeStrategy:
    """Retrieval spends 4 s in one call and leaves a trace, like an agent that stopped early."""

    name = "graph_agent"

    def __init__(self, meter: UsageMeter) -> None:
        self._meter = meter

    def retrieve(self, question_text: str) -> RetrievalResult:
        self._meter.timed_call(lambda _t: _response(4.0), is_final=False)
        return RetrievalResult(
            context="gathered", failure=None, trace={"stop_reason": "deadline", "n_steps": 2}
        )


class _HangingClient:
    """Every final call hangs: it is abandoned at the time it was given."""

    def complete(self, request: ChatRequest, **kwargs: Any) -> ChatResponse:
        timeout_s = kwargs["timeout_s"]
        raise RequestTimedOut("abandoned", latency_s=timeout_s)


def _question() -> Question:
    return Question.model_validate(
        {
            "question_id": "q1",
            "corpus_id": CORPUS_ID,
            "family": QuestionFamily.LOOKUP_TYPE,
            "template_id": "t",
            "template_version": "1",
            "text": "What class of item is P-101?",
            "answer_type": AnswerType.CLASS_NAME,
            "answerable": True,
            "reference": "pump",
            "generator_seed": 0,
        }
    )


@pytest.fixture
def config(tmp_path: Path) -> RunConfig:
    return make_config(build_toy(tmp_path), question_deadline_s=_DEADLINE_S)


@pytest.fixture
def timed_out(config: RunConfig) -> Answered:
    meter = UsageMeter(SpendGuard(None), deadline_s=_DEADLINE_S)
    item = WorkItem(_AgentLikeStrategy(meter), _question(), 0)  # type: ignore[arg-type]
    outcome = attempt(item, config, None, _HangingClient(), meter)  # type: ignore[arg-type]
    assert isinstance(outcome, Answered)
    return outcome


def test_a_timeout_in_the_final_call_keeps_the_retrieval_trace(timed_out: Answered) -> None:
    row = timed_out.row

    assert row.outcome is Outcome.TIMED_OUT
    assert row.trace["retrieval"] == {"stop_reason": "deadline", "n_steps": 2}
    assert row.trace["timed_out"] == "request"
    assert row.trace["recorded_elapsed_s"] == _DEADLINE_S


def test_latency_s_of_a_timed_out_row_is_the_final_calls_share(timed_out: Answered) -> None:
    assert timed_out.row.latency_s == pytest.approx(_DEADLINE_S - 4.0)


def test_the_cascade_total_of_a_timed_out_row_is_the_deadline(
    timed_out: Answered, config: RunConfig
) -> None:
    signals = extract_signals(timed_out.row, "tier", config.answer_pin, None, local_compute_s=0.0)

    assert signals.latency_s == pytest.approx(_DEADLINE_S)
    assert signals.latency_s <= _DEADLINE_S + 1e-9
