"""The agent's action parser and bounded loop, driven by a scripted model on the toy plant."""

from __future__ import annotations

import pytest

from plantgraph.qa.agent.actions import Done, InvalidAction, ToolCall, parse_action
from plantgraph.qa.agent.loop import run_agent_loop
from plantgraph.qa.agent.models import AgentParams, AgentRun
from plantgraph.qa.agent.tool_text import compact_tool_reference
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.tool_registry import TOOLS
from qa_agent_fakes import DONE, PIN, ScriptedModel, call
from qa_plant_api_toy import toy_graph


def _run(model: ScriptedModel, **params: int) -> AgentRun:
    return run_agent_loop(
        pin=PIN,
        send=model,
        api=PlantApi(toy_graph()),
        system_prompt="SYSTEM",
        first_user_message="FIRST",
        params=AgentParams(**params),
    )


# --- parse_action -------------------------------------------------------------------


def test_a_call_and_done_are_read_and_args_default_to_an_empty_object() -> None:
    assert parse_action('{"call": {"tool": "find", "args": {"limit": 3}}}') == ToolCall(
        tool="find", args={"limit": 3}
    )
    assert parse_action('{"call": {"tool": "find"}}') == ToolCall(tool="find", args={})
    assert parse_action(DONE) == Done()


def test_a_fenced_reply_is_still_read() -> None:
    assert parse_action('```json\n{"done": true}\n```') == Done()


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("not json", "not JSON"),
        ("[1, 2]", "found list"),
        ("{}", "found keys"),
        ('{"done": false}', "found keys"),
        ('{"call": "find"}', 'expected "call"'),
        ('{"call": {"tool": "find", "args": [1]}}', 'expected "args"'),
    ],
)
def test_a_reply_that_is_not_an_action_says_what_was_expected(reply: str, expected: str) -> None:
    with pytest.raises(InvalidAction, match=expected):
        parse_action(reply)


# --- the loop -----------------------------------------------------------------------


def test_the_loop_runs_calls_in_order_feeds_each_result_back_and_stops_on_done() -> None:
    model = ScriptedModel(
        [
            call("find", where={"label": "OperatedValve"}),
            call("neighbours", of="$r1", direction="downstream", relations="flow"),
            DONE,
        ]
    )

    run = _run(model)

    assert run.stop_reason == "done" and len(run.steps) == 3
    assert [s.tool for s in run.steps] == ["find", "neighbours", None]
    assert [g.call_text.split("(")[0] for g in run.gathered] == ["find", "neighbours"]
    # the second request carries the first reply and its result under the handle `$r1`
    second = model.requests[1].messages
    assert [m.role for m in second] == ["system", "user", "assistant", "user"]
    assert second[-1].content.startswith("Result $r1:\n$r1: 2 items")
    assert all(r.json_mode and r.purpose == "agent_step" for r in model.requests)
    assert run.touched_keys and run.tool_errors == 0 and run.invalid_actions == 0


def test_done_on_the_first_reply_gathers_nothing() -> None:
    run = _run(ScriptedModel([DONE]))

    assert run.stop_reason == "done" and run.gathered == () and run.touched_keys == ()


def test_the_loop_stops_after_max_steps_and_keeps_the_last_result() -> None:
    model = ScriptedModel([call("find", limit=1)] * 10)

    run = _run(model, max_steps=3)

    assert run.stop_reason == "max_steps"
    assert len(model.requests) == 3 and len(run.gathered) == 3


def test_a_bad_reply_and_a_refused_call_are_shown_to_the_model_and_counted() -> None:
    model = ScriptedModel(
        ["oops", call("find", limit=1), call("find", where={"label": "Nope"}), call("find"), DONE]
    )

    run = _run(model)

    assert run.invalid_actions == 1 and run.tool_errors == 1
    assert run.stop_reason == "done"  # the errors were never two in a row
    assert model.last_user_text(1).startswith("error: expected a JSON object")
    assert model.last_user_text(3).startswith("error: expected a known label")
    assert [s.error is not None for s in run.steps] == [True, False, True, False, False]
    assert len(run.gathered) == 2  # errors are not evidence


def test_two_errors_in_a_row_stop_the_loop() -> None:
    model = ScriptedModel(["oops", call("nope"), call("find")])

    run = _run(model)

    assert run.stop_reason == "errors" and len(model.requests) == 2
    assert run.invalid_actions == 1 and run.tool_errors == 1


def test_an_unknown_handle_and_bad_arguments_are_tool_errors() -> None:
    model = ScriptedModel([call("filter", items="$r9", where={}), call("path", source="T1"), DONE])

    run = _run(model, max_steps=2)

    assert run.tool_errors == 2 and run.invalid_actions == 0
    assert "handles" in (run.steps[0].error or "") and "invalid arguments" in (
        run.steps[1].error or ""
    )


def test_the_cumulative_prompt_cap_stops_before_the_call_that_would_pass_it() -> None:
    model = ScriptedModel([call("find", limit=1)] * 5)

    run = _run(model, max_prompt_chars_total=1_000)

    assert run.stop_reason == "prompt_budget"
    assert 1 <= len(model.requests) < 5  # at least one fit; later, longer prompts did not


def test_a_context_overflow_ends_the_loop_with_what_was_gathered() -> None:
    model = ScriptedModel([call("find", limit=1)], overflow_at=1)

    run = _run(model)

    assert run.stop_reason == "overflow" and len(run.gathered) == 1


def test_a_cut_observation_is_flagged_truncated() -> None:
    run = _run(ScriptedModel([call("find"), DONE]), max_items_listed=2)

    assert run.steps[0].truncated is True
    assert "more not shown" in run.gathered[0].observation.splitlines()[0]


def test_the_compact_tool_reference_covers_every_registry_tool_and_argument() -> None:
    text = compact_tool_reference()

    for name, spec in TOOLS.items():
        line = next(line for line in text.splitlines() if line.startswith(f"{name}("))
        assert all(argument in line for argument in spec.args_model.model_fields)
    assert "limit?: integer = 50" in text and "direction: downstream|upstream|both" in text
    assert text.count("ItemFilter (") == 1 and len(text) < 2_000
