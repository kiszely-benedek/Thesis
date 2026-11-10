"""The $40 ledger, the dry-run caps and the OpenRouter balance check (F15, ADR-0065)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.qa.exp0008 import balance, caps, ledger


def _calls(path: Path, costs: list[tuple[float | None, bool]]) -> None:
    """Write a `calls.jsonl` with one call per (cost, from_cache) pair."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"response": {"cost_usd": c, "from_cache": cached}}) for c, cached in costs]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_only_calls_not_served_from_the_cache_are_paid(tmp_path: Path) -> None:
    _calls(tmp_path / "calls.jsonl", [(0.5, False), (0.7, True), (None, False)])
    assert ledger.paid_usd_of_calls(tmp_path / "calls.jsonl") == pytest.approx(0.5)


def test_a_broken_calls_line_before_the_last_stops_the_count(tmp_path: Path) -> None:
    (tmp_path / "calls.jsonl").write_text('{not json\n{"response": null}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="expected JSON in .*calls.jsonl line 1"):
        ledger.paid_usd_of_calls(tmp_path / "calls.jsonl")


def test_a_truncated_last_calls_line_is_skipped_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _calls(tmp_path / "calls.jsonl", [(0.5, False)])
    with (tmp_path / "calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"response": {"cost_usd": 0.')  # the process died mid-write

    assert ledger.paid_usd_of_calls(tmp_path / "calls.jsonl") == pytest.approx(0.5)
    assert "truncated last line" in caplog.text


def test_runs_spend_adds_up_every_run_and_d4_but_not_the_audit(tmp_path: Path) -> None:
    _calls(tmp_path / "m6a" / "runs" / "r1" / "calls.jsonl", [(1.0, False)])
    _calls(tmp_path / "p3" / "q" / "decisions" / "d4_llm_calls.jsonl", [(0.25, False)])
    _calls(tmp_path / "audit" / "pilot" / "calls.jsonl", [(9.0, False)])
    assert ledger.runs_spent_usd(tmp_path) == pytest.approx(1.25)


def test_a_runs_cap_is_the_smallest_of_dry_cap_step_ceiling_and_ledger(tmp_path: Path) -> None:
    step = tmp_path / "step"
    _calls(step / "runs" / "a" / "calls.jsonl", [(3.0, False)])
    _calls(tmp_path / "other" / "calls.jsonl", [(25.0, False)])  # 28.0 spent in all
    assert ledger.run_cap_usd(5.0, tmp_path, step, 10.0) == pytest.approx(
        2.0
    )  # the ledger: 30 - 28
    assert ledger.run_cap_usd(1.0, tmp_path, step, 10.0) == pytest.approx(1.0)  # its own dry cap
    assert ledger.run_cap_usd(5.0, tmp_path, step, 3.5) == pytest.approx(0.5)  # the step: 3.5 - 3.0


def test_an_exhausted_ledger_or_step_is_refused(tmp_path: Path) -> None:
    _calls(tmp_path / "s" / "calls.jsonl", [(30.0, False)])
    with pytest.raises(ledger.LedgerExhausted, match=r"runs ledger"):
        ledger.run_cap_usd(1.0, tmp_path, tmp_path / "s", 100.0)
    with pytest.raises(ledger.LedgerExhausted, match=r"step ceiling"):
        ledger.run_cap_usd(1.0, tmp_path, tmp_path / "s", 30.0)


def test_the_audit_cap_is_ten_dollars_or_what_the_runs_leave(tmp_path: Path) -> None:
    assert ledger.audit_cap_usd(tmp_path) == 10.0
    _calls(tmp_path / "m6a" / "calls.jsonl", [(33.0, False)])
    assert ledger.audit_cap_usd(tmp_path) == pytest.approx(7.0)
    (tmp_path / "audit").mkdir()
    (tmp_path / "audit" / "ledger.jsonl").write_text(
        json.dumps({"stage": "pilot", "item_key": "k", "paid_usd": 7.0}) + "\n", encoding="utf-8"
    )
    with pytest.raises(ledger.LedgerExhausted, match="money left for the audit"):
        ledger.audit_cap_usd(tmp_path)


def test_a_dry_cap_is_misses_times_cost_times_one_and_a_half_with_a_floor() -> None:
    assert caps.run_cap_usd(100, "cyp") == pytest.approx(100 * 0.00075 * 1.5, abs=1e-4)
    assert (
        caps.run_cap_usd(0, "ag") == caps.MIN_RUN_CAP_USD
    )  # all cached: the harness still needs a cap
    with pytest.raises(ValueError, match="expected a tier"):
        caps.run_cap_usd(1, "gpu")


def test_p4_arms_and_ladder_sizes_have_their_own_measured_cost_per_question() -> None:
    assert caps.COST_PER_QUESTION_USD["cyp-d4"] == pytest.approx(0.0938 / 83, rel=1e-3)
    assert caps.COST_PER_QUESTION_USD["ag-d4"] > caps.COST_PER_QUESTION_USD["ag-d0"]
    # a 1-sheet ContextRAG run is capped far below the old 2.67/236 average
    assert caps.run_cap_usd(70, "ctx-H1g21") == pytest.approx(70 * 0.00274 * 1.5, abs=1e-4)
    assert caps.run_cap_usd(70, "ctx-H10g21") == pytest.approx(70 * 0.02172 * 1.5, abs=1e-4)


def test_a_cap_always_covers_the_reservations_of_the_questions_in_flight() -> None:
    # the smoke stopped on ag-d2: 5 x 0.00266 = 0.0133 is above the 0.01 floor
    assert caps.run_cap_usd(0, "ag-d2") == pytest.approx(5 * 0.00266, abs=1e-4)
    assert caps.run_cap_usd(1, "ctx-H10g21") == pytest.approx(5 * 0.02172, abs=1e-4)
    assert caps.run_cap_usd(100, "ag-d2") == pytest.approx(100 * 0.00266 * 1.5, abs=1e-4)


def test_every_ceiling_of_the_design_is_present_and_the_runs_ceilings_fit_the_ledger() -> None:
    assert caps.STEP_CEILING_USD["M5"] == 4.90 and caps.STEP_CEILING_USD["M8b"] == 7.28
    # design 6: the 1.5x caps sum to $33.14 with the $0.15 smokes, for which there is no stage
    assert sum(caps.STEP_CEILING_USD.values()) == pytest.approx(33.14 - 0.15)


def _fetch(total: float, usage: float) -> balance.CreditsFetcher:
    reply = json.dumps({"data": {"total_credits": total, "total_usage": usage}})
    return lambda: reply


def test_the_balance_is_credits_minus_usage_and_must_cover_the_need() -> None:
    assert balance.balance_usd(_fetch(50.0, 12.5)) == pytest.approx(37.5)
    assert balance.require_balance(30.0, _fetch(50.0, 12.5)) == pytest.approx(37.5)
    with pytest.raises(balance.BalanceError, match=r"at least \$40.00, found \$37.50"):
        balance.require_balance(40.0, _fetch(50.0, 12.5))


def test_an_unreadable_balance_reply_is_an_error() -> None:
    with pytest.raises(balance.BalanceError, match="expected data.total_credits"):
        balance.balance_usd(lambda: '{"error": "nope"}')


def test_the_key_never_reaches_an_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret-123")
    monkeypatch.setenv(
        "OPENROUTER_BASE_URL", "http://127.0.0.1:9"
    )  # nothing listens: the call fails
    with pytest.raises(balance.BalanceError) as error:
        balance.fetch_credits_json()
    assert "sk-secret-123" not in str(error.value)


def test_a_resumed_run_keeps_its_earlier_spend_under_the_new_cap(tmp_path: Path) -> None:
    run = tmp_path / "step" / "runs" / "r1"
    _calls(run / "calls.jsonl", [(2.0, False), (0.5, True)])
    # the allowance is bounded by what the step ceiling and the ledger still allow (4.9 - 2.0)
    assert ledger.resumed_run_cap_usd(0.01, tmp_path, tmp_path / "step", 4.9, run) == pytest.approx(
        2.01
    )
    assert ledger.resumed_run_cap_usd(9.0, tmp_path, tmp_path / "step", 4.9, run) == pytest.approx(
        4.9
    )
    fresh = tmp_path / "step" / "runs" / "new"
    assert ledger.resumed_run_cap_usd(
        0.2, tmp_path, tmp_path / "step", 4.9, fresh
    ) == pytest.approx(0.2)
