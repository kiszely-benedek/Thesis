"""The main audit sample is drawn from scope R rows only (ADR-0069, F9)."""

from __future__ import annotations

import pytest

from plantgraph.qa.audit.models import SourceRow
from plantgraph.qa.exp0009 import audit_select
from plantgraph.qa.models import Outcome, QuestionFamily
from plantgraph.qa.questions.scope_x import SCOPE_X_FAMILIES


def _row(index: int, family: QuestionFamily, correct: bool) -> SourceRow:
    return SourceRow(
        run_id="S9-AG-H100g22p1", strategy="graph_agent_lines", question_id=f"q{index}",
        corpus_id="H100g22p1", family=family, scale="100", outcome=Outcome.ANSWERED,
        scorer_correct=correct, answer_key=f"a{index}",
    )  # fmt: skip


def _pool() -> list[SourceRow]:
    rows = [_row(i, QuestionFamily.FLOW_PATH, i % 3 != 0) for i in range(12)]
    x_family = SCOPE_X_FAMILIES[0]
    rows += [_row(100 + i, x_family, False) for i in range(8)]  # wrong by construction
    return rows


def test_scope_x_rows_are_left_out_of_the_pool() -> None:
    kept = audit_select.scope_r_rows(_pool())
    assert len(kept) == 12 and all(r.family is QuestionFamily.FLOW_PATH for r in kept)


def test_the_plan_holds_no_scope_x_row_even_when_the_budget_has_room_for_them() -> None:
    plan = audit_select.select_scope_r(_pool(), seed=1, call_usd=0.03, remaining_usd=100.0)
    assert plan.items and {i.row.family for i in plan.items} == {QuestionFamily.FLOW_PATH}
    assert plan.wrong_available == 4  # only R's wrong rows: 12 rows, every third one wrong


def test_a_pool_with_no_scope_r_row_is_refused() -> None:
    only_x = [_row(i, SCOPE_X_FAMILIES[0], False) for i in range(3)]
    with pytest.raises(ValueError, match="scope R rows"):
        audit_select.select_scope_r(only_x, seed=1, call_usd=0.03, remaining_usd=1.0)
