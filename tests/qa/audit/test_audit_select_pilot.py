"""Row selection in the registered budget order, the ledger, sizing and the pilot (F14)."""

from __future__ import annotations

from pathlib import Path

import pytest

from audit_fakes import make_question, make_result, make_run, make_source_row
from plantgraph.qa.audit.budget import (
    SIZING_SAFETY_FACTOR,
    LedgerLine,
    SpendLedger,
    sizing_cost_per_call,
)
from plantgraph.qa.audit.models import SourceRow
from plantgraph.qa.audit.pilot import (
    MIN_DEFECTS_PER_GROUP,
    N_CONTROLS,
    build_pilot_set,
    parse_failure_candidates,
)
from plantgraph.qa.audit.select import AuditPlan, select_audit
from plantgraph.qa.models import AnswerType, Outcome, QuestionFamily

F = QuestionFamily
_FAMILIES = [F.LOOKUP_TYPE, F.CONNECTED, F.COUNT_IN_UNIT, F.FLOW_PATH]


def _pool() -> list[SourceRow]:
    """4 families x 2 scales; per (family, scale): 7 right rows, 3 wrong rows."""
    rows = []
    for scale_index, corpus in enumerate(["H100g21p1", "H1000g21p1"]):
        for family_index, family in enumerate(_FAMILIES):
            base = (scale_index * 10 + family_index) * 100
            for number in range(10):
                rows.append(
                    make_source_row(
                        base + number, family=family, correct=number >= 3, scale_corpus=corpus
                    )
                )
    return rows


def _select(pool: list[SourceRow], remaining: float, seed: int = 1) -> AuditPlan:
    contextrag = [make_source_row(900 + n, correct=False, run_id="ctx") for n in range(6)]
    return select_audit(pool, contextrag, seed=seed, call_usd=0.02, remaining_usd=remaining)


def _strata(plan: AuditPlan) -> list[str]:
    return [item.stratum for item in plan.items]


def test_rows_are_judged_right_minimum_first_then_wrong_then_contextrag_then_more_right() -> None:
    plan = _select(_pool(), remaining=10.0)

    strata = _strata(plan)
    assert strata == sorted(
        strata, key=["right_min", "wrong", "contextrag_wrong", "right_extra"].index
    )
    assert strata.count("wrong") == 24  # every distinct wrong row
    assert strata.count("right_min") == 16  # 2 per family per scale
    assert strata.count("contextrag_wrong") == 6
    assert strata.count("right_extra") == 24  # up to 5 per group: 3 more each


def test_the_selection_is_reproducible_from_its_seed_and_changes_with_it() -> None:
    first, again, other = _select(_pool(), 10.0), _select(_pool(), 10.0), _select(_pool(), 10.0, 2)

    assert first == again
    assert first.items != other.items


def test_the_minimum_right_sample_is_a_prefix_of_the_larger_one() -> None:
    plan = _select(_pool(), remaining=10.0)

    keys = {(i.row.family, i.row.scale) for i in plan.items if i.stratum == "right_min"}
    assert len(keys) == 8
    min_ids = {i.row.question_id for i in plan.items if i.stratum == "right_min"}
    extra_ids = {i.row.question_id for i in plan.items if i.stratum == "right_extra"}
    assert not min_ids & extra_ids


@pytest.mark.parametrize("remaining", [0.41, 0.55, 0.91, 1.35, 10.0])
def test_sizing_never_exceeds_the_remaining_budget(remaining: float) -> None:
    plan = _select(_pool(), remaining)

    assert plan.estimated_usd <= remaining + 1e-9


def test_a_tight_budget_cuts_the_wrong_rows_across_families_and_keeps_the_right_minimum() -> None:
    roomy = _select(_pool(), remaining=0.91)  # 45 calls: 16 right_min, all 24 wrong, 5 more
    tight = _select(_pool(), remaining=0.61)  # 30 calls: 16 right_min and 14 of the 24 wrong

    assert _strata(tight).count("right_min") == 16
    assert tight.wrong_selected == 14 and tight.wrong_available == 24
    families = {i.row.family for i in tight.items if i.stratum == "wrong"}
    assert families == set(_FAMILIES)  # the cut is spread, not the first families only
    assert _strata(roomy).count("wrong") == 24


def test_a_budget_below_the_minimum_right_sample_is_refused() -> None:
    with pytest.raises(ValueError, match="minimum right-sample"):
        _select(_pool(), remaining=0.11)


def test_two_tiers_giving_the_same_wrong_answer_are_one_row() -> None:
    twin_a = make_source_row(1, correct=False, strategy="cypher")
    twin_b = make_source_row(1, correct=False, strategy="agent")
    different = make_source_row(1, correct=False, strategy="other", answer="Valve")
    right = [make_source_row(n, family=F.CONNECTED, correct=True) for n in range(20, 24)]

    plan = _select([twin_a, twin_b, different, *right], remaining=10.0)

    wrong = [i.row for i in plan.items if i.stratum == "wrong"]
    assert len(wrong) == 2 and {r.answer_key for r in wrong} == {
        twin_a.answer_key,
        different.answer_key,
    }


def test_rows_without_an_answer_are_not_audit_rows(tmp_path: Path) -> None:
    from plantgraph.qa.audit.sources import count_without_answer, source_rows

    question = make_question(1)
    errored = make_result(question, correct=False, answer=None, outcome=Outcome.RETRIEVAL_ERROR)
    run = make_run("r", [(question, errored)])

    assert source_rows(run) == [] and count_without_answer(run) == 1


