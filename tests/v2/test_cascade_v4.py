"""QT-6: cascade_v4 and cascade_v4_iso, the `complete` rule, the two limit settings, the report.

Everything runs offline over toy stored runs (`cascade_toy`): no model call, no database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pytest

from cascade_v4_toy import AGENT_V2T, CYPHER_V2T, loaded_tier, pin
from plantgraph.qa.cascade.accept import first_failed_rule, is_accepted, walk_question
from plantgraph.qa.cascade.limits import SETTING_A, SETTING_B, LimitSetting, run_problems
from plantgraph.qa.cascade.models import AcceptRule, Signals
from plantgraph.qa.cascade.policy import POLICIES_DIR, V2T_POLICIES_DIR, load_policies
from plantgraph.qa.cascade.tune_select import TUNING_CORPUS_ID, V4, V4_ISO, select_variant
from plantgraph.qa.models import Outcome
from plantgraph.qa.need.labels import NeedLabel


def _signals(**fields: Any) -> Signals:
    base: dict[str, Any] = {
        "question_id": "q",
        "tier": "cypher-v2t",
        "outcome": Outcome.ANSWERED,
        "n_rows": 3,
        "truncated": False,
        "not_present": False,
        "runaway": False,
        "cost_usd": 0.0,
        "latency_s": 1.0,
        "final_latency_s": 1.0,
        "latency_complete": True,
        "need_label": None,
    }
    return Signals(**(base | fields))


# ---- the shipped policies ------------------------------------------------------------------


def test_the_v4_policies_are_the_two_luna_tiers_with_the_complete_rule() -> None:
    policies = load_policies(V2T_POLICIES_DIR)
    v3 = load_policies(POLICIES_DIR)["cascade_v3"]

    assert set(policies) == {V4, V4_ISO}
    for policy in policies.values():
        cypher, agent = policy.tiers
        assert (cypher.strategy, agent.strategy) == (CYPHER_V2T, AGENT_V2T)
        assert cypher.accept == {"answered", "not_abstained", "rows", "complete"}
        assert agent.accept == {AcceptRule.ANSWERED}
        assert (cypher.pin_sha256, agent.pin_sha256) == (
            v3.tiers[0].pin_sha256,
            v3.tiers[1].pin_sha256,
        )
    assert not policies[V4].start_tier_by_label
    assert policies[V4_ISO].start_tier_by_label == {
        NeedLabel.UPSTREAM_TO_FIRST_VALVE: 1,
        NeedLabel.DOWNSTREAM_TO_FIRST_VALVE: 1,
    }


def test_f1s_policy_folder_does_not_list_the_v2t_policies() -> None:
    assert not {V4, V4_ISO} & set(load_policies(POLICIES_DIR))


def test_the_two_v2t_pins_are_the_pins_of_the_policies() -> None:
    policy = load_policies(V2T_POLICIES_DIR)[V4]

    assert pin("pin_cypher_luna_low.json").pin_hash() == policy.tiers[0].pin_sha256
    assert pin("pin_agent_luna_final_high.json").pin_hash() == policy.tiers[1].pin_sha256


# ---- the complete rule ---------------------------------------------------------------------

ALL_RULES = frozenset(AcceptRule)


def test_a_result_cut_at_the_row_cap_is_not_accepted() -> None:
    assert is_accepted(_signals(truncated=False), ALL_RULES)
    assert not is_accepted(_signals(truncated=True), ALL_RULES)
    assert first_failed_rule(_signals(truncated=True), ALL_RULES) is AcceptRule.COMPLETE


def test_rules_are_checked_in_order_so_the_first_failure_is_named() -> None:
    cut_and_empty = _signals(n_rows=0, truncated=True)
    assert first_failed_rule(cut_and_empty, ALL_RULES) is AcceptRule.ROWS
    assert (
        first_failed_rule(_signals(outcome=Outcome.RETRIEVAL_ERROR), ALL_RULES)
        is AcceptRule.ANSWERED
    )
    assert first_failed_rule(_signals(not_present=True), ALL_RULES) is AcceptRule.NOT_ABSTAINED


def test_complete_without_a_record_of_the_cut_is_an_error_not_a_pass() -> None:
    with pytest.raises(ValueError, match="record whether its query result was cut"):
        is_accepted(_signals(truncated=None), ALL_RULES)


def test_f1s_rules_do_not_read_the_cut_flag() -> None:
    f1_rules = frozenset({AcceptRule.ANSWERED, AcceptRule.ROWS, AcceptRule.NOT_ABSTAINED})

    assert is_accepted(_signals(truncated=True), f1_rules)
    assert is_accepted(_signals(truncated=None), f1_rules)


def test_a_cut_cypher_answer_escalates_to_the_agent() -> None:
    policy = load_policies(V2T_POLICIES_DIR)[V4]
    signals = {
        "cypher-v2t": {"q": _signals(truncated=True)},
        "agent-v2t": {"q": _signals(tier="agent-v2t", n_rows=None, truncated=None)},
    }

    walk = walk_question(policy, "q", None, signals)

    assert walk.tried == ("cypher-v2t", "agent-v2t") and walk.accepted == "agent-v2t"


def test_the_iso_policy_starts_first_valve_questions_at_the_agent() -> None:
    iso = load_policies(V2T_POLICIES_DIR)[V4_ISO]
    signals = {"agent-v2t": {"q": _signals(tier="agent-v2t", n_rows=None, truncated=None)}}

    walk = walk_question(iso, "q", NeedLabel.DOWNSTREAM_TO_FIRST_VALVE, signals)

    assert walk.tried == ("agent-v2t",) and walk.missing_tier is None


# ---- the two limit settings ----------------------------------------------------------------


def test_the_settings_are_a_timeout_and_one_limit_each() -> None:
    assert (SETTING_A.cypher_timeout_s, SETTING_A.cutoff_s) == (30.0, 120.0)
    assert SETTING_A.question_deadline_s == 120.0 and SETTING_A.hang_guard_s is None
    assert (SETTING_B.cypher_timeout_s, SETTING_B.cutoff_s) == (120.0, 900.0)
    assert SETTING_B.question_deadline_s is None and SETTING_B.hang_guard_s == 900.0


def test_a_setting_needs_exactly_one_of_deadline_and_hang_guard() -> None:
    for fields in ({}, {"question_deadline_s": 1.0, "hang_guard_s": 2.0}):
        with pytest.raises(ValueError, match="exactly one of"):
            LimitSetting(name="A", cypher_timeout_s=1.0, **fields)


def test_run_problems_is_empty_when_the_runs_match_the_setting(tmp_path: Path) -> None:
    runs = {
        "cypher-v2t": loaded_tier(tmp_path / "a", 0),
        "agent-v2t": loaded_tier(tmp_path / "b", 1),
    }

    assert run_problems(SETTING_A, runs) == []


def test_run_problems_catches_a_cypher_timeout_of_the_other_setting(tmp_path: Path) -> None:
    runs = {
        "cypher-v2t": loaded_tier(tmp_path / "a", 0, timeout_s=120.0),
        "agent-v2t": loaded_tier(tmp_path / "b", 1),
    }

    problems = run_problems(SETTING_A, runs)

    assert len(problems) == 1 and "timeout_s 30" in problems[0] and "120.0" in problems[0]
    assert run_problems(SETTING_B, runs) == []  # a 120 s Cypher timeout is exactly B's


def test_run_problems_catches_a_deadline_shorter_than_the_limit(tmp_path: Path) -> None:
    runs = {"cypher-v2t": loaded_tier(tmp_path / "a", 0, timeout_s=120.0, deadline_s=120.0)}

    assert run_problems(SETTING_A, runs) != []  # the cypher timeout is B's
    assert any("question deadline" in p for p in run_problems(SETTING_B, runs))


def test_run_problems_catches_tiers_with_different_v2t_templates(tmp_path: Path) -> None:
    runs = {
        "cypher-v2t": loaded_tier(tmp_path / "a", 0, template_hash="1" * 64),
        "agent-v2t": loaded_tier(tmp_path / "b", 1, template_hash="2" * 64),
    }

    assert any("final_answer_v2t.txt" in p for p in run_problems(SETTING_A, runs))


# ---- the pre-registered choice -------------------------------------------------------------


@pytest.mark.parametrize("setting", ["A", "B"])
@pytest.mark.parametrize(
    ("n_v4", "n_iso", "chosen"),
    [(100, 101, V4_ISO), (100, 100, V4_ISO), (100, 99, V4)],
)
def test_iso_replaces_v4_iff_its_primary_accuracy_on_t_is_at_least_v4s(
    setting: Literal["A", "B"], n_v4: int, n_iso: int, chosen: str
) -> None:
    choice = select_variant(TUNING_CORPUS_ID, setting, 163, n_v4, n_iso)

    assert choice.chosen == chosen and (choice.n_correct_v4, choice.n_correct_v4_iso) == (
        n_v4,
        n_iso,
    )
    assert choice.basis == ("within 120 s" if setting == "A" else "uncut")


def test_the_choice_is_refused_on_any_corpus_but_the_tuning_set() -> None:
    with pytest.raises(ValueError, match="tuning set 'X100g2s211', found 'X100g2s212'"):
        select_variant("X100g2s212", "A", 163, 100, 100)
    with pytest.raises(ValueError, match="correct count in 0..10"):
        select_variant(TUNING_CORPUS_ID, "B", 10, 11, 5)
