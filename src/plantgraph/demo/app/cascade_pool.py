"""The cascades of one corpus: replay, paid and tier-2-only.

Replay and paid cascades differ in their model client, so each is built once and reused. The
paid one exists only when the server was started with paid calls allowed, and is opened together
with the replay one so the first paid question does not wait for it. The tier-2-only variants
open on first use.
"""

from __future__ import annotations

import logging
import threading
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


class Asker(Protocol):
    """Anything that answers one question through a cascade."""

    def ask(self, asked: AskedQuestion) -> LiveAnswer | NeedsPaidCall:
        """Answer the question, or say which paid call is missing."""
        ...


class CascadeSource(Protocol):
    """What the app needs from a corpus's cascades; tests may pass a fake."""

    #: Tiers that can answer (tier 1 is missing when the store does not hold the corpus).
    tiers: tuple[str, ...]
    #: False when the policy's database tier had to be left out.
    tier1_store: bool
    #: Why the database tier can or cannot answer (the page explains it).
    store: StoreState
    #: Seconds each cascade took to open, by mode ("replay", "paid", ...).
    open_s: dict[str, float]

    def asker(self, *, paid: bool, tier2_only: bool) -> Asker:
        """The cascade for this mode."""
        ...

    def close(self) -> None:
        """Free the caches and connections."""
        ...


@dataclass(frozen=True)
class PoolSettings:
    """Everything needed to open a corpus's cascades."""

    corpus_id: str
    policy: CascadePolicy
    view: GraphView
    load_plan: LoadPlan
    tier_run_dirs: dict[str, Path]
    cache_path: Path
    calls_log_path: Path
    cutoff_s: float
    #: The session's spend guard, given to the paid cascade so its calls are counted.
    guard: SpendGuard
    allow_paid_calls: bool
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


class CascadePool:
    """Opens the replay cascade (to learn the tiers) and, if allowed, the paid one at once."""

    def __init__(self, settings: PoolSettings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._opened: dict[tuple[bool, bool], OpenedCascade] = {}
        self.open_s: dict[str, float] = {}
        probe = _StoreProbe(settings.cypher_source_factory)
        self._opened[(False, False)] = self._open_timed(paid=False, tier2_only=False, probe=probe)
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
        if settings.allow_paid_calls:
            self._open_paid_now()

    def asker(self, *, paid: bool, tier2_only: bool) -> Asker:
        """The cascade for this mode, opened on first use.

        Raises:
            ValueError: `paid` was asked for but the server does not allow paid calls.
        """
        if paid and not self._settings.allow_paid_calls:
            raise ValueError("expected paid calls to be allowed on the server, found them off")
        with self._lock:
            key = (paid, tier2_only)
            if key not in self._opened:
                self._opened[key] = self._open_timed(paid=paid, tier2_only=tier2_only)
            return self._opened[key].cascade

    def close(self) -> None:
        """Close every opened cascade (caches and the database connection)."""
        with self._lock:
            for opened in self._opened.values():
                opened.close()
            self._opened.clear()

    def _open_paid_now(self) -> None:
        """Open the paid cascade early; a failure is logged and retried by the first paid ask."""
        try:
            self._opened[(True, False)] = self._open_timed(paid=True, tier2_only=False)
        except Exception:  # e.g. no API key: replay still works, the first paid ask raises again
            _LOG.exception("opening the paid cascade of %s failed", self._settings.corpus_id)

    def _open_timed(
        self, *, paid: bool, tier2_only: bool, probe: _StoreProbe | None = None
    ) -> OpenedCascade:
        started = time.monotonic()
        opened = self._open(paid=paid, tier2_only=tier2_only, probe=probe)
        mode = _mode_name(paid, tier2_only)
        self.open_s[mode] = round(time.monotonic() - started, 2)
        _LOG.info(
            "opened the %s cascade of %s in %.2f s",
            mode,
            self._settings.corpus_id,
            self.open_s[mode],
        )
        return opened

    def _open(
        self, *, paid: bool, tier2_only: bool, probe: _StoreProbe | None = None
    ) -> OpenedCascade:
        s = self._settings
        return open_live_cascade(
            corpus_id=s.corpus_id,
            policy=s.policy,
            view=s.view,
            # no load plan makes the builder leave the database tier out
            load_plan=None if tier2_only else s.load_plan,
            tier_run_dirs=s.tier_run_dirs,
            cache_path=s.cache_path,
            calls_log_path=s.calls_log_path,
            allow_paid_calls=paid,
            cutoff_s=s.cutoff_s,
            guard=s.guard if paid else None,
            cypher_source_factory=probe or s.cypher_source_factory,
            http_client=s.http_client,
        )


def _mode_name(paid: bool, tier2_only: bool) -> str:
    return ("paid" if paid else "replay") + ("_tier2_only" if tier2_only else "")
