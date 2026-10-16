"""The route one ask took, as the page shows it: query and rows, tool calls, and call costs.

Everything here is read from what was recorded on the wire (`trace_recorder.py`) and from the
call log, never recomputed. A part that could not be read keeps its raw text and says
`parsed=False`, so nothing is dropped silently.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class CypherStep(BaseModel):
    """The database tier: the query the model wrote and the rows it was then given."""

    model_config = ConfigDict(frozen=True)

    #: The strategy that wrote the query (the call log's name for the tier).
    tier: str
    query: str
    #: The text the final answering step saw: the query and its rows, verbatim.
    context: str
    #: The JSON lines of `context` read as objects; `()` when there were none or they did not parse.
    rows: tuple[dict[str, Any], ...] = ()
    #: The result was cut off at the tier's row cap (the model saw only the first rows).
    truncated: bool = False
    #: False when `context` did not have the expected shape (it is then kept whole).
    parsed: bool = True


class AgentStep(BaseModel):
    """One tool call of the agent tier, with what came back from it."""

    model_config = ConfigDict(frozen=True)

    #: 1-based position among the tool calls of one agent run.
    index: int
    tier: str
    #: The model's reply, verbatim.
    reply: str
    #: Empty when the reply was not a readable tool call.
    tool: str
    args: dict[str, Any]
    #: What the tool returned, as the model saw it; empty when it could not be found.
    observation: str
    #: Plant items named in `args` or `observation`: tags, and item ids of untagged items.
    items: tuple[str, ...] = ()
    #: False when the reply was not a tool call or its observation could not be found.
    parsed: bool = True


class TraceCall(BaseModel):
    """One model call of the ask, from the call log."""

    model_config = ConfigDict(frozen=True)

    purpose: str
    strategy: str
    latency_s: float
    cost_usd: float
    from_cache: bool
    #: `timeout`, `provider_error` ... when the call did not give a normal answer.
    error_kind: str | None


class AskTrace(BaseModel):
    """The whole route of one ask."""

    model_config = ConfigDict(frozen=True)

    cypher: tuple[CypherStep, ...] = ()
    agent: tuple[AgentStep, ...] = ()
    calls: tuple[TraceCall, ...] = ()
    #: HTTP attempts with no call-log line (retried after a transport error, or still in flight).
    unlogged_attempts: int = 0
    #: Why no trace could be built (the answer is still valid); `None` when all is well.
    error: str | None = None
