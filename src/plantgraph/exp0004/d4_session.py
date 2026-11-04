"""Open a D4 decider with the paid-call guard of the QA harness.

Reuses `qa/harness/clients.py` (cache-only unless `--allow-paid-calls`; the API key is read only
for a paid run) and `qa/harness/spend_cap.py` (the hard cap). D4 has its own cache file, so the
EXP-0007 caches stay untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx2

from plantgraph.exp0004.d4_decider import ChatPairDecider
from plantgraph.llm.models import ModelPin
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.spend_cap import SpendGuard

DEFAULT_PIN_PATH = Path("data/runs/exp0007/inputs/pin_cypher_luna_low.json")  # V2T-A Cypher tier
DEFAULT_CACHE_PATH = Path("data/llm-cache/exp0004.sqlite")


@dataclass(frozen=True)
class LlmOptions:
    """How a D4 command talks to the model. `http_client` is for tests (a fake transport)."""

    allow_paid_calls: bool = False
    max_spend_usd: float | None = None
    pin_path: Path = DEFAULT_PIN_PATH
    cache_path: Path = DEFAULT_CACHE_PATH
    http_client: httpx2.Client | None = None


def check_paid_options(options: LlmOptions) -> None:
    """A paid run needs a positive cap.

    Raises:
        ValueError: `allow_paid_calls` without a cap above zero.
    """
    if options.allow_paid_calls and not (options.max_spend_usd and options.max_spend_usd > 0):
        raise ValueError(
            "expected --max-spend-usd above 0 together with --allow-paid-calls, "
            f"got {options.max_spend_usd}"
        )


@contextmanager
def open_decider(
    options: LlmOptions, calls_log_path: Path, run_id: str
) -> Iterator[tuple[ChatPairDecider, ModelPin]]:
    """Yield a D4 decider and its pin; the cache is closed on exit.

    The spend cap applies to this invocation: money spent by earlier invocations is in the cache
    and is not counted again, since cache hits cost nothing.
    """
    check_paid_options(options)
    pin = ModelPin.model_validate_json(options.pin_path.read_text(encoding="utf-8"))
    client, cache = build_chat_client(
        pin=pin,
        allow_paid_calls=options.allow_paid_calls,
        cache_path=options.cache_path,
        calls_log_path=calls_log_path,
        http_client=options.http_client,
    )
    cap = options.max_spend_usd if options.allow_paid_calls else None
    guard = SpendGuard(cap)
    client.on_late_response = guard.charge_late
    try:
        yield ChatPairDecider(client, pin, guard, run_id), pin
    finally:
        cache.close()