# --- ledger and sizing -----------------------------------------------------------------------


def test_the_ledger_shares_one_cap_and_a_stage_cap(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "ledger.jsonl", cap_usd=1.0)
    ledger.record(LedgerLine(stage="pilot", item_key="a", paid_usd=0.60))
    ledger.record(LedgerLine(stage="audit", item_key="b", paid_usd=0.30))

    assert ledger.spent_usd() == pytest.approx(0.90)
    assert ledger.spent_usd("pilot") == pytest.approx(0.60)
    assert ledger.remaining_usd() == pytest.approx(0.10)
    assert ledger.allows(0.05, "audit")
    assert not ledger.allows(0.11, "audit")  # over the shared cap
    assert not ledger.allows(0.05, "pilot", stage_cap_usd=0.62)  # over the pilot's own cap


def test_sizing_uses_the_measured_pilot_cost_with_a_safety_factor(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "ledger.jsonl")
    for key, paid in [("a", 0.010), ("b", 0.020), ("c", 0.0)]:  # a cache hit is not a call
        ledger.record(LedgerLine(stage="pilot", item_key=key, paid_usd=paid))

    measured = ledger.measured_cost_per_call("pilot")

    assert measured == pytest.approx(0.015)
    assert sizing_cost_per_call(measured) == pytest.approx(0.015 * SIZING_SAFETY_FACTOR)
    with pytest.raises(ValueError, match="no paid calls|found none"):
        ledger.measured_cost_per_call("audit")


# --- the pilot set ---------------------------------------------------------------------------


N_VALVES_FOUND = 16  # the real first-measurement counts: more valves rows than planned,
N_PARSE_FOUND = 9  # fewer parse rows than planned


def _pilot_pool(
    n_valves: int = N_VALVES_FOUND, n_parse: int = N_PARSE_FOUND
) -> tuple[list[SourceRow], list[SourceRow], set[str]]:
    valves = [
        make_source_row(n, family=F.VALVES_ON_PATH, correct=False, scale_corpus="H1000g21p1")
        for n in range(n_valves)
    ]
    parse = [
        make_source_row(500 + n, family=F.UNITS_REACHED, correct=False) for n in range(n_parse)
    ]
    controls = [
        make_source_row(700 + n, family=_FAMILIES[n % 4], correct=True)
        for n in range(N_CONTROLS + 6)
    ]
    return [*valves, *controls], parse, {r.question_id for r in valves}


def test_the_pilot_keeps_every_defect_row_and_exactly_20_controls() -> None:
    pool, parse, valve_ids = _pilot_pool()

    items = build_pilot_set(pool, parse, valve_ids, seed=3)

    kinds = [item.stratum for item in items]
    assert kinds.count("pilot_defect_valves") == 16
    assert kinds.count("pilot_defect_parse") == 9
    assert kinds.count("pilot_control") == N_CONTROLS == 20
    assert len(items) == 16 + 9 + 20
    assert all(i.row.scorer_correct for i in items if i.stratum == "pilot_control")
    assert build_pilot_set(pool, parse, valve_ids, seed=3) == items  # reproducible


def test_the_pilot_refuses_a_defect_group_below_the_minimum() -> None:
    pool, parse, valve_ids = _pilot_pool()
    few = MIN_DEFECTS_PER_GROUP - 1

    with pytest.raises(ValueError, match=f"at least 8 parse-failure defect rows.*found {few}"):
        build_pilot_set(pool, parse[:few], valve_ids, seed=3)
    with pytest.raises(ValueError, match=f"at least 8 VALVES_ON_PATH defect rows.*found {few}"):
        build_pilot_set(pool, parse, set(sorted(valve_ids)[:few]), seed=3)
    build_pilot_set(pool, parse[:8], set(sorted(valve_ids)[:8]), seed=3)  # exactly 8 is enough


def test_the_pilot_refuses_too_few_controls() -> None:
    pool, parse, valve_ids = _pilot_pool()

    with pytest.raises(ValueError, match="expected 20 control rows.*found 10"):
        build_pilot_set(pool[:-16], parse, valve_ids, seed=3)


def test_parse_failure_candidates_are_the_failures_the_current_parser_reads() -> None:
    question = make_question(1, F.UNITS_REACHED, answer_type=AnswerType.UNIT_SET).model_copy(
        update={"reference": ["3", "7"]}
    )
    readable = make_result(
        question, correct=False, answer=None, outcome=Outcome.PARSE_FAILURE,
        raw_reply='{"answer": [3, 7], "not_present": false}',
    )  # fmt: skip
    other = make_question(2, F.UNITS_REACHED, answer_type=AnswerType.UNIT_SET)
    garbage = make_result(
        other, correct=False, answer=None, outcome=Outcome.PARSE_FAILURE, raw_reply="no idea"
    )
    run = make_run("r", [(question, readable), (other, garbage)])

    found = parse_failure_candidates(run)

    assert [row.question_id for row in found] == [question.question_id]


def test_a_re_read_answer_that_is_still_wrong_is_not_a_parse_defect() -> None:
    question = make_question(1, F.UNITS_REACHED, answer_type=AnswerType.UNIT_SET).model_copy(
        update={"reference": ["3", "7"]}
    )
    wrong_but_readable = make_result(
        question, correct=False, answer=None, outcome=Outcome.PARSE_FAILURE,
        raw_reply='{"answer": [3, 9], "not_present": false}',
    )  # fmt: skip
    run = make_run("r", [(question, wrong_but_readable)])

    assert parse_failure_candidates(run) == []
