"""A fresh live cascade for every ask: the demo never reads a stored answer.

The frozen paid model client always looks a request up in its SQLite cache before it sends it.
The demo cannot switch that off, but it chooses where the cache lives: `LIVE_CACHE` is an empty
database in memory, private to each model client. Opening a new cascade per ask (and closing it
when the ask ends) means every ask starts with empty caches, so every model call is a real one.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx2

from plantgraph.demo.app.store_probe import (
    HeldCorporaProbe,
    StoreState,
    held_corpus_ids_from_env,
    store_state,
)
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

#: Each model client gets its own empty SQLite database in memory: nothing is read from disk,
#: and the database disappears when the ask's cascade is closed.
LIVE_CACHE = Path(":memory:")

#: Error code of a demo that cannot reach any model (the label table has its text).
NO_API_KEY = "no_api_key"


class NoApiKey(RuntimeError):
    """The server has no model API key (and no test transport), so it cannot answer."""


class Asker(Protocol):
    """Anything that answers one question through a cascade."""

    def ask(self, asked: AskedQuestion) -> LiveAnswer | NeedsPaidCall:
        """Answer the question, or say which paid call is missing."""
        ...


class OpenedForAsk(Protocol):
    """A cascade opened for one ask; `close` frees its caches and database connection."""

    @property
    def cascade(self) -> Asker:
        """The cascade to ask."""
        ...

    def close(self) -> None:
        """Free the caches and the connection."""
        ...


class CascadeSource(Protocol):
    """What the app needs from a corpus's cascades; tests may pass a fake."""

    #: Tiers that can answer (tier 1 is missing when the store does not hold the corpus).
    tiers: tuple[str, ...]
    #: False when the policy's database tier had to be left out.
    tier1_store: bool
    #: Why the database tier can or cannot answer (the page explains it).
    store: StoreState

    def open_for_ask(self) -> tuple[OpenedForAsk, float]:
        """A fresh cascade and the seconds it took to open."""
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
    http_client: httpx2.Client | None = None
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
    """Opens a fresh live cascade per ask; opens one at start only to learn the tiers."""

    def __init__(self, settings: LiveSettings) -> None:
        """Learn the tiers by opening one cascade.

        Raises:
            NoApiKey: no model key and no injected transport.
        """
        _require_api_key(settings.http_client)
        self._settings = settings
        probe = _StoreProbe(settings.cypher_source_factory)
        opened, open_s = self._open(probe)
        opened.close()
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
        _LOG.info("first open of the %s cascade took %.2f s", settings.corpus_id, open_s)

    def open_for_ask(self) -> tuple[OpenedCascade, float]:
        """A fresh cascade with empty caches, and the seconds opening it took."""
        return self._open(self._settings.cypher_source_factory)

    def _open(self, factory: CypherSourceFactory) -> tuple[OpenedCascade, float]:
        s = self._settings
        started = time.monotonic()
        opened = open_live_cascade(
            corpus_id=s.corpus_id,
            policy=s.policy,
            view=s.view,
            load_plan=s.load_plan,
            tier_run_dirs=s.tier_run_dirs,
            cache_path=LIVE_CACHE,
            calls_log_path=s.calls_log_path,
            allow_paid_calls=True,
            cutoff_s=s.cutoff_s,
            guard=s.guard,
            cypher_source_factory=factory,
            http_client=s.http_client,
        )
        return opened, round(time.monotonic() - started, 3)


def _require_api_key(http_client: httpx2.Client | None) -> None:
    # an injected transport (tests) never authenticates, so it needs no key
    if http_client is None and openrouter_settings.from_env() is None:
        raise NoApiKey("expected OPENROUTER_API_KEY to answer live, found it unset")
