"""The demo's need routing, wired into the live cascades (T2): offline, fake model transport.

The toy plant cannot serve a Cypher tier, so most tests use two `context_rag` tiers named `first`
and `second`: which of them ran is visible in the answer's tier reports and in the number of model
requests the fake transport saw. One test uses the real `cypher_rag_plant` tier to cover a missing
store.
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

import json
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest

from plantgraph.demo.app.api_models import AskRequest, DemoAnswer
from plantgraph.demo.app.live_cascades import LiveCascadeFactory
from plantgraph.demo.app.state import AppState, build_app_state
from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.cascade.live_build import OpenedCascade, open_live_cascade
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.need.labels import NeedLabel
from qa_harness_toy import CORPUS_ID, pin
from test_demo_app import Env, env, scripted_transport, toy  # noqa: F401

ISOLATE_UPSTREAM = "To isolate P-3 from all upstream equipment, which valves must be closed?"
PLAIN_QUESTION = "Which sheet is the pump P-3 drawn on?"
POLICY_NAME = "cascade_v4_iso"


@pytest.fixture(autouse=True)
def _close_states() -> Iterator[None]:
    yield
    for state in _OPENED_STATES:  # delete each open cascade's temporary cache file
        state.close()
    _OPENED_STATES.clear()


_OPENED_STATES: list[AppState] = []


def _tier(name: str, strategy: str, *rules: AcceptRule) -> TierSpec:
    return TierSpec(
        name=name, strategy=strategy, pin_sha256=pin().pin_hash(), accept=frozenset(rules)
    )


def _routed_policy(first: TierSpec, second: TierSpec) -> CascadePolicy:
    """Like cascade_v4_iso: isolation-from-upstream questions start at the second tier."""
    return CascadePolicy(
        name=POLICY_NAME,
        tiers=(first, second),
        start_tier_by_label={NeedLabel.UPSTREAM_TO_FIRST_VALVE: 1},
    )


def _two_context_tiers() -> CascadePolicy:
    # the first tier rejects an abstention, so an unrouted question escalates to the second
    first = _tier("first", "context_rag", AcceptRule.ANSWERED, AcceptRule.NOT_ABSTAINED)
    return _routed_policy(first, _tier("second", "context_rag", AcceptRule.ANSWERED))


def _cypher_then_context() -> CascadePolicy:
    first = _tier("cypher-low", "cypher_rag_plant", AcceptRule.ANSWERED, AcceptRule.ROWS)
    return _routed_policy(first, _tier("answer", "context_rag", AcceptRule.ANSWERED))


def _state(env: Env, policy: CascadePolicy, transport: FakeTransport) -> AppState:
    """An app state running `policy`; every tier reads the toy run the `env` fixture wrote."""
    run = env.config.corpora[0].tier_runs["answer"]
    first_run, second_run = run, _primer_copy_of(run)
    corpus = env.config.corpora[0].model_copy(
        update={"tier_runs": {policy.tiers[0].name: first_run, policy.tiers[1].name: second_run}}
    )
    policy_file = run.parent / "routed-policy.json"
    policy_file.write_text(policy.model_dump_json(), encoding="utf-8")
    config = env.config.model_copy(update={"corpora": (corpus,), "policy": str(policy_file)})
    state = build_app_state(
        config,
        transport=httpx2.MockTransport(transport.handler),
        held_corpora_probe=lambda: (CORPUS_ID,),  # no real Neo4j in tests
    )
    state.load_all()
    _OPENED_STATES.append(state)
    return state


def _primer_copy_of(run: Path) -> Path:
    """A copy of the tier run that words its prompts differently (the primer is on).

    Both toy tiers would otherwise send the same request, and the second would read the first's
    stored reply from the shared cache, which real tiers (different strategies) never do.
    """
    copy = run.parent / "tier-run-primer"
    shutil.copytree(run, copy)
    config_file = copy / "run_config.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["primer"] = True
    config_file.write_text(json.dumps(config), encoding="utf-8")
    return copy


def _ask(state: AppState, text: str) -> DemoAnswer:
    job_id = state.start_ask(AskRequest(corpus_id=CORPUS_ID, text=text))
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status = state.job_status(job_id)
        if status.state != "running":
            assert status.result is not None, f"expected an answer, found {status.message}"
            return status.result
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} was still running after 20 s")


def _tiers_run(answer: DemoAnswer) -> tuple[str, ...]:
    return tuple(report.tier for report in answer.live.tiers)


def _factory(state: AppState) -> LiveCascadeFactory:
    source = state.ready_corpus(CORPUS_ID).source
    assert isinstance(source, LiveCascadeFactory)
    return source


def test_a_routed_question_calls_only_the_agent_tier(env: Env) -> None:
    transport = scripted_transport()
    state = _state(env, _two_context_tiers(), transport)

    answer = _ask(state, ISOLATE_UPSTREAM)

    assert len(transport.requests) == 1 and _tiers_run(answer) == ("second",)
    assert answer.need_label == NeedLabel.UPSTREAM_TO_FIRST_VALVE.value
    assert answer.start_tier == "second" and answer.live.evaluated_policy is True


def test_an_unrouted_question_runs_the_first_tier_first(env: Env) -> None:
    transport = scripted_transport()
    state = _state(env, _two_context_tiers(), transport)

    answer = _ask(state, PLAIN_QUESTION)

    assert len(transport.requests) == 2 and _tiers_run(answer) == ("first", "second")
    assert answer.need_label is not None and answer.start_tier == "first"


def test_a_missing_store_derives_the_full_cascade_but_the_routed_one_is_still_evaluated(
    env: Env,
) -> None:
    state = _state(env, _cypher_then_context(), scripted_transport())

    unrouted = _ask(state, PLAIN_QUESTION)
    routed = _ask(state, ISOLATE_UPSTREAM)

    assert unrouted.live.evaluated_policy is False and unrouted.live.notice is not None
    assert unrouted.live.policy == f"{POLICY_NAME}-no-cypher-low"
    # the start-1 policy never needed the store, so it runs exactly as evaluated
    assert routed.live.evaluated_policy is True and routed.live.policy == POLICY_NAME
    assert _tiers_run(routed) == ("answer",) and routed.start_tier == "answer"


def test_the_status_shows_the_evaluated_policy_and_all_its_tiers(env: Env) -> None:
    state = _state(env, _two_context_tiers(), scripted_transport())

    status = state.status()

    assert status.policy == POLICY_NAME and status.policy_tiers == ("first", "second")
    assert status.corpora[0].tiers == ("first", "second") and status.corpora[0].tier1_store


def test_one_cascade_is_opened_per_start_tier_and_a_reopen_opens_them_again(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    opens: list[int] = []

    def counting_open(**kwargs: Any) -> OpenedCascade:
        opens.append(len(kwargs["policy"].tiers))
        return open_live_cascade(**kwargs)

    monkeypatch.setattr("plantgraph.demo.app.live_cascades.open_live_cascade", counting_open)
    state = _state(env, _two_context_tiers(), scripted_transport())
    assert opens == [2, 1]  # start 0 runs both tiers, start 1 only the second

    cache_file = _factory(state).cache_file
    state.reopen_cascades()

    assert opens == [2, 1, 2, 1] and not cache_file.exists()
    assert _factory(state).cache_file.exists()


def test_closing_twice_is_harmless(env: Env) -> None:
    state = _state(env, _two_context_tiers(), scripted_transport())
    cache_dir: Path = _factory(state).cache_file.parent

    state.close()
    state.close()

    assert not cache_dir.exists()
