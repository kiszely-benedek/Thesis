"""`ModelPin`, `ChatRequest`/`ChatResponse` and `canonical_hash` (design `qa-system.md` §4).

No network, no database — these are plain Pydantic models, so every test
below is a pure in-memory check.
"""

from __future__ import annotations

from datetime import datetime

from plantgraph.llm.models import ChatMessage, ChatRequest, ChatResponse, ModelPin, canonical_hash


def _pin(**overrides: object) -> ModelPin:
    defaults: dict[str, object] = {
        "backend": "openrouter",
        "model_id": "openai/gpt-5-mini",
        "route_provider": "openai",
        "temperature": 0.0,
        "seed": 42,
        "max_output_tokens": 512,
        "extra": {},
    }
    defaults.update(overrides)
    return ModelPin.model_validate(defaults)


def test_pin_hash_is_identical_for_two_equal_pins() -> None:
    assert _pin().pin_hash() == _pin().pin_hash()


def test_pin_hash_changes_with_every_field() -> None:
    baseline = _pin().pin_hash()

    assert _pin(backend="local").pin_hash() != baseline
    assert _pin(model_id="openai/gpt-5").pin_hash() != baseline
    assert _pin(route_provider="azure").pin_hash() != baseline
    assert _pin(temperature=0.7).pin_hash() != baseline
    assert _pin(seed=43).pin_hash() != baseline
    assert _pin(max_output_tokens=1024).pin_hash() != baseline
    assert _pin(extra={"reasoning_effort": "high"}).pin_hash() != baseline


def test_model_pin_has_no_field_that_could_hold_a_credential() -> None:
    # ADR-0014 / qa-system.md §6: a credential lives only in a settings object,
    # read once by the client — never in a cached, logged model like this one.
    forbidden_names = {"api_key", "key", "token", "secret", "password", "credential"}
    assert forbidden_names.isdisjoint(ModelPin.model_fields.keys())


def test_chat_request_has_no_field_that_could_hold_a_credential() -> None:
    forbidden_names = {"api_key", "key", "token", "secret", "password", "credential"}
    assert forbidden_names.isdisjoint(ChatRequest.model_fields.keys())


def test_canonical_hash_ignores_dict_key_order() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_canonical_hash_distinguishes_different_payloads() -> None:
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_chat_response_round_trips_through_json() -> None:
    response = ChatResponse(
        text="P-101",
        prompt_tokens=120,
        completion_tokens=8,
        cost_usd=0.0012,
        latency_s=0.83,
        provider_response_id="gen-abc123",
        finish_reason="stop",
        from_cache=False,
        created_at=datetime(2026, 9, 26, 12, 0, 0),
    )

    restored = ChatResponse.model_validate_json(response.model_dump_json())

    assert restored == response


def test_chat_request_holds_pin_and_messages() -> None:
    request = ChatRequest(
        pin=_pin(),
        messages=[ChatMessage(role="user", content="What is P-101?")],
        json_mode=True,
        purpose="answer",
    )

    assert request.pin.model_id == "openai/gpt-5-mini"
    assert request.messages[0].content == "What is P-101?"
