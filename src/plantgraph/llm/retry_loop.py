"""The retry loop around one chat completion: what is retried, what the call's time covers.

Split out of `client.py`. Only transport failures (429, 5xx, a dropped connection) and a
reply that says `finish_reason: "error"` with no text are retried. The last one is a provider
failure that arrives inside an HTTP 200, so the SDK does not raise on it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import openai
from pydantic import SecretStr

from plantgraph.llm.models import ChatResponse, ContextOverflow, ProviderError
from plantgraph.llm.status_errors import classify_status_error, redact

logger = logging.getLogger(__name__)

#: `finish_reason` an OpenAI-compatible gateway sets when the provider failed mid-request.
ERROR_FINISH_REASON = "error"


@dataclass(frozen=True)
class LiveResult:
    """A live answer and how many extra attempts it took to get it."""

    response: ChatResponse
    n_retries: int


def is_error_reply(response: ChatResponse) -> bool:
    """True for a 200 reply that carries a provider failure instead of an answer."""
    return response.finish_reason == ERROR_FINISH_REASON and not response.text


def call_with_retries(
    call_once: Callable[[], ChatResponse],
    *,
    purpose: str,
    api_key: SecretStr | None,
    max_retries: int,
    backoff_base_seconds: float,
) -> LiveResult:
    """Call until it answers; the result's `latency_s` spans every attempt and back-off.

    Raises:
        ContextOverflow: the prompt does not fit; never retried.
        ProviderError: a fatal error, or retries ran out.
    """
    started = time.monotonic()
    attempt = 0
    while True:
        try:
            response = call_once()
            if not is_error_reply(response):
                elapsed = time.monotonic() - started
                return LiveResult(response.model_copy(update={"latency_s": elapsed}), attempt)
            message = "expected a reply with text, found finish_reason 'error' and no text"
            if attempt >= max_retries:
                raise ProviderError(message, n_retries=attempt)
        except openai.APIStatusError as exc:
            outcome, message = classify_status_error(exc, api_key)
            if outcome == "overflow":
                raise ContextOverflow(message) from exc
            if outcome == "fatal" or attempt >= max_retries:
                raise ProviderError(message, n_retries=attempt) from exc
        except openai.APIConnectionError as exc:
            if attempt >= max_retries:
                raise ProviderError(redact(str(exc), api_key), n_retries=attempt) from exc
        attempt += 1
        _wait_before_retry(purpose, attempt, max_retries, backoff_base_seconds)


def _wait_before_retry(purpose: str, attempt: int, max_retries: int, base_seconds: float) -> None:
    backoff = base_seconds * (2 ** (attempt - 1))
    logger.warning(
        "Retrying %s call after a transport error (attempt %d/%d, waiting %.2fs)",
        purpose,
        attempt,
        max_retries,
        backoff,
    )
    if backoff > 0:
        time.sleep(backoff)
