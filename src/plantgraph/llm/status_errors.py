"""Reading provider errors: which are worth a retry, which mean "prompt too long".

Split out of `client.py`. A provider answers a bad call with an HTTP status code
(429 = rate limited, 5xx = server trouble, other 4xx = our request was wrong); the
client reacts differently to each.
"""

from __future__ import annotations

from typing import Literal

import openai
from pydantic import SecretStr

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

StatusErrorOutcome = Literal["overflow", "retry", "fatal"]


def _is_retryable_status(status_code: int) -> bool:
    """429 (rate limit) and any 5xx are transport-only failures worth a retry.

    Any other 4xx is a content or configuration problem — retrying it would
    just repeat the same mistake, so the client raises immediately
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


def redact(text: str, secret: SecretStr | None) -> str:
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


def classify_status_error(
    exc: openai.APIStatusError, secret: SecretStr | None
) -> tuple[StatusErrorOutcome, str]:
    """What the client should do about one provider status error, and its redacted message."""
    message = redact(str(exc), secret)
    if _looks_like_context_overflow(exc.code, message):
        return "overflow", message
    if _is_retryable_status(exc.status_code):
        return "retry", message
    return "fatal", message
