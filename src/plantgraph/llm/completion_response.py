"""Turn the SDK's completion object into this project's `ChatResponse`."""

from __future__ import annotations

from datetime import UTC, datetime

from openai.types.chat import ChatCompletion

from plantgraph.llm.models import ChatResponse
from plantgraph.llm.served_by import served_by


def response_from_completion(completion: ChatCompletion, latency_s: float) -> ChatResponse:
    """Copy the fields we record; `latency_s` is the time the one request took."""
    choice = completion.choices[0]
    usage = completion.usage
    return ChatResponse(
        # A `None` content (e.g. a provider that returns only a refusal or a tool call) is
        # left as an empty string; this project never sends tool definitions, so an empty
        # answer is treated downstream as a parse failure, not masked as a client error.
        text=choice.message.content or "",
        prompt_tokens=usage.prompt_tokens if usage is not None else 0,
        completion_tokens=usage.completion_tokens if usage is not None else 0,
        # OpenRouter's `usage` block adds a `cost` field (§4); the SDK keeps
        # unknown fields, so it is read as a plain attribute, not a typed one.
        cost_usd=getattr(usage, "cost", None) if usage is not None else None,
        latency_s=latency_s,
        provider_response_id=completion.id,
        finish_reason=choice.finish_reason,
        from_cache=False,
        created_at=datetime.now(UTC),
        provider=served_by(completion),  # OpenRouter's top-level `provider` field
    )
