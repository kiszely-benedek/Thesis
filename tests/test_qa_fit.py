"""The context-wall fit check: pre-call and on-call paths to `DID_NOT_FIT` (`qa-system.md` §7, §12).

Per `qa-system.md` §18 QA-T8's acceptance check: the fit check covers both
paths — a prompt already known to be rejected (pre-call) and a call that
overflows once attempted (on-call) — and a run with no measured wall yet is
handled explicitly, never as an error.
"""

from __future__ import annotations

from datetime import datetime

from plantgraph.llm.models import ContextOverflow, ContextWall
from plantgraph.qa.fit import check_fit, handle_overflow
from plantgraph.qa.models import Outcome


def _wall(*, max_ok_chars: int, min_rejected_chars: int | None) -> ContextWall:
    return ContextWall(
        pin_hash="pin-abc123",
        max_ok_chars=max_ok_chars,
        min_rejected_chars=min_rejected_chars,
        measured_at=datetime(2026, 9, 26, 12, 0, 0),
        probe_corpus_ids=["D10"],
    )


# --- no wall measured yet ------------------------------------------------------------------


def test_no_wall_known_lets_every_prompt_through() -> None:
    decision = check_fit(1_000_000, wall=None)

    assert decision.should_call is True
    assert decision.outcome is None
    assert decision.trace == {"fit_check": "no_wall_known", "overflow_on_call": False}


# --- pre-call path: already known to be rejected --------------------------------------------


def test_prompt_under_the_wall_is_let_through() -> None:
    wall = _wall(max_ok_chars=1000, min_rejected_chars=1500)

    decision = check_fit(500, wall)

    assert decision.should_call is True
    assert decision.outcome is None
    assert decision.trace["fit_check"] == "under_max_ok"
    assert decision.trace["overflow_on_call"] is False


def test_prompt_at_or_over_min_rejected_chars_does_not_call() -> None:
    wall = _wall(max_ok_chars=1000, min_rejected_chars=1500)

    decision = check_fit(1500, wall)

    assert decision.should_call is False
    assert decision.outcome is Outcome.DID_NOT_FIT
    assert decision.trace["fit_check"] == "pre_call_over_min_rejected"
    assert decision.trace["overflow_on_call"] is False
    assert decision.trace["prompt_chars"] == 1500


def test_prompt_over_min_rejected_chars_also_does_not_call() -> None:
    wall = _wall(max_ok_chars=1000, min_rejected_chars=1500)

    decision = check_fit(2000, wall)

    assert decision.should_call is False
    assert decision.outcome is Outcome.DID_NOT_FIT


def test_prompt_in_the_margin_between_max_ok_and_min_rejected_still_calls() -> None:
    # The binary search left this zone unresolved: the pilot has not proven
    # a prompt of exactly this size is rejected, so the call is attempted
    # and only a live ContextOverflow (handle_overflow) can settle it.
    wall = _wall(max_ok_chars=1000, min_rejected_chars=1500)

    decision = check_fit(1200, wall)

    assert decision.should_call is True
    assert decision.outcome is None
    assert decision.trace["fit_check"] == "within_margin"


def test_prompt_over_max_ok_with_no_rejection_measured_yet_still_calls() -> None:
    # The probe found a safe size but has not yet found a rejected one at all
    # (min_rejected_chars is None): there is no known wall to reject against.
    wall = _wall(max_ok_chars=1000, min_rejected_chars=None)

    decision = check_fit(5000, wall)

    assert decision.should_call is True
    assert decision.trace["fit_check"] == "within_margin"


# --- on-call path: the call was attempted and the provider rejected it ----------------------


def test_handle_overflow_maps_to_did_not_fit_with_a_record_of_the_path() -> None:
    error = ContextOverflow("this model's maximum context length is 128000 tokens")

    decision = handle_overflow(4_200_000, error)

    assert decision.should_call is False
    assert decision.outcome is Outcome.DID_NOT_FIT
    assert decision.trace["fit_check"] == "overflow_on_call"
    assert decision.trace["overflow_on_call"] is True
    assert decision.trace["prompt_chars"] == 4_200_000
    assert "128000" in decision.trace["provider_message"]


def test_handle_overflow_never_raises() -> None:
    # A context overflow is scored data (an outcome), never an error the
    # caller has to catch again — that is the whole point of this function.
    decision = handle_overflow(10, ContextOverflow("boom"))

    assert isinstance(decision.trace, dict)
