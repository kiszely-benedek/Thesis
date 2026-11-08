"""The OpenRouter credit balance, read before every paid stage (review-fixes §5.4).

OpenRouter's `GET /api/v1/credits` answers `{"data": {"total_credits": X, "total_usage": Y}}`; the
balance is `X - Y` dollars. The API key is read from the environment inside `fetch_credits_json`
only and never appears in a message or a log. If the balance cannot be read the stage must stop,
so every failure here raises `BalanceError` with what was expected and what was found.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable

from plantgraph.llm.openrouter_settings import from_env

CREDITS_PATH = "/credits"
_TIMEOUT_S = 20.0

#: Fetches the endpoint's JSON text; replaceable so tests and the smoke never touch the network.
CreditsFetcher = Callable[[], str]


class BalanceError(RuntimeError):
    """The balance could not be read, or does not cover what a stage needs."""


def fetch_credits_json() -> str:
    """GET the credits endpoint with the key from the environment.

    Raises:
        BalanceError: no key, a network or HTTP error (the key is never put in the message).
    """
    settings = from_env()
    if settings is None:
        raise BalanceError("expected OPENROUTER_API_KEY in the environment or .env, found none")
    request = urllib.request.Request(  # noqa: S310 - the base URL is OpenRouter's own, https
        settings.base_url.rstrip("/") + CREDITS_PATH,
        headers={"Authorization": f"Bearer {settings.api_key.get_secret_value()}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as reply:  # noqa: S310
            return str(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise BalanceError(
            f"expected HTTP 200 from the credits endpoint, found {error.code}"
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise BalanceError(
            f"expected the credits endpoint to answer, found {type(error).__name__}"
        ) from None


def balance_usd(fetch: CreditsFetcher = fetch_credits_json) -> float:
    """Dollars left on the account.

    Raises:
        BalanceError: the reply is not the documented shape.
    """
    text = fetch()
    try:
        data = json.loads(text)["data"]
        return float(data["total_credits"]) - float(data["total_usage"])
    except (ValueError, KeyError, TypeError) as error:
        raise BalanceError(
            f"expected data.total_credits and data.total_usage in the reply, found {text[:120]!r}"
        ) from error


def require_balance(needed_usd: float, fetch: CreditsFetcher = fetch_credits_json) -> float:
    """The balance, if it covers `needed_usd`.

    Raises:
        BalanceError: unreadable, or smaller than `needed_usd`.
    """
    balance = balance_usd(fetch)
    if balance < needed_usd:
        raise BalanceError(
            f"expected a balance of at least ${needed_usd:.2f}, found ${balance:.2f}: top up"
        )
    return balance
