"""The pin, request/response and run-log data for the LLM client (design `qa-system.md` §4, §6).

Terms, because the reader may not know either the domain or ADR-0014's design:

- **model pin**: the frozen choice of provider, model id and generation
  parameters for one experiment run. "Frozen" matters because the thesis
  claim depends on where a model's context window fills up (ADR-0014); if
  the model changed mid-run, a reported number would no longer mean one
  thing.
- **cache key**: a hash identifying one exact request (see `cache.py`), so
  the same question asked twice returns the same cached answer instead of a
  second paid call.

Nothing in this module can hold an API key: `ChatRequest` has no such field,
and no request-shaped model ever will (see `qa-system.md` §6, "the key never
leaves the settings object"). Settings modules such as a future
`openrouter_settings.py` are the only place a credential lives.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

#: What an LLM call is *for*. Logged on every `CallRecord` so the run log can
#: be broken down by step; deliberately **not** part of the cache key (§6),
#: because the same prompt gets the same answer regardless of who asked.
CallPurpose = Literal[
    "answer", "cypher", "route", "judge", "probe", "pathrag_step", "embed", "agent_step"
]


def canonical_hash(payload: Any) -> str:
    """Sha256 of `payload` as sorted-key JSON.

    Used everywhere a hash must be identical across processes and Python
    versions — `ModelPin.pin_hash` and the cache key function in `cache.py`.
    Sorting keys removes dict-ordering as a source of difference; sha256
    (not the builtin `hash()`) removes `PYTHONHASHSEED` randomization as one.
    """
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ModelPin(BaseModel):
    """One frozen model configuration: provider, model id and every generation parameter."""

    model_config = ConfigDict(frozen=True)

    backend: Literal["openrouter", "local"]
    model_id: str
    #: OpenRouter provider slug. Sent with `allow_fallbacks=False` (client.py, §6) so one
    #: model id cannot silently be served by different hosts run to run.
    route_provider: str | None = None
    temperature: float | None = None
    seed: int | None = None
    max_output_tokens: int
    #: Backend-specific extras, e.g. a reasoning-effort setting. Part of the pin: two
    #: runs differing only here are two different configurations.
    extra: dict[str, Any] = Field(default_factory=dict)

    def pin_hash(self) -> str:
        """Stable identifier for this exact configuration, for `RunConfig` and `CallRecord`."""
        return canonical_hash(self.model_dump(mode="json"))


class ChatMessage(BaseModel):
    """One message of a chat prompt, in the OpenAI-compatible shape every backend speaks."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Everything needed to ask a model one question — and nothing that could authenticate it.

    There is deliberately no field here for an API key or any other
    credential: a `ChatRequest` is cached and logged, so anything it could
    hold would end up on disk (§6).
    """

    model_config = ConfigDict(frozen=True)

    pin: ModelPin
    messages: list[ChatMessage]
    json_mode: bool = False
    #: Logged for the run-log breakdown; excluded from the cache key (see `CallPurpose`).
    purpose: CallPurpose


class ChatResponse(BaseModel):
    """One model reply, with the usage and timing data ADR-0014 requires on every cache entry."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    #: As reported by the provider's own `usage` block — never computed from a remembered
    #: price, because prices change and would silently go stale (`qa-system.md` §4).
    cost_usd: float | None
    latency_s: float
    provider_response_id: str | None
    finish_reason: str | None
    #: True when this `ChatResponse` came from the cache rather than a live call.
    from_cache: bool
    created_at: datetime


CallErrorKind = Literal["context_overflow", "provider_error", "timeout", "late_after_timeout"]

#: `finish_reason` of the cache entry written when a call is abandoned (a "tombstone").
TIMEOUT_FINISH_REASON = "client_timeout"


class CallRecord(BaseModel):
    """One line of a run's `calls.jsonl`: every LLM call it made, cached or not."""

    run_id: str
    question_id: str | None = None
    strategy: str | None = None
    purpose: CallPurpose
    cache_key: str
    pin_hash: str
    prompt_sha256: str
    #: `None` when the call failed before a response existed; see `error_kind`.
    response: ChatResponse | None = None
    #: `timeout`: the call was abandoned at its deadline. `late_after_timeout`: an abandoned
    #: call answered after all; `response` holds that answer, which is billed but never cached.
    error_kind: CallErrorKind | None = None


def tombstone_response(timeout_s: float) -> ChatResponse:
    """The cache entry for an abandoned call: empty, free, as long as the budget it ran out of."""
    return ChatResponse(
        text="",
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        latency_s=timeout_s,
        provider_response_id=None,
        finish_reason=TIMEOUT_FINISH_REASON,
        from_cache=False,
        created_at=datetime.now(UTC),
    )


class ContextWall(BaseModel):
    """The largest prompt size a pinned model accepts, as measured by the pilot's binary search."""

    pin_hash: str
    max_ok_chars: int
    #: `None` until the search has found a rejected size at all.
    min_rejected_chars: int | None = None
    measured_at: datetime
    probe_corpus_ids: list[str]


class ContextOverflow(Exception):
    """The provider reported that the prompt exceeded the model's context window."""


class ProviderError(Exception):
    """The provider returned an error other than a context overflow."""


class CacheMiss(Exception):
    """Replay mode found no cached response for a request and made no network call."""


class RequestTimedOut(Exception):
    """A model call outlived its wall-clock budget and was abandoned (or a tombstone says so).

    `latency_s` is the budget the call was given; the question's latency meter counts it
    as time spent, live and on replay alike.
    """

    def __init__(self, message: str, latency_s: float) -> None:
        super().__init__(message)
        self.latency_s = latency_s


class QuestionDeadline(Exception):
    """The question's recorded call time already reached its deadline, so no call was started."""
