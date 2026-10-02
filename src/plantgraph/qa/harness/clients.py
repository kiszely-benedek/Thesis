"""Build the chat client for a run, enforcing the paid-call guard (`qa-system.md` §6).

Without `--allow-paid-calls` the client is cache-only: the cache is in
`replay` mode, `allow_network` is False, the API key is never read, and the
HTTP layer is a transport that refuses every request. A key in `.env` is
therefore never taken as permission to spend.
"""

from __future__ import annotations

from pathlib import Path

import httpx2
from pydantic import SecretStr

from plantgraph.llm import local_settings, openrouter_settings
from plantgraph.llm.cache import SqliteCache
from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ModelPin

#: A host that can never resolve (RFC 2606), so a replay-only client has no real address.
_REPLAY_ONLY_BASE_URL = "http://replay-only.invalid/v1"


def _refuse_request(request: httpx2.Request) -> httpx2.Response:
    raise RuntimeError(
        f"a replay-only client tried to send {request.method} {request.url}; "
        "without --allow-paid-calls no network request may be made"
    )


def build_chat_client(
    *,
    pin: ModelPin,
    allow_paid_calls: bool,
    cache_path: Path,
    calls_log_path: Path,
    http_client: httpx2.Client | None = None,
) -> tuple[ChatClient, SqliteCache]:
    """Return the client and its cache; the caller closes the cache.

    `http_client` lets tests inject the fake transport; without it, a paid run
    uses the real SDK transport and a free run uses the refusing one.
    """
    if not allow_paid_calls:
        return _replay_only_client(pin, cache_path, calls_log_path, http_client)
    cache = SqliteCache(cache_path, "live")
    return _paid_client(pin, cache, calls_log_path, http_client), cache


def _replay_only_client(
    pin: ModelPin, cache_path: Path, calls_log_path: Path, http_client: httpx2.Client | None
) -> tuple[ChatClient, SqliteCache]:
    cache = SqliteCache(cache_path, "replay")
    refusing = httpx2.Client(transport=httpx2.MockTransport(_refuse_request))
    client = ChatClient(
        backend=pin.backend,
        base_url=_REPLAY_ONLY_BASE_URL,
        api_key=None,
        cache=cache,
        calls_log_path=calls_log_path,
        allow_network=False,
        http_client=http_client or refusing,
    )
    return client, cache


def _paid_client(
    pin: ModelPin, cache: SqliteCache, calls_log_path: Path, http_client: httpx2.Client | None
) -> ChatClient:
    if pin.backend == "local":
        local = local_settings.from_env()
        if local is None:
            raise ValueError("expected LOCAL_LLM_BASE_URL for a local pin, found it unset")
        return ChatClient.for_local(
            local,
            cache=cache,
            calls_log_path=calls_log_path,
            allow_network=True,
            http_client=http_client,
        )
    settings = openrouter_settings.from_env()
    if settings is None:
        if http_client is None:
            raise ValueError("expected OPENROUTER_API_KEY for a paid run, found it unset")
        # an injected transport (the fake) never authenticates, so any key will do
        settings = openrouter_settings.OpenRouterSettings(api_key=SecretStr("injected-transport"))
    return ChatClient.for_openrouter(
        settings,
        cache=cache,
        calls_log_path=calls_log_path,
        allow_network=True,
        http_client=http_client,
    )
