"""The English label table covers every code the demo can send, and API errors carry codes."""

from __future__ import annotations

import json
from typing import cast, get_args

import pytest
from fastapi.testclient import TestClient

from plantgraph.demo.app.api_models import JobStatus
from plantgraph.demo.app.labels import LABELS_PATH, load_labels
from plantgraph.demo.app.server import _ERROR_OF, ERROR_CODES, create_app
from plantgraph.demo.app.state import AppState
from plantgraph.demo.app.store_probe import StoreKind
from plantgraph.demo.app.topics import TOPIC_ORDER, topic_of
from plantgraph.qa.agent.models import StopReason
from plantgraph.qa.cascade.policy import load_policies
from plantgraph.qa.models import Outcome, QuestionFamily

LABELS = load_labels()
# the policies a demo is configured with (`demo_config.example.json` uses v3; v2 is its predecessor)
DEMO_POLICIES = ("cascade_v2", "cascade_v3")


def _job_states() -> tuple[str, ...]:
    return get_args(JobStatus.model_fields["state"].annotation)


def _assert_has_text(section: dict[str, str], keys: set[str] | frozenset[str]) -> None:
    assert keys <= set(section), f"missing labels: {sorted(keys - set(section))}"
    assert all(section[key] for key in keys), "a label is empty"


def test_the_outcomes_and_stop_reasons_have_text() -> None:
    _assert_has_text(LABELS.outcomes, {o.value for o in Outcome})
    _assert_has_text(LABELS.stop_reasons, set(get_args(StopReason)))


def test_the_store_states_and_job_states_have_text() -> None:
    # `not_needed` shows nothing, so its text is empty on purpose
    kinds = set(get_args(StoreKind))
    assert kinds == set(LABELS.store_states)
    _assert_has_text(LABELS.store_states, kinds - {"not_needed"})
    _assert_has_text(LABELS.job_states, set(_job_states()))


def test_the_tiers_and_strategies_of_the_demo_policies_have_text() -> None:
    policies = load_policies()
    for name in DEMO_POLICIES:
        tiers = policies[name].tiers
        _assert_has_text(LABELS.tiers, {tier.name for tier in tiers})
        _assert_has_text(LABELS.strategies, {tier.strategy for tier in tiers})


def test_every_family_maps_to_a_listed_topic_with_a_heading() -> None:
    assert set(LABELS.family_topics) == {f.value for f in QuestionFamily}
    assert all(topic_of(family) in TOPIC_ORDER for family in QuestionFamily)
    _assert_has_text(LABELS.topics, set(TOPIC_ORDER))


def test_every_error_code_the_api_sends_has_text() -> None:
    _assert_has_text(LABELS.error_codes, ERROR_CODES)
    assert set(LABELS.error_codes) == ERROR_CODES, "a label for a code the API never sends"


def test_the_answer_values_are_english_yes_and_no() -> None:
    assert LABELS.answer_values == {"yes": "Yes", "no": "No"}


def test_the_json_has_only_the_sections_the_model_knows() -> None:
    sections = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    assert set(sections) == set(type(LABELS).model_fields)


# --- errors carry a code ---------------------------------------------------------------------


class _RaisingState:
    """A stand-in `AppState` whose job lookup raises the given error."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def job_status(self, job_id: str) -> None:
        raise self._error


@pytest.mark.parametrize("error_type", list(_ERROR_OF))
def test_a_domain_error_is_a_status_and_a_code_with_the_english_message(
    error_type: type[Exception],
) -> None:
    state = cast(AppState, _RaisingState(error_type("expected X, found Y")))
    response = TestClient(create_app(state)).get("/api/jobs/any")

    status, code = _ERROR_OF[error_type]
    assert response.status_code == status
    assert response.json() == {"detail": {"code": code, "message": "expected X, found Y"}}
