"""A scripted OpenAI-compatible transport for tests — makes no network call.

Design `qa-system.md` §6, §16. Every `ChatClient` test in this project
injects one of these instead of a real HTTP connection, via
`openai.OpenAI(http_client=...)`. `httpx2.MockTransport` (`httpx2` is the
`httpx` fork the `openai` SDK vendors as its own transport layer) never
opens a socket: it hands the outgoing request straight to
`FakeTransport.handler`, so a test can prove a code path made "zero
transport calls" simply by checking `len(transport.requests)`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import httpx2

from plantgraph.llm.models import ChatMessage

#: Wording for the scripted context-overflow error. **Not an observed
#: OpenRouter message** — the pilot's wall probe (`qa-system.md` §12 step 2)
#: records the real text per model before any reported run. This is only a
#: stand-in for exercising `ChatClient`'s detection logic ahead of that
#: measurement, and is flagged as unverified in the design note.
SCRIPTED_OVERFLOW_MESSAGE = (
    "This model's maximum context length was exceeded by the supplied messages."
)


def message_hash(messages: list[ChatMessage]) -> str:
    """Deterministic key for a prompt, so a test can script a reply for it ahead of time.

    Requests carry no `purpose` field on the wire (`ChatRequest.purpose` is
    logged, never sent — `cache.py` excludes it from the cache key for the
    same reason), so a scripted reply is matched by prompt content alone.
    """
    return _hash_message_dicts([message.model_dump() for message in messages])


def _hash_message_dicts(messages: list[dict[str, Any]]) -> str:
    payload = json.dumps(messages, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScriptedReply:
    """One canned, successful chat-completion reply."""

    text: str
    prompt_tokens: int = 10
    completion_tokens: int = 5
    cost_usd: float | None = 0.0001
    finish_reason: str = "stop"


@dataclass
class FakeTransport:
    """Serves scripted replies and transport failures for `ChatClient` tests.

    Args:
        default_reply: served for any request whose prompt is not in `replies_by_message_hash`.
        replies_by_message_hash: extra replies for specific prompts, keyed by `message_hash`.
        fail_times: how many leading requests get `fail_status` before a real
            reply is served — scripts "429-then-success" with `fail_times=1`.
        fail_status: the HTTP status of those leading failures (429 or 5xx).
        context_wall_chars: if set, a request whose messages' combined length
            exceeds this many characters gets the scripted overflow error
            instead of any reply, regardless of `fail_times`.
        echo_authorization_header: if set, every error response embeds the
            request's raw `Authorization` header value in its body — used
            only by the key-hygiene test, to prove `ChatClient` redacts it
            before the value can reach an exception, a log or `calls.jsonl`.
    """

    default_reply: ScriptedReply = field(default_factory=lambda: ScriptedReply(text="ok"))
    replies_by_message_hash: dict[str, ScriptedReply] = field(default_factory=dict)
    fail_times: int = 0
    fail_status: int = 429
    context_wall_chars: int | None = None
    echo_authorization_header: bool = False
    #: Every request this transport has handled, in order — assert on its
    #: length to prove a code path made zero (or exactly N) transport calls.
    requests: list[httpx2.Request] = field(default_factory=list, init=False)

    def as_httpx_client(self) -> httpx2.Client:
        """An `httpx2.Client` whose transport is this fake; pass as `ChatClient`'s `http_client`."""
        return httpx2.Client(transport=httpx2.MockTransport(self.handler))

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        """The `MockTransport` callback: inspect the request, return a scripted response."""
        self.requests.append(request)
        body = json.loads(request.content.decode("utf-8"))
        messages: list[dict[str, Any]] = body.get("messages", [])
        prompt_chars = sum(len(message.get("content", "")) for message in messages)

        if self.context_wall_chars is not None and prompt_chars > self.context_wall_chars:
            return self._error_response(
                400, "context_length_exceeded", SCRIPTED_OVERFLOW_MESSAGE, request
            )
        if len(self.requests) <= self.fail_times:
            return self._error_response(
                self.fail_status, "transient_error", "Scripted transport failure", request
            )
        reply = self.replies_by_message_hash.get(_hash_message_dicts(messages), self.default_reply)
        return self._success_response(reply, model=body.get("model", "fake-model"))

    def _success_response(self, reply: ScriptedReply, *, model: str) -> httpx2.Response:
        payload = {
            "id": "fake-completion",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reply.text},
                    "finish_reason": reply.finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": reply.prompt_tokens,
                "completion_tokens": reply.completion_tokens,
                "total_tokens": reply.prompt_tokens + reply.completion_tokens,
                "cost": reply.cost_usd,
            },
        }
        return httpx2.Response(200, json=payload)

    def _error_response(
        self, status: int, code: str, message: str, request: httpx2.Request
    ) -> httpx2.Response:
        if self.echo_authorization_header:
            header_value = request.headers.get("authorization", "")
            message = f"{message} (request had Authorization: {header_value})"
        payload = {"error": {"message": message, "code": code, "type": "invalid_request_error"}}
        return httpx2.Response(status, json=payload)
