"""The plant switch (DP-T13): selecting a plant loads it; an ask never does. No Neo4j, no paid call.

The loader and the probe are fakes over a list that stands for "what the database holds".
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from plantgraph.demo.app import live_cascades, store_loader
from plantgraph.demo.app.api_models import PlantLoad
from plantgraph.demo.app.server import create_app
from plantgraph.demo.app.state import AppState, build_app_state
from plantgraph.demo.app.store_probe import HeldCorporaProbe
from plantgraph.qa.cascade.live_build import OpenedCascade
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings
from qa_harness_toy import CORPUS_ID
from test_demo_app import Env, _ask, _wait_for_end, env, scripted_transport, toy  # noqa: F401

PLAN = cast(LoadPlan, object())  # the fake loader never reads it
SETTINGS = cast(Neo4jSettings, object())


class FakeDatabase:
    """Stands for Neo4j: the plants it holds, and the calls made on it."""

    def __init__(self, held: tuple[str, ...]) -> None:
        self.held = held
        self.calls: list[str] = []
        self.gate: threading.Event | None = None  # when set, a switch waits for it
        self.fail = False

    def probe(self) -> tuple[str, ...]:
        return self.held

    def switch(self, corpus_id: str, plan: LoadPlan, held: HeldCorporaProbe) -> PlantLoad:
        self.calls.append(f"switch {corpus_id}")
        if self.gate is not None:
            self.gate.wait(10)
        if self.fail:
            raise RuntimeError("load failed")
        wiped = tuple(h for h in self.held if h != corpus_id)
        self.held = (corpus_id,)
        return PlantLoad(corpus_id=corpus_id, wiped=wiped, wipe_s=0.5, load_s=2.5)


Build = Callable[[FakeDatabase], tuple[AppState, TestClient]]


@pytest.fixture
def build(env: Env) -> Iterator[Build]:
    states: list[AppState] = []

    def make(database: FakeDatabase) -> tuple[AppState, TestClient]:
        state = build_app_state(
            env.config,
            http_client=scripted_transport().as_httpx_client(),
            held_corpora_probe=database.probe,
            plant_switcher=database.switch,
        )
        state.load_all()
        states.append(state)
        return state, TestClient(create_app(state))

    yield make
    for state in states:
        state.close()


def _wait_until_loaded(client: TestClient) -> dict[str, Any]:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        body: dict[str, Any] = client.get("/api/plant").json()
        if body["loading"] is None:
            return body
        time.sleep(0.05)
    raise AssertionError("the plant load was still running after 20 s")


def test_switch_plant_wipes_the_other_plants_then_loads_in_that_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        store_loader, "wipe_corpus", lambda settings, cid: calls.append(f"wipe {cid}")
    )

    class _Report:
        total_s = 2.5

    def fake_load(settings: Neo4jSettings, plan: LoadPlan) -> Any:
        calls.append("load")
        return _Report()

    monkeypatch.setattr(store_loader, "load_corpus", fake_load)

    result = store_loader.switch_plant("D100", PLAN, lambda: ("D1000", "D100"), SETTINGS)

    assert calls == ["wipe D1000", "load"]  # D100's own copy is wiped by the loader itself
    assert result.wiped == ("D1000",) and result.load_s == 2.5 and result.wipe_s >= 0.0


def test_the_status_names_the_held_plant_and_the_recorded_last_time(build: Build, env: Env) -> None:
    _, client = build(FakeDatabase((CORPUS_ID,)))

    plant = client.get("/api/status").json()["plant"]

    assert plant["held"] == [CORPUS_ID] and plant["loading"] is None and plant["last"] is None


def test_selecting_the_held_plant_does_nothing(build: Build) -> None:
    database = FakeDatabase((CORPUS_ID,))
    _, client = build(database)

    response = client.post("/api/plant", json={"corpus_id": CORPUS_ID})

    assert response.status_code == 200 and database.calls == []


def test_selecting_another_plant_loads_it_and_reopens_the_cascades(
    build: Build, env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    opens: list[int] = []
    real_open = live_cascades.open_live_cascade

    def counting_open(**kwargs: Any) -> OpenedCascade:
        opens.append(1)
        return real_open(**kwargs)

    database = FakeDatabase(("OTHER",))
    _, client = build(database)
    monkeypatch.setattr(live_cascades, "open_live_cascade", counting_open)

    response = client.post("/api/plant", json={"corpus_id": CORPUS_ID})
    done = _wait_until_loaded(client)

    assert response.status_code == 202 and response.json()["loading"] == CORPUS_ID
    assert done["held"] == [CORPUS_ID] and done["error"] is None
    assert done["last"]["wiped"] == ["OTHER"] and done["last"]["load_s"] == 2.5
    assert len(opens) == 1  # the corpus's cascade was opened again against the new contents


def test_an_ask_on_a_plant_the_database_does_not_hold_is_refused_without_a_model_call(
    build: Build, env: Env
) -> None:
    transport = scripted_transport()
    state = build_app_state(
        env.config,
        http_client=transport.as_httpx_client(),
        held_corpora_probe=lambda: ("OTHER",),
    )
    state.load_all()
    client = TestClient(create_app(state))

    response = _ask(client, env, env.answerable)

    assert response.status_code == 409 and response.json()["detail"]["code"] == "plant_not_loaded"
    assert transport.requests == []
    state.close()


def test_an_ask_during_a_switch_is_busy_and_a_second_switch_too(build: Build, env: Env) -> None:
    database = FakeDatabase(("OTHER",))
    database.gate = threading.Event()
    _, client = build(database)
    client.post("/api/plant", json={"corpus_id": CORPUS_ID})

    ask = _ask(client, env, env.answerable)
    second = client.post("/api/plant", json={"corpus_id": CORPUS_ID})
    database.gate.set()
    _wait_until_loaded(client)

    assert ask.status_code == 409 and ask.json()["detail"]["code"] == "busy"
    assert second.status_code == 409 and second.json()["detail"]["code"] == "busy"


def test_after_the_switch_the_ask_runs(build: Build, env: Env) -> None:
    _, client = build(FakeDatabase(("OTHER",)))
    client.post("/api/plant", json={"corpus_id": CORPUS_ID})
    _wait_until_loaded(client)

    response = _ask(client, env, env.answerable)

    assert response.status_code == 200
    _wait_for_end(client, response.json()["job_id"])  # let the job finish before the teardown


def test_a_failed_switch_is_a_code_and_the_held_plants_are_read_again(build: Build) -> None:
    database = FakeDatabase(("OTHER",))
    database.fail = True
    _, client = build(database)

    client.post("/api/plant", json={"corpus_id": CORPUS_ID})
    done = _wait_until_loaded(client)

    assert done["error"] == "plant_load_failed" and done["held"] == ["OTHER"]


def test_an_unknown_plant_is_a_404(build: Build) -> None:
    _, client = build(FakeDatabase(()))

    response = client.post("/api/plant", json={"corpus_id": "nope"})

    assert response.status_code == 404 and response.json()["detail"]["code"] == "unknown_corpus"
