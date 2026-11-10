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
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx2
import openai
from pydantic import SecretStr

from plantgraph.llm.abandonable_call import start_daemon_call
from plantgraph.llm.cache import SqliteCache, cache_key
from plantgraph.llm.completion_response import response_from_completion
from plantgraph.llm.local_settings import LocalLLMSettings
from plantgraph.llm.models import (
    OVERFLOW_FINISH_REASON,
    TIMEOUT_FINISH_REASON,
    CacheMiss,
    CallErrorKind,
    CallRecord,
    ChatRequest,
    ChatResponse,
    ContextOverflow,
    ProviderError,
    RequestTimedOut,
    canonical_hash,
    overflow_response,
    tombstone_response,
)
from plantgraph.llm.openrouter_settings import OpenRouterSettings
from plantgraph.llm.request_kwargs import build_request_kwargs
from plantgraph.llm.retry_loop import LiveResult, call_with_retries
from plantgraph.llm.single_flight import SingleFlight

logger = logging.getLogger(__name__)

#: Placeholder credential for the "local" backend, which needs some non-empty
#: string to satisfy the SDK's constructor but authenticates nothing (no
#: local runtime checks it — `local_settings.py`).
_LOCAL_PLACEHOLDER_API_KEY = "local-backend-no-key-required"


@dataclass(frozen=True)
class CallOrigin:
    """Who asked: the labels one `calls.jsonl` line carries."""

    run_id: str
    question_id: str | None
    strategy: str | None


