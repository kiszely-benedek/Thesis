"""One live cascade per corpus, opened once; its model cache is emptied before every ask.

The frozen paid model client always looks a request up in its SQLite cache before it sends it.
The demo cannot switch that off, but it owns the cache file: a temporary SQLite file per corpus.
Before each ask the demo empties that file through its own connection, so every model call of
the ask is a real one while the cascade (and its database connection) stays open, as in the
evaluated system.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx2
import openai

from plantgraph.demo.app.store_probe import (
    HeldCorporaProbe,
    StoreState,
    held_corpus_ids_from_env,
    store_state,
)
from plantgraph.demo.app.trace_recorder import RecordingTransport, TraceWindow
from plantgraph.llm import openrouter_settings
from plantgraph.qa.cascade.live_build import OpenedCascade, open_live_cascade
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.strategies.base import AskedQuestion
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME
from plantgraph.store.neo4j_plan import LoadPlan

_LOG = logging.getLogger(__name__)

#: The frozen cache's table, created here too in case the demo empties the file before it exists.
_CREATE_RESPONSES = (
    "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, response_json TEXT NOT NULL)"
)

#: Error code of a demo that cannot reach any model (the label table has its text).
NO_API_KEY = "no_api_key"


class NoApiKey(RuntimeError):
    """The server has no model API key (and no test transport), so it cannot answer."""


class Asker(Protocol):
    """Anything that answers one question through a cascade."""

    def ask(self, asked: AskedQuestion) -> LiveAnswer | NeedsPaidCall:
        """Answer the question, or say which paid call is missing."""
        ...


@dataclass(frozen=True)
class AskHandle:
    """What one ask needs: the open cascade, the cache-clearing seconds, and the trace window."""

    cascade: Asker
    #: Seconds spent emptying the model cache before the ask (not part of the answer time).
    clear_s: float
    #: Marks where this ask's recorded traffic and call-log lines begin.
    window: TraceWindow


class CascadeSource(Protocol):
    """What the app needs from a corpus's cascade; tests may pass a fake."""

    #: Tiers that can answer (tier 1 is missing when the store does not hold the corpus).
    tiers: tuple[str, ...]
    #: False when the policy's database tier had to be left out.
    tier1_store: bool
    #: Why the database tier can or cannot answer (the page explains it).
    store: StoreState

    def begin_ask(self) -> AskHandle:
        """The open cascade with its model cache emptied, and the marks that bound the ask."""
        ...

    def close(self) -> None:
        """Close the cascade and delete its cache file."""
        ...

    def reopen(self) -> CascadeSource:
        """Close this cascade and open a fresh one from the same settings.

        Needed after the database's plant changed: a Cypher tier opened earlier still points at
        the old contents, and the tier list depends on what the database holds.
        """
        ...


@dataclass(frozen=True)
class LiveSettings:
    """Everything needed to open a corpus's cascade."""

    corpus_id: str
    policy: CascadePolicy
    view: GraphView
    load_plan: LoadPlan
    tier_run_dirs: dict[str, Path]
    calls_log_path: Path
    cutoff_s: float
    #: The session's spend guard, so every live call is counted against the cap.
    guard: SpendGuard
    cypher_source_factory: CypherSourceFactory
    #: Carries the model requests; tests pass a fake one, production leaves it `None`.
    transport: httpx2.BaseTransport | None = None
    #: Reads which corpora the database holds; tests pass a fake instead of reaching Neo4j.
    held_corpora_probe: HeldCorporaProbe = held_corpus_ids_from_env


class _StoreProbe:
    """Wraps the database factory to learn whether the store really opened for the corpus."""

    def __init__(self, factory: CypherSourceFactory) -> None:
        self._factory = factory
        self.opened = False

    def __call__(self, plan: LoadPlan) -> CypherSource:
        source = self._factory(plan)
        self.opened = True
        return source


