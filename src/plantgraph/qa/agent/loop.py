"""The bounded agent loop (design §5.1): ask, run one tool, show the result, repeat.

The loop needs only a sender (a function from `ChatRequest` to `ChatResponse`), so tests drive
it with a scripted fake and the harness gives it the metered sender that counts every call
towards the question's cost and the run's spend cap.

Seven things end it: `done` (a reply of `{"done": true}`, or a call sent with `"done": true`
that succeeded), `max_steps` replies, a cumulative prompt size over the cap (`prompt_budget`), two
bad replies in a row (`errors`), a context overflow (`overflow`), a reply that used the whole output
cap (`runaway`) and a spent time budget (`deadline`). However it ends, the caller still runs the
final answer step on what was gathered.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from plantgraph.llm.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ContextOverflow,
    ModelPin,
    QuestionDeadline,
    RequestTimedOut,
)
from plantgraph.qa.agent.actions import Done, InvalidAction, ToolCall, parse_action
from plantgraph.qa.agent.models import AgentParams, AgentRun, AgentStep, GatheredResult, StopReason
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.plant_api.model import PlantApiError
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import render_was_cut
from plantgraph.qa.plant_api.tool_registry import call_tool

#: Two replies in a row that fail (malformed or refused) mean the model is not recovering.
_MAX_ERRORS_IN_A_ROW = 2

#: Seconds of the question's time budget still unspent, or `None` when the run has no deadline.
RemainingSeconds = Callable[[], float | None]


def run_agent_loop(
    *,
    pin: ModelPin,
    send: SendChatRequest,
    api: PlantApi,
    system_prompt: str,
    first_user_message: str,
    params: AgentParams,
    remaining_s: RemainingSeconds | None = None,
) -> AgentRun:
    """Run the loop for one question; never raises for a bad reply, only reports it.

    `remaining_s` tells how much of the question's time budget is left; below
    `params.final_reserve_s` the loop stops so the final answer still fits.
    A provider error from `send` is not caught: the harness records it for the question.
    """
    loop = _Loop(pin, send, api, params, system_prompt, first_user_message, remaining_s)
    stop_reason = loop.run()
    return AgentRun(
        steps=tuple(loop.steps),
        stop_reason=stop_reason,
        gathered=tuple(loop.gathered),
        tool_errors=loop.tool_errors,
        invalid_actions=loop.invalid_actions,
    )


class _Loop:
    """The state of one question's loop; `run` returns why it stopped."""

    def __init__(
        self,
        pin: ModelPin,
        send: SendChatRequest,
        api: PlantApi,
        params: AgentParams,
        system_prompt: str,
        first_user_message: str,
        remaining_s: RemainingSeconds | None,
    ) -> None:
        self._pin = _step_pin(pin, params)
        self._remaining_s = remaining_s
        self._send = send
        self._api = api
        self._params = params
        self._messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=first_user_message),
        ]
        self._prompt_chars_sent = 0
        self._errors_in_a_row = 0
        self.steps: list[AgentStep] = []
        self.gathered: list[GatheredResult] = []
        self.tool_errors = 0
        self.invalid_actions = 0

    def run(self) -> StopReason:
        for index in range(1, self._params.max_steps + 1):
            if self._budget_is_short():
                return "deadline"
            request = ChatRequest(
                pin=self._pin, messages=list(self._messages), json_mode=True, purpose="agent_step"
            )
            request_chars = sum(len(m.content) for m in request.messages)
            if self._prompt_chars_sent + request_chars > self._params.max_prompt_chars_total:
                return "prompt_budget"
            try:
                response = self._send(request)
            except ContextOverflow:
                return "overflow"
            except (QuestionDeadline, RequestTimedOut):
                return "deadline"  # the harness ran out of time inside this step
            self._prompt_chars_sent += request_chars
            if response.completion_tokens >= self._pin.max_output_tokens:
                self._record_runaway(index, response)
                return "runaway"
            if self._take_reply(index, response):
                return "done"
            if self._errors_in_a_row >= _MAX_ERRORS_IN_A_ROW:
                return "errors"
        return "max_steps"

    def _budget_is_short(self) -> bool:
        remaining = None if self._remaining_s is None else self._remaining_s()
        return remaining is not None and remaining < self._params.final_reserve_s

    def _record_runaway(self, index: int, response: ChatResponse) -> None:
        """A reply cut off at the output cap is not trusted, even if the cut text parses."""
        self.invalid_actions += 1
        message = (
            f"error: reply used all {self._pin.max_output_tokens} output tokens and was cut off"
        )
        self.steps.append(_step(index, response, None, None, message, False, message, ()))

    def _take_reply(self, index: int, response: ChatResponse) -> bool:
        """Handle one reply; True when the loop should stop (`done`, or a call sent with done)."""
        try:
            action = parse_action(response.text)
        except InvalidAction as error:
            self.invalid_actions += 1
            self._record_error(index, response, f"error: {error}", tool=None, args=None)
            return False
        if isinstance(action, Done):
            self._errors_in_a_row = 0
            self.steps.append(_step(index, response, None, None, "", False, None, ()))
            return True
        succeeded = self._run_tool(index, response, action)
        return succeeded and action.finish  # a refused call with done: keep going

    def _run_tool(self, index: int, response: ChatResponse, action: ToolCall) -> bool:
        """Run the call; False when the plant API refused it."""
        try:
            result = call_tool(self._api, action.tool, action.args)
        except PlantApiError as error:
            self.tool_errors += 1
            self._record_error(index, response, f"error: {error}", action.tool, action.args)
            return False
        self._errors_in_a_row = 0
        text = result.render(self._params.observation_chars, self._params.max_items_listed)
        truncated = render_was_cut(text, self._params.observation_chars)
        call_text = f"{action.tool}({json.dumps(action.args, sort_keys=True)})"
        self.gathered.append(GatheredResult(call_text=call_text, observation=text))
        self.steps.append(
            _step(
                index,
                response,
                action.tool,
                action.args,
                text,
                truncated,
                None,
                result.touched_keys,
            )
        )
        self._show(response, f"Result {result.handle}:\n{text}")
        return True

    def _record_error(
        self,
        index: int,
        response: ChatResponse,
        message: str,
        tool: str | None,
        args: dict[str, Any] | None,
    ) -> None:
        self._errors_in_a_row += 1
        self.steps.append(_step(index, response, tool, args, message, False, message, ()))
        self._show(response, message)

    def _show(self, response: ChatResponse, observation: str) -> None:
        """Add the model's reply and our answer to it, ready for the next step."""
        self._messages.append(ChatMessage(role="assistant", content=response.text))
        self._messages.append(ChatMessage(role="user", content=observation))


def _step_pin(pin: ModelPin, params: AgentParams) -> ModelPin:
    """The pin for step requests: low reasoning effort if asked, else the run's pin unchanged."""
    if params.step_effort == "default":
        return pin
    return pin.model_copy(update={"extra": {**pin.extra, "reasoning": {"effort": "low"}}})


def _step(
    index: int,
    response: ChatResponse,
    tool: str | None,
    args: dict[str, Any] | None,
    observation: str,
    truncated: bool,
    error: str | None,
    touched_keys: tuple[str, ...],
) -> AgentStep:
    return AgentStep(
        index=index,
        reply_text=response.text,
        tool=tool,
        args=args,
        observation_chars=len(observation),
        truncated=truncated,
        error=error,
        touched_keys=touched_keys,
        usage={
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "cost_usd": response.cost_usd,
            "latency_s": response.latency_s,
            "from_cache": response.from_cache,
        },
    )
