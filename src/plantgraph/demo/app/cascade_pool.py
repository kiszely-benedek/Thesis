"""The cascades of one corpus: replay, paid and tier-2-only, opened when first needed.

Replay and paid cascades differ in their model client, so each is built once and reused. The
paid one exists only when the server was started with paid calls allowed.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx2

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
    """Opens the replay cascade at once (to learn the tiers) and the others on first use."""

    def __init__(self, settings: PoolSettings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._opened: dict[tuple[bool, bool], OpenedCascade] = {}
        probe = _StoreProbe(settings.cypher_source_factory)
        self._opened[(False, False)] = self._open(paid=False, tier2_only=False, probe=probe)
        has_database_tier = any(t.strategy in PROFILE_OF_NAME for t in settings.policy.tiers)
        self.tier1_store = probe.opened or not has_database_tier
        self.tiers = tuple(
            t.name
            for t in settings.policy.tiers
            if self.tier1_store or t.strategy not in PROFILE_OF_NAME
        )

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
                self._opened[key] = self._open(paid=paid, tier2_only=tier2_only)
            return self._opened[key].cascade

    def close(self) -> None:
        """Close every opened cascade (caches and the database connection)."""
        with self._lock:
            for opened in self._opened.values():
                opened.close()
            self._opened.clear()

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