class LiveCascadeFactory:
    """Opens a corpus's live cascade once and keeps it for the session."""

    def __init__(self, settings: LiveSettings) -> None:
        """Open the cascade; its tiers are what the corpus can answer with.

        Raises:
            NoApiKey: no model key and no injected transport.
        """
        _require_api_key(settings.transport)
        self._settings = settings
        # one recorder per opened cascade; a reopen builds a new one with the new cascade
        self._recorder = RecordingTransport(settings.transport or httpx2.HTTPTransport())
        self._sdk_client = _sdk_client(self._recorder)
        probe = _StoreProbe(settings.cypher_source_factory)
        self._cache_dir = Path(tempfile.mkdtemp(prefix="plantgraph-demo-"))
        self.cache_file = self._cache_dir / f"{settings.corpus_id}.sqlite"
        started = time.perf_counter()
        try:
            self._opened = _open(settings, probe, self.cache_file, self._sdk_client)
        except Exception:
            self._sdk_client.close()
            shutil.rmtree(self._cache_dir)
            raise
        has_database_tier = any(t.strategy in PROFILE_OF_NAME for t in settings.policy.tiers)
        self.tier1_store = probe.opened or not has_database_tier
        self.tiers = tuple(
            t.name
            for t in settings.policy.tiers
            if self.tier1_store or t.strategy not in PROFILE_OF_NAME
        )
        self.store = store_state(
            settings.policy,
            settings.load_plan,
            settings.corpus_id,
            probe.opened,
            settings.held_corpora_probe,
        )
        _LOG.info(
            "opened the %s cascade once, in %.2f s",
            settings.corpus_id,
            time.perf_counter() - started,
        )

    def begin_ask(self) -> AskHandle:
        """Empty the model cache (so no call can be a stored one) and mark where the ask starts."""
        started = time.perf_counter()
        _empty_cache(self.cache_file)
        clear_s = round(time.perf_counter() - started, 4)
        window = TraceWindow.open(self._recorder, self._settings.calls_log_path)
        return AskHandle(self._opened.cascade, clear_s, window)

    def close(self) -> None:
        """Close the cascade's caches and database connection, then delete the cache file.

        Closing twice is harmless.
        """
        if not self._cache_dir.exists():
            return
        self._opened.close()
        self._sdk_client.close()
        shutil.rmtree(self._cache_dir)

    def reopen(self) -> LiveCascadeFactory:
        """Close this cascade, then open a new one (the old one holds the database connection)."""
        self.close()
        return LiveCascadeFactory(self._settings)


def _sdk_client(recorder: RecordingTransport) -> httpx2.Client:
    """The SDK's own default client (so its timeouts and limits) sending through `recorder`."""
    return openai.DefaultHttpxClient(transport=recorder)


def _open(
    settings: LiveSettings, factory: CypherSourceFactory, cache_file: Path, client: httpx2.Client
) -> OpenedCascade:
    return open_live_cascade(
        corpus_id=settings.corpus_id,
        policy=settings.policy,
        view=settings.view,
        load_plan=settings.load_plan,
        tier_run_dirs=settings.tier_run_dirs,
        cache_path=cache_file,
        calls_log_path=settings.calls_log_path,
        allow_paid_calls=True,
        cutoff_s=settings.cutoff_s,
        guard=settings.guard,
        cypher_source_factory=factory,
        http_client=client,
    )


def _empty_cache(cache_file: Path) -> None:
    """Delete every stored response through the demo's own connection (plain public SQLite)."""
    connection = sqlite3.connect(cache_file)
    try:
        connection.execute(_CREATE_RESPONSES)
        connection.execute("DELETE FROM responses")
        connection.commit()
    finally:
        connection.close()


def _require_api_key(transport: httpx2.BaseTransport | None) -> None:
    # an injected transport (tests) never authenticates, so it needs no key
    if transport is None and openrouter_settings.from_env() is None:
        raise NoApiKey("expected OPENROUTER_API_KEY to answer live, found it unset")
