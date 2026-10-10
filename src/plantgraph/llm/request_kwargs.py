"""The keyword arguments the OpenAI SDK's `chat.completions.create` is called with."""

from __future__ import annotations

from typing import Any

from plantgraph.llm.models import ChatRequest


def build_request_kwargs(request: ChatRequest) -> dict[str, Any]:
    """Model, messages and the provider-routing extras for one request (§6)."""
    pin = request.pin
    extra_body: dict[str, Any] = dict(pin.extra)
    if pin.backend == "openrouter":
        # require_parameters: a host that would silently ignore temperature
        # or seed is excluded from routing instead of chosen anyway (§6).
        extra_body["require_parameters"] = True
        if pin.route_provider is not None:
            # allow_fallbacks=False: one model id must not be served by a
            # different host than the one pinned, run to run (§4).
            extra_body["provider"] = {"order": [pin.route_provider], "allow_fallbacks": False}
    kwargs: dict[str, Any] = {
        "model": pin.model_id,
        "messages": [message.model_dump() for message in request.messages],
        "max_tokens": pin.max_output_tokens,
        "extra_body": extra_body,
    }
    if pin.temperature is not None:
        kwargs["temperature"] = pin.temperature
    if pin.seed is not None:
        kwargs["seed"] = pin.seed
    if request.json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs
