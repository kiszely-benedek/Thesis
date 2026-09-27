"""An OpenAI-compatible chat client for OpenRouter and a generic local backend.

Design `qa-system.md` §3, §6. **OpenRouter** is a hosted gateway that
exposes many providers' language models through one OpenAI-compatible HTTP
API; this project talks to it instead of calling any single model vendor's
API directly. A "local" backend (a self-hosted model server on the
developer's machine) plugs into the same client through the same code path
— only the base URL and key differ. No local runtime is installed on this
machine (`local_settings.py`), so only the OpenRouter path is ever
exercised for real; "local" is exercised only through `fake_transport.py`.

Every call goes through the SQLite cache from `cache.py` first (ADR-0014): a
cache hit never reaches the network, and a miss in `"replay"` mode raises
`CacheMiss` instead of spending money. `allow_network` is a second,
independent guard on top of that: even a cache configured in `"live"` mode
will not be asked to fetch anything unless this client was built with
`allow_network=True`. That flag is never read from the environment or
`.env` — only an explicit `--allow-paid-calls` CLI flag the user types is
allowed to set it (§6, the paid-call guard), so a stored `OPENROUTER_API_KEY`
is never mistaken for permission to spend money.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx2
import openai
from pydantic import SecretStr

from plantgraph.llm.cache import SqliteCache, cache_key
from plantgraph.llm.local_settings import LocalLLMSettings
from plantgraph.llm.models import (
    CacheMiss,
    CallRecord,
    ChatRequest,
    ChatResponse,
    ContextOverflow,
    ProviderError,
    canonical_hash,
)
from plantgraph.llm.openrouter_settings import OpenRouterSettings

logger = logging.getLogger(__name__)

#: Substrings of an OpenAI-style "context length exceeded" error.
#: **Unverified for OpenRouter**: the pilot's wall probe (`qa-system.md` §12
#: step 2) records the exact wording per model before any reported run.
#: This list matches the closest publicly documented convention (OpenAI's
#: own error code and message shape), not an observed OpenRouter response.
_CONTEXT_OVERFLOW_MARKERS = (
    "maximum context length",
    "context length exceeded",
    "context_length_exceeded",
    "context window",
)

#: Placeholder credential for the "local" backend, which needs some non-empty
#: string to satisfy the SDK's constructor but authenticates nothing (no
#: local runtime checks it — `local_settings.py`).
_LOCAL_PLACEHOLDER_API_KEY = "local-backend-no-key-required"


def _is_retryable_status(status_code: int) -> bool:
    """429 (rate limit) and any 5xx are transport-only failures worth a retry.

    Any other 4xx is a content or configuration problem — retrying it would
    just repeat the same mistake, so `_call_with_retries` raises immediately
    instead (§6, "nothing is retried on content").
    """
    return status_code == 429 or status_code >= 500


def _looks_like_context_overflow(error_code: str | None, message: str) -> bool:
    """Best-effort match for a "the prompt is too long" provider error.

    See the module-level note: the wording is unverified until the pilot
    runs the wall probe against OpenRouter.
    """
    if error_code == "context_length_exceeded":
        return True
    lowered = message.lower()
    return any(marker in lowered for marker in _CONTEXT_OVERFLOW_MARKERS)


def _redact(text: str, secret: SecretStr | None) -> str:
    """Replace `secret`'s value with `***` wherever it appears in `text`.

    Guards against a provider that echoes request headers — including
    `Authorization` — back inside an error body: that value must never reach
    an exception message, a log line, or `calls.jsonl` (§6).
    """
    if secret is None:
        return text
    value = secret.get_secret_value()
    if not value:
        return text
    return text.replace(value, "***")


def _prompt_sha256(request: ChatRequest) -> str:
    """Hash of the prompt's messages, recorded on `CallRecord` for traceability."""
    return canonical_hash([message.model_dump(mode="json") for message in request.messages])


_StatusErrorOutcome = Literal["overflow", "retry", "fatal"]


def _classify_status_error(
    exc: openai.APIStatusError, secret: SecretStr | None
) -> tuple[_StatusErrorOutcome, str]:
    """What `_call_with_retries` should do about one provider status error."""
    message = _redact(str(exc), secret)
    if _looks_like_context_overflow(exc.code, message):
        return "overflow", message
    if _is_retryable_status(exc.status_code):
        return "retry", message
    return "fatal", message


