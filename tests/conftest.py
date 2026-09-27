"""Shared pytest configuration: the opt-in flag for paid LLM calls, and the live-Neo4j skip check.

Design `qa-system.md` §16. Without `--live-llm`, every test marked
`live_llm` is skipped with a message saying it is paid — never merely
because `OPENROUTER_API_KEY` is set, since
`.env` is loaded automatically and a key being present must never be enough
to spend money on its own (§6, the paid-call guard).

`neo4j_skip_reason` gives every module with live-database tests
(`test_neo4j_integration.py`, `test_ingest_integration.py`) one shared,
fast check: skip because credentials are absent, or skip because the
database does not answer within a few seconds — never hang the whole suite
waiting on a `neo4j` driver's own, much longer, default timeout.
"""

from __future__ import annotations

from functools import cache

import pytest

from plantgraph.store.neo4j_probe import probe_connectivity
from plantgraph.store.neo4j_settings import from_env, missing_required_vars


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


@cache
def neo4j_skip_reason() -> str | None:
    """Why a live-Neo4j test module should be skipped, or `None` if it may run.

    Two checks, cheapest first: missing `NEO4J_URI`/`NEO4J_USERNAME`/
    `NEO4J_PASSWORD` (instant, no network) before a reachability probe
    (bounded by `neo4j_probe.DEFAULT_CONNECTION_TIMEOUT_S`, so a stopped
    database is reported in a few seconds rather than the driver's own 30s
    default). `@cache` because both live-Neo4j test modules call this at
    collection time — one process, one database to ask, so one probe for
    the whole run rather than one per module.
    """
    missing = missing_required_vars()
    if missing:
        return f"Neo4j settings missing: {', '.join(missing)} (set in the shell or in .env)"

    settings = from_env()
    if settings is None:
        raise RuntimeError(
            "from_env() returned None right after missing_required_vars() found none missing"
        )

    probe = probe_connectivity(settings)
    if not probe.reachable:
        return f"Neo4j not reachable at {settings.uri}: {probe.detail}"
    return None
