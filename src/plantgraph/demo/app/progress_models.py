"""What the page shows while an ask runs: one event per model attempt, newest last."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

#: What the attempt is for. `unknown` means neither the call log nor the prompt says.
Phase = Literal["cypher", "answer", "agent_step", "unknown"]
EventState = Literal["running", "done", "failed"]

#: The client tries a call once and retries it five times (`ChatClient`'s default `max_retries`).
MAX_ATTEMPTS = 6


class ProgressEvent(BaseModel):
    """One HTTP attempt to the model provider, as the visitor should see it."""

    model_config = ConfigDict(frozen=True)

    phase: Phase
    state: EventState
    #: Seconds into the ask when the attempt was sent.
    started_s: float
    #: Seconds the attempt took; for a running one, how long it has been waiting so far.
    elapsed_s: float
    #: 1-based; counts up while the same request is sent again after a failure.
    attempt: int
    #: The provider's HTTP status when it replied with an error (for example 502).
    http_status: int | None = None
    #: The exception class when no reply came at all (for example `ReadTimeout`).
    error: str | None = None
    #: The Cypher query of a finished query call, or the `tool(args)` of a finished agent step.
    summary: str | None = None
    #: The first line of what the agent's tool returned, once the next request shows it.
    detail: str | None = None
    #: 1-based number of the agent action this attempt belongs to; `None` for other phases.
    action: int | None = None


class LiveProgress(BaseModel):
    """The attempts of the running (or just finished) ask, in the order they were sent."""

    model_config = ConfigDict(frozen=True)

    events: tuple[ProgressEvent, ...] = ()
    #: How many times one call is tried in all (the page says "attempt 2 of 6").
    max_attempts: int = MAX_ATTEMPTS


class LostTime(BaseModel):
    """Time the model provider's errors cost: measured, never estimated."""

    model_config = ConfigDict(frozen=True)

    failed_attempts: int = 0
    lost_s: float = 0.0
