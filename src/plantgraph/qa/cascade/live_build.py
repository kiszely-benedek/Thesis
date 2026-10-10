"""Build a `LiveCascade` from a policy and the stored runs that fix each tier's settings.

A tier's pin, strategy parameters and primer come from a *tier source run* (its frozen
`run_config.json`), so the live tier answers exactly as the evaluated one did. A Cypher tier
needs the database to hold this corpus; when it does not, the tier is left out and the
cascade runs as a derived "not the evaluated policy" (`<policy>-no-<tier>`), never crashes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx2
from neo4j.exceptions import DriverError, Neo4jError

from plantgraph.llm.cache import SqliteCache
from plantgraph.qa.cascade.evaluate import DEFAULT_CUTOFF_S
from plantgraph.qa.cascade.live import (
    LiveCascade,
    LivePolicyRefused,
    LiveTier,
    check_pin,
    refuse_label_routing,
)
from plantgraph.qa.cascade.models import CascadePolicy, TierSpec
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.harness.attempt import active_remaining_s, sender_for_run
from plantgraph.qa.harness.attempt_models import AttemptSettings
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.cypher_setup import (
    CypherSourceFactory,
    check_store_profile,
    open_checked_neo4j_view,
)
from plantgraph.qa.harness.registry import CypherDeps, LlmDeps, build_strategy
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.models import RunConfig
from plantgraph.qa.neo4j_view import StoreMismatch
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME
from plantgraph.store.neo4j_plan import LoadPlan

#: The run id live calls are logged under in `calls.jsonl`.
LIVE_RUN_ID = "live-ask"
#: What "the database does not hold this corpus" can look like when we try to open it.
_STORE_UNAVAILABLE = (StoreMismatch, ValueError, DriverError, Neo4jError)


@dataclass(frozen=True)
class TierFromRun:
    """A tier's answer settings and strategy parameters, read from its source run."""

    settings: AttemptSettings
    params: dict[str, Any]


class OpenedCascade:
    """A `LiveCascade` plus the resources behind it (caches, database); `close` frees them."""

    def __init__(
        self, cascade: LiveCascade, caches: list[SqliteCache], cypher: CypherSource | None
    ) -> None:
        self.cascade = cascade
        self._caches = caches
        self._cypher = cypher

    def close(self) -> None:
        """Close every cache and the database connection."""
        self.release(self._caches, self._cypher)

    @staticmethod
    def release(caches: list[SqliteCache], cypher: CypherSource | None) -> None:
        """Close the given resources (also used when opening fails half way)."""
        for cache in caches:
            cache.close()
        if cypher is not None:
            cypher.close()

    def __enter__(self) -> OpenedCascade:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def load_tier_from_run(spec: TierSpec, run_dir: Path) -> TierFromRun:
    """Read the tier's settings from `run_dir/run_config.json` and check its pin.

    Raises:
        LivePolicyRefused: no config, the run lacks the tier's strategy, or the pin differs.
    """
    config_path = RunDir(run_dir).config_path
    if not config_path.exists():
        raise LivePolicyRefused(
            f"expected run_config.json in {run_dir} for {spec.name!r}, found none"
        )
    config = RunConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    if spec.strategy not in config.strategies:
        raise LivePolicyRefused(
            f"expected run {config.run_id!r} to hold strategy {spec.strategy!r} "
            f"(tier {spec.name!r}), found {sorted(config.strategies)}"
        )
    check_pin(spec, config.answer_pin)
    settings = AttemptSettings(
        LIVE_RUN_ID, config.answer_pin, config.context_wall, config.primer, None
    )
    return TierFromRun(settings, dict(config.strategies[spec.strategy]))


def open_cypher_source(
    plan: LoadPlan | None, spec: TierSpec, factory: CypherSourceFactory
) -> tuple[CypherSource | None, str | None]:
    """The checked database for a Cypher tier, or `None` and the reason it is unavailable."""
    if plan is None:
        return None, f"no load plan for the corpus, so tier {spec.name!r} cannot query the store"
    try:
        check_store_profile(plan, PROFILE_OF_NAME[spec.strategy])
        return factory(plan), None
    except _STORE_UNAVAILABLE as error:
        return None, f"tier {spec.name!r} unavailable, the store does not hold the corpus: {error}"


