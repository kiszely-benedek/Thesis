"""Stage arithmetic: the estimate on the dev numbers, tuning rules, run ids."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.qa.exp0009 import stages


def test_estimate_reproduces_the_design_table_on_the_dev_numbers() -> None:
    by_stage = {
        s: sum(g.estimate_usd for g in stages.stage_groups(s)) for s in ("P1a", "P1b", "P1c")
    }
    assert by_stage["P1a"] == pytest.approx(1.48, abs=0.02)
    assert by_stage["P1b"] == pytest.approx(1.41, abs=0.02)
    assert by_stage["P1c"] == pytest.approx(14.06, abs=0.1)


def test_estimate_note_names_questions_keys_ceiling_and_ledgers(tmp_path: Path) -> None:
    note = stages.render_estimate("P1a", tmp_path, balance="$37.11")
    for expected in (
        "153 q",
        "163 q",
        "key dev",
        "step ceiling $2.22",
        "runs $0.0000",
        "balance $37.11",
    ):
        assert expected in note
    with pytest.raises(ValueError, match="paid stage"):
        stages.render_estimate("P0", tmp_path)


def test_tuning_ends_on_a_small_gain_or_after_round_three() -> None:
    assert stages.next_round_allowed([0.70])[0]
    assert stages.next_round_allowed([0.70, 0.75])[0]
    assert not stages.next_round_allowed([0.70, 0.705])[0]
    assert not stages.next_round_allowed([0.70, 0.75, 0.80])[0]
    assert not stages.next_round_allowed([])[0]


def test_a_round_with_unchanged_b_code_is_refused() -> None:
    stages.require_new_b_code({1: "aaa"}, "bbb")
    with pytest.raises(ValueError, match="round 1"):
        stages.require_new_b_code({1: "aaa"}, "aaa")


def test_run_ids() -> None:
    assert stages.run_id("U9", "D100g22B", "CYP", 2) == "U9-2-CYP-D100g22B"
    assert stages.run_id("U9", "D100g22", "CYP") == "U9-CYP-D100g22"
    assert stages.run_id("S9", "H100g22p1B", "AG") == "S9-AG-H100g22p1B"
