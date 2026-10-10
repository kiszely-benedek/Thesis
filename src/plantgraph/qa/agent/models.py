"""Parameters, steps and outcome of one agent loop (design §5.1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

#: Why the loop ended. `overflow`: the model's context window rejected the next prompt.
#: `runaway`: a step reply used the whole output-token cap (the model reasoned until cut off).
#: `deadline`: too little of the question's time budget was left to take another step.
StopReason = Literal[
    "done", "max_steps", "prompt_budget", "errors", "overflow", "runaway", "deadline"
]


class AgentParams(BaseModel):
    """Loop limits. Fixed by design, not tuned: tuning is paid at every point (design §5.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Most model replies (tool calls or `done`) in one question.
    max_steps: int = 6
    #: Longest rendered result shown to the model.
    observation_chars: int = 4_000
    #: Most items or edges one result lists; the full count is still reported.
    max_items_listed: int = 50
    #: Cap on the prompt characters summed over every call of the question.
    max_prompt_chars_total: int = 150_000
    #: Longest seed map (`hier_agent` only).
    seed_chars: int = 12_000
    #: `low` asks for low reasoning effort on step requests only; the final answer keeps the pin.
    step_effort: Literal["default", "low"] = "default"
    #: Seconds of the question budget kept for the final answer; stepping stops below it.
    final_reserve_s: float = 30.0


class AgentStep(BaseModel):
    """One model reply and what the loop did with it; kept in the trace."""

    model_config = ConfigDict(frozen=True)

    index: int
    reply_text: str
    #: The tool named, if the reply was a well-formed call; `None` for `done` or a malformed reply.
    tool: str | None
    args: dict[str, Any] | None
    #: Characters of the observation sent back (0 for `done`).
    observation_chars: int
    #: The rendering dropped items or was cut at `observation_chars`.
    truncated: bool
    #: What went wrong, if anything: a malformed reply, or a call the plant API refused.
    error: str | None
    touched_keys: tuple[str, ...]
    #: The call's own tokens, cost and latency (`from_cache` as the client reports it).
    usage: dict[str, Any]


class GatheredResult(BaseModel):
    """A successful call and its observation: one entry of the final context."""

    model_config = ConfigDict(frozen=True)

    call_text: str
    observation: str


class AgentRun(BaseModel):
    """Everything one loop produced."""

    model_config = ConfigDict(frozen=True)

    steps: tuple[AgentStep, ...]
    stop_reason: StopReason
    gathered: tuple[GatheredResult, ...]
    #: Well-formed calls the plant API refused: unknown tool, bad arguments, unknown tag or handle.
    tool_errors: int
    #: Replies that were not an action at all: not JSON, or neither a call nor `done`.
    invalid_actions: int

    @property
    def touched_keys(self) -> tuple[str, ...]:
        """Occurrence keys behind every result the model saw, sorted."""
        return tuple(sorted({key for step in self.steps for key in step.touched_keys}))