@dataclass
class _Wiring:
    """Where the tier clients read and write, and the caches they opened (for `close`)."""

    cache_path: Path
    calls_log_path: Path
    allow_paid_calls: bool
    http_client: httpx2.Client | None
    caches: list[SqliteCache] = field(default_factory=list)


def open_live_cascade(
    *,
    corpus_id: str,
    policy: CascadePolicy,
    view: GraphView,
    load_plan: LoadPlan | None,
    tier_run_dirs: Mapping[str, Path],
    cache_path: Path,
    calls_log_path: Path,
    allow_paid_calls: bool,
    cutoff_s: float = DEFAULT_CUTOFF_S,
    guard: SpendGuard | None = None,
    cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view,
    http_client: httpx2.Client | None = None,
) -> OpenedCascade:
    """Open the replay (or, with `allow_paid_calls`, paid) cascade for one corpus.

    Raises:
        LivePolicyRefused: label routing, a tier without a source run, a pin mismatch, or no
            tier left to run.
    """
    refuse_label_routing(policy)
    # every refusal that needs no resource comes first, so a refusal leaves nothing open
    loaded = {
        spec.name: load_tier_from_run(spec, _run_dir(spec, tier_run_dirs)) for spec in policy.tiers
    }
    cypher_specs = [spec for spec in policy.tiers if spec.strategy in PROFILE_OF_NAME]
    cypher, notice = None, None
    if cypher_specs:
        cypher, notice = open_cypher_source(load_plan, cypher_specs[0], cypher_source_factory)
    kept = (
        list(policy.tiers)
        if cypher is not None or not cypher_specs
        else _without(policy, cypher_specs)
    )
    if not kept:
        raise LivePolicyRefused(f"expected a tier to run in {policy.name!r}, found none: {notice}")
    run_policy = policy
    if len(kept) < len(policy.tiers):
        dropped = "-".join(spec.name for spec in cypher_specs)
        name = f"{policy.name}-no-{dropped}"
        run_policy = policy.model_copy(update={"name": name, "tiers": tuple(kept)})
    wiring = _Wiring(cache_path, calls_log_path, allow_paid_calls, http_client)
    try:
        tiers = [_live_tier(spec, loaded[spec.name], view, cypher, wiring) for spec in kept]
        cascade = LiveCascade(
            corpus_id, run_policy, tiers, cutoff_s=cutoff_s, guard=guard, notice=notice
        )
    except Exception:
        OpenedCascade.release(wiring.caches, cypher)
        raise
    return OpenedCascade(cascade, wiring.caches, cypher)


def _run_dir(spec: TierSpec, tier_run_dirs: Mapping[str, Path]) -> Path:
    run_dir = tier_run_dirs.get(spec.name)
    if run_dir is None:
        raise LivePolicyRefused(
            f"expected a source run for tier {spec.name!r}, found only {sorted(tier_run_dirs)}"
        )
    return run_dir


def _without(policy: CascadePolicy, dropped: list[TierSpec]) -> list[TierSpec]:
    return [spec for spec in policy.tiers if spec not in dropped]


def _live_tier(
    spec: TierSpec,
    loaded: TierFromRun,
    view: GraphView,
    cypher: CypherSource | None,
    wiring: _Wiring,
) -> LiveTier:
    settings = loaded.settings
    client, cache = build_chat_client(
        pin=settings.answer_pin,
        allow_paid_calls=wiring.allow_paid_calls,
        cache_path=wiring.cache_path,
        calls_log_path=wiring.calls_log_path,
        http_client=wiring.http_client,
    )
    wiring.caches.append(cache)
    send = sender_for_run(client, settings.run_id)(spec.strategy)
    cypher_deps = CypherDeps(cypher, settings.answer_pin, send, settings.primer) if cypher else None
    llm_deps = LlmDeps(settings.answer_pin, send, settings.primer, active_remaining_s)
    strategy = build_strategy(spec.strategy, loaded.params, view, cypher_deps, llm_deps)
    return LiveTier(spec, strategy, settings, client)