class ChatClient:
    """Sends `ChatRequest`s to one OpenAI-compatible backend, through the cache.

    One instance talks to one backend (OpenRouter or local) at one base URL
    — build it with `for_openrouter` or `for_local` rather than the
    constructor directly.
    """

    def __init__(
        self,
        *,
        backend: Literal["openrouter", "local"],
        base_url: str,
        api_key: SecretStr | None,
        cache: SqliteCache,
        calls_log_path: Path,
        allow_network: bool,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        http_client: httpx2.Client | None = None,
    ) -> None:
        self._backend = backend
        self._api_key = api_key
        self._cache = cache
        self._calls_log_path = calls_log_path
        self._allow_network = allow_network
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        raw_key = api_key.get_secret_value() if api_key is not None else _LOCAL_PLACEHOLDER_API_KEY
        self._sdk_client = openai.OpenAI(
            base_url=base_url,
            api_key=raw_key,
            # ChatClient does its own retries below, on transport errors only,
            # so the SDK's built-in (opaque, content-agnostic) retrying is off.
            max_retries=0,
            http_client=http_client,
        )
        self._calls_log_path.parent.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return f"ChatClient(backend={self._backend!r}, base_url={self._sdk_client.base_url!r})"

    @classmethod
    def for_openrouter(
        cls,
        settings: OpenRouterSettings,
        *,
        cache: SqliteCache,
        calls_log_path: Path,
        allow_network: bool,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        http_client: httpx2.Client | None = None,
    ) -> ChatClient:
        """Build a client for OpenRouter's OpenAI-compatible endpoint."""
        return cls(
            backend="openrouter",
            base_url=settings.base_url,
            api_key=settings.api_key,
            cache=cache,
            calls_log_path=calls_log_path,
            allow_network=allow_network,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            http_client=http_client,
        )

    @classmethod
    def for_local(
        cls,
        settings: LocalLLMSettings,
        *,
        cache: SqliteCache,
        calls_log_path: Path,
        allow_network: bool,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        http_client: httpx2.Client | None = None,
    ) -> ChatClient:
        """Build a client for a local, OpenAI-compatible model server (§6: none installed here)."""
        return cls(
            backend="local",
            base_url=settings.base_url,
            api_key=None,
            cache=cache,
            calls_log_path=calls_log_path,
            allow_network=allow_network,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            http_client=http_client,
        )

    def complete(
        self,
        request: ChatRequest,
        *,
        run_id: str,
        question_id: str | None = None,
        strategy: str | None = None,
    ) -> ChatResponse:
        """Answer `request`, through the cache, logging one line to `calls.jsonl`.

        Raises:
            CacheMiss: the cache is in `"replay"` mode, or this client has
                `allow_network=False`, and nothing is cached for `request`.
            ContextOverflow: the provider reported the prompt exceeded its context window.
            ProviderError: any other provider error, after transport retries were exhausted.
        """
        cached = self._cache.get(request)  # raises CacheMiss itself in "replay" mode
        if cached is not None:
            # The stored value's own `from_cache` is whatever it was when
            # first written (False, for an original live call); it is this
            # retrieval, not the write, that makes the flag true.
            response = cached.model_copy(update={"from_cache": True})
            self._log_call(
                request, run_id, question_id, strategy, response=response, error_kind=None
            )
            return response
        if not self._allow_network:
            raise CacheMiss(
                f"No cached response for purpose={request.purpose!r}, and this client has "
                "allow_network=False: refusing to make a network call without the user's "
                "explicit --allow-paid-calls approval (qa-system.md §6)"
            )
        try:
            response = self._call_with_retries(request)
        except ContextOverflow:
            self._log_call(
                request, run_id, question_id, strategy, response=None, error_kind="context_overflow"
            )
            raise
        except ProviderError:
            self._log_call(
                request, run_id, question_id, strategy, response=None, error_kind="provider_error"
            )
            raise
        self._cache.put(request, response)
        self._log_call(request, run_id, question_id, strategy, response=response, error_kind=None)
        return response

    def _call_with_retries(self, request: ChatRequest) -> ChatResponse:
        """Retry only on a transport-level failure (429 or 5xx); never on a content error."""
        attempt = 0
        while True:
            try:
                return self._call_once(request)
            except openai.APIStatusError as exc:
                outcome, message = _classify_status_error(exc, self._api_key)
                if outcome == "overflow":
                    raise ContextOverflow(message) from exc
                if outcome == "fatal" or attempt >= self._max_retries:
                    raise ProviderError(message) from exc
            except openai.APIConnectionError as exc:
                if attempt >= self._max_retries:
                    raise ProviderError(_redact(str(exc), self._api_key)) from exc
            attempt += 1
            self._wait_before_retry(request.purpose, attempt)

    def _wait_before_retry(self, purpose: str, attempt: int) -> None:
        backoff = self._backoff_base_seconds * (2 ** (attempt - 1))
        logger.warning(
            "Retrying %s call after a transport error (attempt %d/%d, waiting %.2fs)",
            purpose,
            attempt,
            self._max_retries,
            backoff,
        )
        if backoff > 0:
            time.sleep(backoff)

    def _call_once(self, request: ChatRequest) -> ChatResponse:
        kwargs = self._build_request_kwargs(request)
        started = time.monotonic()
        completion = self._sdk_client.chat.completions.create(**kwargs)
        latency_s = time.monotonic() - started

        choice = completion.choices[0]
        usage = completion.usage
        return ChatResponse(
            # A `None` content (e.g. a provider that returns only a refusal
            # or a tool call) is left as an empty string here; this project
            # never sends tool definitions, so an empty answer is treated
            # downstream as a parse failure, not masked as a client error.
            text=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage is not None else 0,
            completion_tokens=usage.completion_tokens if usage is not None else 0,
            # OpenRouter's `usage` block extends the standard OpenAI shape
            # with a `cost` field (§4); the SDK keeps unknown fields, so it
            # is read as a plain attribute rather than a typed one.
            cost_usd=getattr(usage, "cost", None) if usage is not None else None,
            latency_s=latency_s,
            provider_response_id=completion.id,
            finish_reason=choice.finish_reason,
            from_cache=False,
            created_at=datetime.now(UTC),
        )

    def _build_request_kwargs(self, request: ChatRequest) -> dict[str, Any]:
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

    def _log_call(
        self,
        request: ChatRequest,
        run_id: str,
        question_id: str | None,
        strategy: str | None,
        *,
        response: ChatResponse | None,
        error_kind: Literal["context_overflow", "provider_error"] | None,
    ) -> None:
        record = CallRecord(
            run_id=run_id,
            question_id=question_id,
            strategy=strategy,
            purpose=request.purpose,
            cache_key=cache_key(request),
            pin_hash=request.pin.pin_hash(),
            prompt_sha256=_prompt_sha256(request),
            response=response,
            error_kind=error_kind,
        )
        with self._calls_log_path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json())
            handle.write("\n")
