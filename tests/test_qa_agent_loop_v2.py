"""Agent loop v2 (design cascade-v2 §5.3): runaway, deadline, finish-with-call, step effort."""

from __future__ import annotations

import json

from plantgraph.llm.models import ModelPin, QuestionDeadline, RequestTimedOut
from plantgraph.qa.agent.actions import ToolCall, parse_action
from plantgraph.qa.agent.loop import RemainingSeconds, run_agent_loop
from plantgraph.qa.agent.models import AgentParams, AgentRun
from plantgraph.qa.agent.prompts import render_system_prompt
from plantgraph.qa.agent.strategies import GraphAgent, GraphAgentLowSteps
from plantgraph.qa.harness.registry import LlmDeps, build_strategy
from plantgraph.qa.plant_api.primitives import PlantApi
from qa_agent_fakes import PIN, ScriptedModel, call
from qa_need_toy import need_toy
from qa_plant_api_toy import toy_graph


def _run(
    model: ScriptedModel,
    params: AgentParams | None = None,
    remaining_s: RemainingSeconds | None = None,
    pin: ModelPin = PIN,
) -> AgentRun:
    return run_agent_loop(
        pin=pin,
        send=model,
        api=PlantApi(toy_graph()),
        system_prompt="SYSTEM",
        first_user_message="FIRST",
        params=params or AgentParams(),
        remaining_s=remaining_s,
    )


def _call_and_done(tool: str, **args: object) -> str:
    return json.dumps({"call": {"tool": tool, "args": args}, "done": True})


def test_a_reply_with_a_call_and_done_is_read_as_a_finishing_call() -> None:
    action = parse_action(_call_and_done("find", limit=1))

    assert action == ToolCall(tool="find", args={"limit": 1}, finish=True)
    assert parse_action(call("find")) == ToolCall(tool="find", args={}, finish=False)


# --- runaway ---------------------------------------------------------------------------


def test_a_cap_hit_step_reply_ends_the_loop_without_another_step() -> None:
    cap = PIN.max_output_tokens
    model = ScriptedModel(
        [call("find", limit=1), call("find", limit=2), call("find")],
        completion_tokens_at={1: cap},
    )

    run = _run(model)

    assert run.stop_reason == "runaway" and len(model.requests) == 2
    assert len(run.gathered) == 1  # the cut-off reply is not run, even though it parses
    assert run.steps[-1].error is not None and "cut off" in run.steps[-1].error
    assert run.invalid_actions == 1


# --- finish with the call ---------------------------------------------------------------


def test_a_call_with_done_runs_the_tool_and_stops() -> None:
    model = ScriptedModel([_call_and_done("find", limit=1), call("find")])

    run = _run(model)

    assert run.stop_reason == "done" and len(model.requests) == 1
    assert len(run.gathered) == 1 and run.steps[0].tool == "find"


def test_a_refused_call_with_done_does_not_stop_the_loop() -> None:
    model = ScriptedModel(
        [_call_and_done("find", where={"label": "Nope"}), _call_and_done("find", limit=1)]
    )

    run = _run(model)

    assert run.tool_errors == 1 and run.stop_reason == "done"
    assert len(model.requests) == 2 and len(run.gathered) == 1
    assert model.last_user_text(1).startswith("error: expected a known label")


# --- deadline ---------------------------------------------------------------------------


def test_a_budget_below_the_reserve_stops_before_the_step_call() -> None:
    model = ScriptedModel([call("find", limit=1)] * 3)
    left = iter([100.0, 29.9])  # enough for step 1, short before step 2

    run = _run(model, remaining_s=lambda: next(left))

    assert run.stop_reason == "deadline" and len(model.requests) == 1
    assert len(run.gathered) == 1  # what was gathered still reaches the final step


def test_no_deadline_never_stops_the_loop_on_time() -> None:
    model = ScriptedModel([call("find", limit=1)] * 2)

    assert _run(model, remaining_s=lambda: None).stop_reason == "done"


def test_the_reserve_is_a_parameter() -> None:
    model = ScriptedModel([])

    run = _run(model, AgentParams(final_reserve_s=5.0), remaining_s=lambda: 10.0)

    assert run.stop_reason == "done"  # 10 s left is above a 5 s reserve


def test_a_timeout_inside_a_step_ends_the_loop_with_deadline() -> None:
    for error in (RequestTimedOut("abandoned", latency_s=60.0), QuestionDeadline("spent")):
        model = ScriptedModel([call("find", limit=1)], raise_at={1: error})

        run = _run(model)

        assert run.stop_reason == "deadline" and len(run.gathered) == 1


# --- step effort ------------------------------------------------------------------------


def test_low_step_effort_changes_the_step_pin_only_and_keeps_other_extras() -> None:
    pin = PIN.model_copy(update={"extra": {"provider_flag": 1}})
    model = ScriptedModel([call("find", limit=1)])

    _run(model, AgentParams(step_effort="low"), pin=pin)

    for request in model.requests:
        assert request.pin.extra == {"provider_flag": 1, "reasoning": {"effort": "low"}}
    assert pin.extra == {"provider_flag": 1}  # the run's pin, used for the final answer, is intact


def test_default_step_effort_sends_the_run_pin_unchanged() -> None:
    model = ScriptedModel([call("find", limit=1)])

    _run(model)

    assert all(request.pin == PIN for request in model.requests)


# --- strategies and registry ------------------------------------------------------------


def _agent_for(name: str, send: ScriptedModel) -> GraphAgent:
    deps = LlmDeps(PIN, send, remaining_s=lambda: 5.0)
    agent = build_strategy(name, {}, need_toy().view(), llm=deps)
    assert isinstance(agent, GraphAgent)
    return agent


def test_the_low_steps_variant_is_registered_and_the_default_agent_is_not_low() -> None:
    low = _agent_for("graph_agent_low_steps", ScriptedModel([]))
    default = _agent_for("graph_agent", ScriptedModel([]))

    assert isinstance(low, GraphAgentLowSteps) and low.name == "graph_agent_low_steps"
    assert low.params.step_effort == "low" and default.params.step_effort == "default"


def test_the_agent_passes_its_remaining_budget_to_the_loop() -> None:
    model = ScriptedModel([])
    agent = _agent_for("graph_agent", model)

    result = agent.retrieve("What is on the plant?")

    assert model.requests == []  # 5 s left is under the 30 s reserve: no step was asked
    assert result.trace is not None and result.trace["stop_reason"] == "deadline"


def test_the_system_prompt_teaches_finish_with_call_and_evidence_of_absence() -> None:
    prompt = render_system_prompt(AgentParams(), primer=False, seeded=False)

    assert '"done": true}' in prompt and "to make one last call and finish with it" in prompt
    assert "no path, no match or no such tag is itself evidence" in prompt
