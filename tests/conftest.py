"""Shared pytest configuration: the opt-in flag for real, paid LLM calls.

Design `qa-system.md` §16. Without `--live-llm`, every test marked
`live_llm` is skipped with a message saying it is paid — never merely
because `OPENROUTER_API_KEY` is set, since
`.env` is loaded automatically and a key being present must never be enough
to spend money on its own (§6, the paid-call guard).
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-llm",
        action="store_true",
        default=False,
        help="Run tests marked live_llm: real, paid calls to OpenRouter. Off by default.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--live-llm"):
        return
    skip_live = pytest.mark.skip(reason="needs --live-llm: makes a real, paid OpenRouter call")
    for item in items:
        if "live_llm" in item.keywords:
            item.add_marker(skip_live)
