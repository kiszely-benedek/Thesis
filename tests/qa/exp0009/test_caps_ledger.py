"""Caps from question counts, the ledger cut, the resume rule, and the `reports/` glob fix."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from plantgraph.qa.exp0008 import ledger as old_ledger
from plantgraph.qa.exp0008.ledger import LedgerExhausted
from plantgraph.qa.exp0009 import caps, ledger


def _paid_calls(path: Path, usd: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"response": {"from_cache": False, "cost_usd": usd}}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_cap_is_questions_times_cost_times_one_and_a_half() -> None:
    assert caps.run_cap_usd(100, 0.002) == pytest.approx(0.3, abs=1e-4)


def test_cap_never_below_five_questions() -> None:
    assert caps.run_cap_usd(1, 0.01) == 0.05


def test_b_costs_ten_percent_more_until_measured() -> None:
    a2 = caps.cost_per_question_usd("ag", 100, arm="A2")
    assert caps.cost_per_question_usd("ag", 100, arm="B") == round(a2 * 1.1, 6)
    measured = {"B-ag-100": 0.003}
    assert caps.cost_per_question_usd("ag", 100, arm="B", measured=measured) == 0.003
    with pytest.raises(ValueError, match="cost key"):
        caps.cost_per_question_usd("ctx", 100, arm="A2")


def test_ledger_cuts_cap_to_step_and_program(tmp_path: Path) -> None:
    step = tmp_path / "p1a"
    _paid_calls(step / "runs" / "r1" / "calls.jsonl", 2.0)
    assert ledger.run_cap_usd(5.0, tmp_path, step, 2.22) == pytest.approx(0.22)
    with pytest.raises(LedgerExhausted):
        ledger.run_cap_usd(5.0, tmp_path, step, 2.0)
    _paid_calls(tmp_path / "other" / "calls.jsonl", 25.0)
    with pytest.raises(LedgerExhausted, match="runs ledger"):
        ledger.run_cap_usd(1.0, tmp_path, tmp_path / "none", 99.0)


def test_resumed_run_adds_what_it_spent(tmp_path: Path) -> None:
    run = tmp_path / "s" / "runs" / "r"
    _paid_calls(run / "calls.jsonl", 0.5)
    cap = ledger.resumed_run_cap_usd(1.0, tmp_path, tmp_path / "s", 5.0, run)
    assert cap == pytest.approx(1.5)


def test_audit_cap_is_the_lesser_of_8_13_and_what_is_left(tmp_path: Path) -> None:
    assert ledger.audit_cap_usd(tmp_path) == 8.13
    _paid_calls(tmp_path / "runs" / "calls.jsonl", 30.0)
    assert ledger.audit_cap_usd(tmp_path) == 5.0
    _paid_calls(tmp_path / "runs2" / "calls.jsonl", 10.0)
    with pytest.raises(LedgerExhausted):
        ledger.audit_cap_usd(tmp_path)


def test_copy_under_reports_is_not_counted_twice(tmp_path: Path) -> None:
    original = tmp_path / "p1c" / "runs" / "S9-AG-x" / "calls.jsonl"
    _paid_calls(original, 1.25)
    copy = tmp_path / "reports" / "x" / "runs" / "S9-AG-x" / "calls.jsonl"
    copy.parent.mkdir(parents=True)
    shutil.copy(original, copy)
    _paid_calls(tmp_path / "audit" / "main" / "calls.jsonl", 0.5)
    assert ledger.runs_spent_usd(tmp_path) == pytest.approx(1.25)
    assert old_ledger.runs_spent_usd(tmp_path) == pytest.approx(2.5)  # EXP-0008's glob, unchanged
