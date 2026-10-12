"""The store state decision table: one test per kind, with fake probes (no Neo4j)."""

from __future__ import annotations

import pytest
from neo4j.exceptions import ServiceUnavailable

from plantgraph.demo.app.store_probe import HeldCorporaProbe, StoreState, store_state
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.store.neo4j_plan import LoadPlan, StoreProfile

PIN = "0" * 64
ACCEPT = frozenset({AcceptRule.ANSWERED})


def _policy(*strategies: str) -> CascadePolicy:
    tiers = tuple(
        TierSpec(name=f"tier-{i}", strategy=s, pin_sha256=PIN, accept=ACCEPT)
        for i, s in enumerate(strategies)
    )
    return CascadePolicy(name="test", tiers=tiers)


def _plan(profile: StoreProfile) -> LoadPlan:
    # only `profile` is read by the decision, so skip building the statements
    return LoadPlan.model_construct(corpus_id="D1", profile=profile)


def _never_called() -> tuple[str, ...]:
    pytest.fail("the store was read although the decision did not need it")


def _holding(*ids: str) -> HeldCorporaProbe:
    return lambda: tuple(ids)


def _unreachable() -> tuple[str, ...]:
    raise ServiceUnavailable("connection refused")


def _no_settings() -> tuple[str, ...]:
    raise ValueError("expected NEO4J_URI, found it unset")


CYPHER = _policy("cypher_rag_plant", "agent")


def test_ready_when_the_database_tier_opened() -> None:
    state = store_state(CYPHER, _plan("plant"), "D1", True, _never_called)

    assert state == StoreState(kind="ready")


def test_not_needed_when_the_policy_has_no_database_tier() -> None:
    state = store_state(_policy("agent"), _plan("plant"), "D1", False, _never_called)

    assert state.kind == "not_needed"


def test_wrong_profile_when_the_ingest_file_was_loaded_with_the_other_layout() -> None:
    state = store_state(CYPHER, _plan("occurrence"), "D1", False, _never_called)

    assert state.kind == "wrong_profile"


def test_empty_when_the_database_holds_no_corpus() -> None:
    state = store_state(CYPHER, _plan("plant"), "D1", False, _holding())

    assert state == StoreState(kind="empty")


def test_holds_other_names_the_corpus_the_database_holds() -> None:
    state = store_state(CYPHER, _plan("plant"), "D1", False, _holding("D1000"))

    assert state == StoreState(kind="holds_other", held=("D1000",))


def test_mismatch_when_the_database_holds_this_corpus_but_the_tier_did_not_open() -> None:
    state = store_state(CYPHER, _plan("plant"), "D1", False, _holding("D1"))

    assert state == StoreState(kind="mismatch", held=("D1",))


@pytest.mark.parametrize("probe", [_unreachable, _no_settings])
def test_unreachable_on_a_driver_error_or_missing_settings(probe: HeldCorporaProbe) -> None:
    state = store_state(CYPHER, _plan("plant"), "D1", False, probe)

    assert state.kind == "unreachable"
