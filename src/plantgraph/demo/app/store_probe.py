"""Which plant does the graph database hold, and what does that mean for the demo's first step?

The demo's first step (a Cypher query) can only read the database if it holds exactly the corpus
being asked about. Neo4j holds one plant at a time, so with two corpora configured one of them
usually runs with the agent step only. This module names the reason, so the page can say it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from neo4j import READ_ACCESS, GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError
from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_probe import DEFAULT_CONNECTION_TIMEOUT_S
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env

StoreKind = Literal[
    "ready", "holds_other", "empty", "wrong_profile", "mismatch", "unreachable", "not_needed"
]

#: Returns the corpus ids the database holds; raises when it cannot be read.
HeldCorporaProbe = Callable[[], tuple[str, ...]]

# What a failed read can raise: no settings (ValueError), driver or server error, network.
_PROBE_FAILURES = (ValueError, DriverError, Neo4jError, OSError)


class StoreState(BaseModel):
    """Why the database tier can or cannot answer for one corpus."""

    model_config = ConfigDict(frozen=True)

    kind: StoreKind
    #: The corpus ids the database holds (filled for `holds_other` and `mismatch`).
    held: tuple[str, ...] = ()


def held_corpus_ids(settings: Neo4jSettings) -> tuple[str, ...]:
    """Read the corpus id of every `DrawingSet` (the node standing for a whole corpus), sorted."""
    driver = GraphDatabase.driver(
        settings.uri,
        auth=(settings.username, settings.password.get_secret_value()),
        connection_timeout=DEFAULT_CONNECTION_TIMEOUT_S,
    )
    try:
        with driver.session(database=settings.database, default_access_mode=READ_ACCESS) as session:
            rows = session.run("MATCH (d:DrawingSet) RETURN d.corpus_id AS corpus_id")
            return tuple(sorted(str(row["corpus_id"]) for row in rows))
    finally:
        driver.close()


def held_corpus_ids_from_env() -> tuple[str, ...]:
    """`held_corpus_ids` with the `NEO4J_*` settings of the environment.

    Raises:
        ValueError: the settings are absent.
    """
    settings = from_env()
    if settings is None:
        raise ValueError("expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD, found them unset")
    return held_corpus_ids(settings)


def store_state(
    policy: CascadePolicy,
    plan: LoadPlan,
    corpus_id: str,
    tier1_opened: bool,
    probe: HeldCorporaProbe,
) -> StoreState:
    """Decide the store's state from what the cascade builder did and, if needed, one read.

    The checks run cheapest first; `probe` is called only when the database tier did not open.
    """
    profiles = [PROFILE_OF_NAME[t.strategy] for t in policy.tiers if t.strategy in PROFILE_OF_NAME]
    if not profiles:
        return StoreState(kind="not_needed")
    if tier1_opened:
        return StoreState(kind="ready")
    if plan.profile != profiles[0]:
        return StoreState(kind="wrong_profile")
    try:
        held = probe()
    except _PROBE_FAILURES:
        return StoreState(kind="unreachable")
    return _from_held(held, corpus_id)


def _from_held(held: tuple[str, ...], corpus_id: str) -> StoreState:
    if not held:
        return StoreState(kind="empty")
    # it holds this corpus yet the tier did not open: the stored counts differ from the plan's
    if corpus_id in held:
        return StoreState(kind="mismatch", held=held)
    return StoreState(kind="holds_other", held=held)
