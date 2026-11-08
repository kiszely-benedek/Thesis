"""The first measurement's constants EXP-0008 parameterises keep their defaults (F15, ADR-0065)."""

from __future__ import annotations

import pytest

from plantgraph.exp0004 import e2e_caps
from plantgraph.exp0004.e2e_dry_run import DryRunReport
from plantgraph.qa.cascade.tune_select import TUNING_CORPUS_ID, TUNING_CORPUS_IDS, select_variant


def _report(n_questions_with_miss: int) -> DryRunReport:
    return DryRunReport(
        run_id="r", n_questions=10, n_calls=0, n_cache_hits=0, n_miss_calls=0,
        n_questions_with_miss=n_questions_with_miss, questions_with_miss=[], misses_by_purpose={},
    )  # fmt: skip


def test_the_variant_choice_is_defined_on_either_tuning_plant_only() -> None:
    assert TUNING_CORPUS_ID == "X100g2s211" and "X100g21s211" in TUNING_CORPUS_IDS
    assert select_variant("X100g21s211", "A", 10, 6, 7).chosen == "cascade_v4_iso"
    with pytest.raises(ValueError, match="EXP-0008's tuning set is 'X100g21s211'"):
        select_variant("VAL100g21", "A", 10, 6, 7)


def test_e2e_caps_default_to_the_first_measurements_prices_and_bound() -> None:
    caps = e2e_caps.compute_caps("d0", _report(100), _report(100))
    assert caps.cost_per_question_usd == e2e_caps.COST_PER_QUESTION_USD
    assert caps.cap_usd["ag"] == pytest.approx(100 * 0.00189 * 1.5, abs=1e-4)
    assert e2e_caps.split_cap(caps, caps.total_cap_usd)  # within the P4 bound of 4.44


def test_e2e_caps_take_exp0008s_own_prices_and_bound() -> None:
    prices = {"cyp": 0.001, "ag": 0.002}
    caps = e2e_caps.compute_caps("d0", _report(100), _report(100), prices)
    assert caps.cost_per_question_usd == prices and caps.cap_usd["cyp"] == pytest.approx(
        0.15, abs=1e-3
    )
    with pytest.raises(ValueError, match="at most 0.2"):
        e2e_caps.split_cap(caps, 0.3, above_dry_cap=True, bound_usd=0.2)
    assert e2e_caps.split_cap(caps, 0.3, above_dry_cap=True, bound_usd=7.28)


def test_the_audit_commands_take_a_cap_and_default_to_the_hard_cap() -> None:
    from plantgraph.qa.audit import cli
    from plantgraph.qa.audit.budget import HARD_CAP_USD

    base = ["--run", "r", "--questions-root", "q", "--ledger", "l"]
    default = cli._parse_args(["select", *base, "--out", "o"])
    cut = cli._parse_args(["select", *base, "--out", "o", "--cap-usd", "7.5"])
    assert default.cap_usd == HARD_CAP_USD and cut.cap_usd == 7.5
