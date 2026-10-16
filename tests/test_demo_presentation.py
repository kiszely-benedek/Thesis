"""Presentation mode on the server: config validation, step resolution and the sequence API.

Uses the toy server of `test_demo_app` (fake model transport, fake store probe, no Neo4j).
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

from collections.abc import Iterator

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from plantgraph.demo.app.config import (
    DemoConfig,
    PresentationSequence,
    PresentationStep,
    load_demo_config,
)
from plantgraph.demo.app.presentation import presentation_view
from plantgraph.demo.app.server import create_app
from plantgraph.demo.app.state import AppState, build_app_state
from qa_harness_toy import CORPUS_ID
from test_demo_app import EXAMPLE_CONFIG, Env, env, scripted_transport, toy  # noqa: F401


def _example(question_id: str | None) -> PresentationStep:
    return PresentationStep(kind="example", question_id=question_id)


def _sequence(
    corpus_id: str, *steps: PresentationStep, title: str = "Talk"
) -> PresentationSequence:
    return PresentationSequence(corpus_id=corpus_id, title=title, steps=steps)


def _with_talks(env: Env, *talks: PresentationSequence) -> DemoConfig:
    return env.config.model_copy(update={"presentation": talks})


@pytest.fixture
def served(env: Env) -> Iterator[tuple[AppState, DemoConfig]]:
    """A loaded toy state whose config holds no talks; tests ask `presentation_view` directly."""
    state = build_app_state(
        env.config,
        transport=httpx2.MockTransport(scripted_transport().handler),
        held_corpora_probe=lambda: (CORPUS_ID,),
    )
    state.load_all()
    yield state, env.config
    state.close()


def _client(state: AppState, config: DemoConfig) -> TestClient:
    state.config = config  # the state reads the talks from its config
    return TestClient(create_app(state))


def test_an_example_step_without_a_question_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="question_id"):
        _example(None)


def test_a_sequence_without_steps_is_rejected() -> None:
    with pytest.raises(ValidationError, match="steps"):
        _sequence(CORPUS_ID)


def test_a_sequence_naming_an_unconfigured_plant_is_rejected(env: Env) -> None:
    talk = _sequence("D9999", PresentationStep(kind="results"))

    with pytest.raises(ValidationError, match="D9999|Talk"):
        DemoConfig(**{**env.config.model_dump(), "presentation": (talk,)})


def test_the_shipped_example_config_has_no_talks_and_the_default_is_empty(env: Env) -> None:
    assert load_demo_config(EXAMPLE_CONFIG).presentation == ()
    assert env.config.presentation == ()


def test_steps_resolve_to_the_examples_own_text(
    env: Env, served: tuple[AppState, DemoConfig]
) -> None:
    state, _ = served
    known = env.answerable
    config = _with_talks(
        env, _sequence(CORPUS_ID, _example(known.question_id), PresentationStep(kind="results"))
    )

    (sequence,) = presentation_view(config, lambda cid: {known.question_id: known.text}).sequences

    first, second = sequence.items
    assert (first.text, first.missing, first.index) == (known.text, None, 0)
    assert (second.kind, second.text, second.missing, second.index) == ("results", None, None, 1)
    assert state.ready_corpus(CORPUS_ID).questions[known.question_id].text == known.text


def test_an_unknown_example_id_is_marked_missing_and_the_text_is_not_invented(env: Env) -> None:
    config = _with_talks(env, _sequence(CORPUS_ID, _example("no-such-id")))

    (sequence,) = presentation_view(config, lambda cid: {}).sequences

    assert (sequence.items[0].missing, sequence.items[0].text) == ("unknown_question", None)


def test_a_plant_that_is_not_loaded_marks_its_examples_not_ready(env: Env) -> None:
    config = _with_talks(env, _sequence(CORPUS_ID, _example("x"), PresentationStep(kind="results")))

    (sequence,) = presentation_view(config, lambda cid: None).sequences

    assert [i.missing for i in sequence.items] == ["corpus_not_ready", None]


def test_the_api_returns_the_sequences_of_the_config(
    env: Env, served: tuple[AppState, DemoConfig]
) -> None:
    state, _ = served
    config = _with_talks(
        env, _sequence(CORPUS_ID, _example(env.answerable.question_id), title="Toy talk")
    )

    body = _client(state, config).get("/api/presentation").json()

    (sequence,) = body["sequences"]
    assert (sequence["corpus_id"], sequence["title"]) == (CORPUS_ID, "Toy talk")
    assert sequence["items"][0] == {
        "index": 0,
        "kind": "example",
        "question_id": env.answerable.question_id,
        "text": env.answerable.text,
        "missing": None,
    }


def test_the_api_is_empty_when_no_talk_is_configured(served: tuple[AppState, DemoConfig]) -> None:
    state, config = served

    assert _client(state, config).get("/api/presentation").json() == {"sequences": []}


def test_a_sequence_is_bound_to_one_plant_so_each_item_names_that_plants_examples(
    env: Env, served: tuple[AppState, DemoConfig]
) -> None:
    state, _ = served
    other = env.unanswerable
    config = _with_talks(
        env, _sequence(CORPUS_ID, _example(other.question_id), _example(env.answerable.question_id))
    )

    (sequence,) = _client(state, config).get("/api/presentation").json()["sequences"]

    assert sequence["corpus_id"] == CORPUS_ID
    assert [i["text"] for i in sequence["items"]] == [other.text, env.answerable.text]