def _prompt_sha256(request: ChatRequest) -> str:
    """Hash of the prompt's messages, recorded on `CallRecord` for traceability."""
    return canonical_hash([message.model_dump(mode="json") for message in request.messages])


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
        self._log_lock = threading.Lock()  # appends to calls.jsonl may come from several threads
        self._single_flight = SingleFlight()
        #: Told about the answer of a call that was abandoned and then came back: the harness
        #: points this at the spend guard, so money the abandoned call cost is still counted.
        self.on_late_response: Callable[[ChatResponse], None] | None = None

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
        timeout_s: float | None = None,
    ) -> ChatResponse:
        """Answer `request`, through the cache, logging one line to `calls.jsonl`.

        Args:
            request: what to ask.
            run_id: with `question_id` and `strategy`, labels the `calls.jsonl` line.
            question_id: see `run_id`.
            strategy: see `run_id`.
            timeout_s: wall-clock budget for a live call; `None` waits as long as it takes.

        Raises:
            CacheMiss: the cache is in `"replay"` mode, or this client has
                `allow_network=False`, and nothing is cached for `request`.
            ContextOverflow: the provider reported the prompt exceeded its context window.
            ProviderError: any other provider error, after transport retries were exhausted.
            RequestTimedOut: the call outlived `timeout_s`, or the cache holds a tombstone
                of an earlier call that outlived a budget at least this large.
        """
        # one call per prompt at a time: a second thread asking the same thing finds the cache full
        with self._single_flight.hold(cache_key(request)):
            origin = CallOrigin(run_id, question_id, strategy)
            return self._complete(request, origin, timeout_s)

    def _complete(
        self,
        request: ChatRequest,
        origin: CallOrigin,
        timeout_s: float | None,
    ) -> ChatResponse:
        cached = self._cache.get(request)  # raises CacheMiss itself in "replay" mode
        if cached is not None and cached.finish_reason == OVERFLOW_FINISH_REASON:
            self._log_call(request, origin, response=None, error_kind="context_overflow")
            raise ContextOverflow(cached.text)  # the same prompt overflows the same way
        if cached is not None:
            self._raise_if_over_budget(cached, timeout_s, request, origin)
        if cached is not None and cached.finish_reason == TIMEOUT_FINISH_REASON:
            cached = None  # a tombstone of a smaller budget: this call may try again
        if cached is not None:
            # The stored value's own `from_cache` is whatever it was when
            # first written (False, for an original live call); it is this
            # retrieval, not the write, that makes the flag true.
            response = cached.model_copy(update={"from_cache": True})
            self._log_call(request, origin, response=response, error_kind=None)
            return response
        if not self._allow_network:
            raise CacheMiss(
                f"No cached response for purpose={request.purpose!r}, and this client has "
                "allow_network=False: refusing to make a network call without the user's "
                "explicit --allow-paid-calls approval (qa-system.md §6)"
            )
        live = self._live_with_error_log(request, origin, timeout_s)
        self._cache.put(request, live.response)
        self._log_call(request, origin, response=live.response, error_kind=None, live=live)
        return live.response

    def _live_with_error_log(
        self, request: ChatRequest, origin: CallOrigin, timeout_s: float | None
    ) -> LiveResult:
        """A live call; its failures are logged here, and an overflow is cached for replay."""
        try:
            return self._live_call(request, origin, timeout_s)
        except ContextOverflow as overflow:
            self._cache.put(request, overflow_response(str(overflow)))
            self._log_call(request, origin, response=None, error_kind="context_overflow")
            raise
        except ProviderError as error:
            self._log_call(
                request,
                origin,
                response=None,
                error_kind="provider_error",
                n_retries=error.n_retries,
            )
            raise

    def _raise_if_over_budget(
        self,
        cached: ChatResponse,
        timeout_s: float | None,
        request: ChatRequest,
        origin: CallOrigin,
    ) -> None:
        """Replay a timeout when the stored entry could not have fitted this call's budget.

        A tombstone counts if it ran at least as long as `timeout_s`; a stored answer counts
        if it took longer, since live the call would have been abandoned at `timeout_s`.
        """
        if timeout_s is None:
            return
        is_tombstone = cached.finish_reason == TIMEOUT_FINISH_REASON
        if cached.latency_s < timeout_s or (not is_tombstone and cached.latency_s == timeout_s):
            return
        self._log_call(request, origin, response=None, error_kind="timeout")
        # a tombstone from a bigger budget still only cost this call's own budget, as live would
        raise RequestTimedOut(
            f"cached entry took {cached.latency_s:g} s of {timeout_s:g} s", timeout_s
        )

    def _live_call(
        self,
        request: ChatRequest,
        origin: CallOrigin,
        timeout_s: float | None,
    ) -> LiveResult:
        if timeout_s is None:
            return self._call_with_retries(request, origin)
        future = start_daemon_call(lambda: self._call_with_retries(request, origin))
        done, _ = wait([future], timeout=timeout_s)
        if done:
            return future.result()  # re-raises the call's own ContextOverflow / ProviderError
        self._abandon(future, request, origin, timeout_s)
        raise RequestTimedOut(f"no reply within {timeout_s:g} s; call abandoned", timeout_s)

    def _abandon(
        self,
        future: Future[LiveResult],
        request: ChatRequest,
        origin: CallOrigin,
        timeout_s: float,
    ) -> None:
        """Leave the call running; cache a tombstone so a replay times out identically."""
        self._cache.put(request, tombstone_response(timeout_s))
        self._log_call(request, origin, response=None, error_kind="timeout")

        def on_finished(finished: Future[LiveResult]) -> None:
            self._handle_late_result(finished, request, origin)

        future.add_done_callback(on_finished)

    def _handle_late_result(
        self,
        future: Future[LiveResult],
        request: ChatRequest,
        origin: CallOrigin,
    ) -> None:
        """An abandoned call finished: log and charge its answer, but do not cache it."""
        error = future.exception()
        if error is not None:
            logger.warning("Abandoned %s call ended in an error: %s", request.purpose, error)
            return
        live = future.result()
        self._log_call(
            request, origin, response=live.response, error_kind="late_after_timeout", live=live
        )
        if self.on_late_response is not None:
            self.on_late_response(live.response)

    def _call_with_retries(self, request: ChatRequest, origin: CallOrigin) -> LiveResult:
        return call_with_retries(
            lambda: self._call_once(request),
            purpose=request.purpose,
            api_key=self._api_key,
            max_retries=self._max_retries,
            backoff_base_seconds=self._backoff_base_seconds,
            on_discarded=lambda response: self._log_call(
                request, origin, response=response, error_kind="provider_error"
            ),
        )

    def _call_once(self, request: ChatRequest) -> ChatResponse:
        kwargs = build_request_kwargs(request)
        started = time.monotonic()
        completion = self._sdk_client.chat.completions.create(**kwargs)
        return response_from_completion(completion, time.monotonic() - started)

    def _log_call(
        self,
        request: ChatRequest,
        origin: CallOrigin,
        *,
        response: ChatResponse | None,
        error_kind: CallErrorKind | None,
        live: LiveResult | None = None,
        n_retries: int = 0,
    ) -> None:
        record = CallRecord(
            run_id=origin.run_id,
            question_id=origin.question_id,
            strategy=origin.strategy,
            purpose=request.purpose,
            cache_key=cache_key(request),
            pin_hash=request.pin.pin_hash(),
            prompt_sha256=_prompt_sha256(request),
            response=response,
            error_kind=error_kind,
            n_retries=live.n_retries if live is not None else n_retries,
        )
        line = record.model_dump_json() + "\n"
        with self._log_lock, self._calls_log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
