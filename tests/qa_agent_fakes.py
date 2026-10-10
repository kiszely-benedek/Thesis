"""A scripted stand-in for the model, shared by the agent tests: it replays a list of replies."""

from __future__ import annotations

import json
from datetime import datetime

from plantgraph.llm.models import ChatRequest, ChatResponse, ContextOverflow, ModelPin

PIN = ModelPin(
    backend="openrouter",
    model_id="openai/gpt-5-mini",
    route_provider="openai",
    temperature=0.0,
    seed=1,
    max_output_tokens=64,
)

CALL_COST = 0.01
DONE = '{"done": true}'


def call(tool: str, **args: object) -> str:
    """The JSON reply that calls `tool`."""
    return json.dumps({"call": {"tool": tool, "args": args}})


class ScriptedModel:
    """A `SendChatRequest`: serves `replies` in order and keeps every request it was sent.

    Past the end of the script it keeps answering `done`; with `overflow_at` set, the call with
    that 0-based index raises `ContextOverflow`. `completion_tokens_at` overrides the reported
    completion tokens of a call (a cap-hit reply), `raise_at` makes a call raise the given error.
    """

    def __init__(
        self,
        replies: list[str],
        *,
        overflow_at: int | None = None,
        completion_tokens_at: dict[int, int] | None = None,
        raise_at: dict[int, Exception] | None = None,
    ) -> None:
        self._replies = replies
        self._overflow_at = overflow_at
        self._completion_tokens_at = completion_tokens_at or {}
        self._raise_at = raise_at or {}
        self.requests: list[ChatRequest] = []

    def __call__(self, request: ChatRequest) -> ChatResponse:
        index = len(self.requests)
        self.requests.append(request)
        if index == self._overflow_at:
            raise ContextOverflow("scripted overflow")
        if index in self._raise_at:
            raise self._raise_at[index]
        text = self._replies[index] if index < len(self._replies) else DONE
        return ChatResponse(
            text=text,
            prompt_tokens=10,
            completion_tokens=self._completion_tokens_at.get(index, 5),
            cost_usd=CALL_COST,
            latency_s=0.5,
            provider_response_id=None,
            finish_reason="stop",
            from_cache=False,
            created_at=datetime(2026, 10, 6),
        )

    def last_user_text(self, request_index: int = -1) -> str:
        """The text of the last message of a request (the latest observation)."""
        return self.requests[request_index].messages[-1].content
