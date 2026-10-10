"""Cost estimate and spend tracking of the demo, from toy runs and a toy call log."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_run_toy import PIN, row, write_run
from plantgraph.demo.app.estimate import RESERVATION_FACTOR, NoCostEvidence, estimate_cost
from plantgraph.demo.app.models import CostEstimate, TierCostStats
from plantgraph.demo.app.spend import SessionSpend, total_spent_usd
from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.harness.spend_cap import SpendCapReached
from plantgraph.qa.models import QuestionResult

OTHER_PIN = ModelPin(backend="openrouter", model_id="toy/other", max_output_tokens=100)


def _policy() -> CascadePolicy:
    accept = frozenset({AcceptRule.ANSWERED})
    return CascadePolicy(
        name="toy",
        tiers=(
            TierSpec(name="first", strategy="cheap", pin_sha256=PIN.pin_hash(), accept=accept),
            TierSpec(name="second", strategy="dear", pin_sha256=PIN.pin_hash(), accept=accept),
        ),
    )


def _rows() -> list[QuestionResult]:
    cheap = [row(f"q{i}", "cheap", cost) for i, cost in enumerate([0.001, 0.003, 0.002])]
    # a question's cost is its final call plus its retrieval calls
    return cheap + [row("q0", "dear", 0.01, retrieval_cost=0.01), row("q1", "dear", 0.05)]


def test_estimate_is_median_and_max_with_the_run_ids(tmp_path: Path) -> None:
    run = write_run(tmp_path, "run-A", "TOY", _rows())

    estimate = estimate_cost(_policy(), [run], "TOY")

    assert estimate.per_tier["first"] == TierCostStats(
        median_usd=0.002, max_usd=0.003, n_questions=3, run_ids=("run-A",), other_corpus=False
    )
    second = estimate.per_tier["second"]
    assert (second.median_usd, second.max_usd, second.n_questions) == (0.035, 0.05, 2)
    assert estimate.reservation_usd == pytest.approx(RESERVATION_FACTOR * (0.003 + 0.05))


def test_a_run_under_another_pin_is_not_used(tmp_path: Path) -> None:
    other = write_run(tmp_path, "run-other-pin", "TOY", _rows(), pin=OTHER_PIN)

    with pytest.raises(NoCostEvidence, match="first"):
        estimate_cost(_policy(), [other], "TOY")


def test_another_corpus_stands_in_and_is_labelled(tmp_path: Path) -> None:
    elsewhere = write_run(tmp_path, "run-B", "ELSE", _rows())

    estimate = estimate_cost(_policy(), [elsewhere], "TOY")

    assert estimate.per_tier["first"].other_corpus is True
    assert estimate.per_tier["first"].run_ids == ("run-B",)


def test_runs_of_the_asked_corpus_win_over_other_corpora(tmp_path: Path) -> None:
    own_rows = [row("q0", "cheap", 0.001), row("q0", "dear", 0.02)]
    own = write_run(tmp_path, "run-own", "TOY", own_rows)
    elsewhere = write_run(tmp_path, "run-else", "ELSE", _rows())

    estimate = estimate_cost(_policy(), [elsewhere, own], "TOY")

    assert estimate.per_tier["first"].run_ids == ("run-own",)
    assert estimate.per_tier["first"].other_corpus is False


def _session(cap: float | None, tmp_path: Path) -> SessionSpend:
    stats = TierCostStats(
        median_usd=0.1, max_usd=0.1, n_questions=1, run_ids=("r",), other_corpus=False
    )
    estimate = CostEstimate(per_tier={"first": stats}, reservation_usd=0.15)
    return SessionSpend(cap, estimate, tmp_path / "calls.jsonl")


def test_a_reservation_that_would_pass_the_cap_is_refused(tmp_path: Path) -> None:
    session = _session(0.20, tmp_path)

    first = session.reserve()  # 0.15 of 0.20 set aside
    with pytest.raises(SpendCapReached, match="cap of 0.200000"):
        session.reserve()  # 0.15 + 0.15 would pass 0.20
    session.release(first, 0.0)
    session.reserve()  # room again once the first question closed


def test_an_unlimited_session_never_refuses(tmp_path: Path) -> None:
    session = _session(None, tmp_path)

    session.reserve()
    session.reserve()


def _call_line(cost: float | None, from_cache: bool, error_kind: str | None = None) -> str:
    response = None
    if cost is not None:
        response = {
            "text": "",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "cost_usd": cost,
            "latency_s": 1.0,
            "provider_response_id": None,
            "finish_reason": "stop",
            "from_cache": from_cache,
            "created_at": "2026-10-10T00:00:00Z",
        }
    return json.dumps(
        {
            "run_id": "demo",
            "purpose": "answer",
            "cache_key": "k",
            "pin_hash": "p",
            "prompt_sha256": "s",
            "response": response,
            "error_kind": error_kind,
        }
    )


def test_all_time_spend_sums_paid_calls_only(tmp_path: Path) -> None:
    log = tmp_path / "calls.jsonl"
    lines = [
        _call_line(0.01, from_cache=False),
        _call_line(0.50, from_cache=True),  # a cache hit costs nothing now
        _call_line(0.02, from_cache=False, error_kind="late_after_timeout"),  # billed
        _call_line(None, from_cache=False, error_kind="timeout"),  # no response, no cost
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert total_spent_usd(log) == pytest.approx(0.03)
    assert total_spent_usd(tmp_path / "missing.jsonl") == 0.0


def test_status_reports_session_cap_and_all_time_spend(tmp_path: Path) -> None:
    session = _session(0.5, tmp_path)
    line = _call_line(0.04, from_cache=False) + "\n"
    (tmp_path / "calls.jsonl").write_text(line, encoding="utf-8")

    status = session.status()

    assert (status.session_spent_usd, status.session_cap_usd) == (0.0, 0.5)
    assert status.demo_total_spent_usd == pytest.approx(0.04)
