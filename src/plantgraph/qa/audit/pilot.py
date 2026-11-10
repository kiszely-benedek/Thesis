"""The pilot of gate G2 (review-fixes §5.3, step 1 of the budget order).

The pilot tests the judge on first-measurement rows whose truth is already known:

- every VALVES_ON_PATH agent row where the benchmark's count and the item-level count differ;
- every row whose numeric-list answer the old parser rejected (the F1 parser now reads them);
- 20 control rows that are right under any definition.

Each defect group must hold at least MIN_DEFECTS_PER_GROUP rows. The design note guessed 13 and 12;
the real first-measurement data holds 16 and about 9, so the pilot takes all of them.

G2 passes if the judge calls at least 80 % of the first two groups "correct" or
"ambiguous_question" and at least 80 % of the controls "correct". Which VALVES_ON_PATH rows
differ cannot be recomputed here (the first-measurement plants cannot be rebuilt by this code),
so the caller names their question ids; everything else is derived from the stored rows.
"""

from __future__ import annotations

from plantgraph.qa.audit.models import AuditItem, SourceRow
from plantgraph.qa.audit.select import dedupe, stratified_cut
from plantgraph.qa.audit.sources import LoadedRun, source_rows
from plantgraph.qa.final_answer import to_outcome
from plantgraph.qa.models import Outcome, QuestionFamily
from plantgraph.qa.scoring import score_answer

MIN_DEFECTS_PER_GROUP = 8
N_CONTROLS = 20


def parse_failure_candidates(run: LoadedRun) -> list[SourceRow]:
    """Stored parse failures the current parser reads as an answer the scorer calls correct.

    Only those are scorer defects: a re-read answer that is still wrong against the reference
    is a plain wrong answer, and would not test whether the judge catches a scorer error.
    """
    candidates = []
    for row in source_rows(run):
        result = run.results[(row.question_id, row.strategy)]
        raw_reply = result.trace.get("raw_reply")
        if row.outcome is not Outcome.PARSE_FAILURE or raw_reply is None:
            continue
        question = run.questions[row.question_id]
        outcome, final = to_outcome(str(raw_reply), question.answer_type)
        if outcome is Outcome.ANSWERED and score_answer(question, outcome, final).correct:
            candidates.append(row)
    return candidates


def _require_at_least(rows: list[SourceRow], what: str) -> None:
    if len(rows) < MIN_DEFECTS_PER_GROUP:
        raise ValueError(
            f"expected at least {MIN_DEFECTS_PER_GROUP} {what} rows for the pilot, "
            f"found {len(rows)}"
        )


def _require_count(rows: list[SourceRow], expected: int, what: str) -> None:
    if len(rows) != expected:
        raise ValueError(f"expected {expected} {what} rows for the pilot, found {len(rows)}")


def build_pilot_set(
    pool: list[SourceRow],
    parse_failures: list[SourceRow],
    defect_valves_question_ids: set[str],
    seed: int,
) -> list[AuditItem]:
    """Every known defect row (valves, then parse) plus N_CONTROLS seeded controls.

    Raises:
        ValueError: a defect group has fewer than MIN_DEFECTS_PER_GROUP rows, or the
            controls cannot reach N_CONTROLS.
    """
    valves = dedupe(
        [
            row
            for row in pool
            if row.family is QuestionFamily.VALVES_ON_PATH
            and not row.scorer_correct
            and row.question_id in defect_valves_question_ids
        ]
    )
    parse = dedupe(parse_failures)
    _require_at_least(valves, "VALVES_ON_PATH defect")
    _require_at_least(parse, "parse-failure defect")
    used_questions = {row.question_id for row in valves + parse}
    controls = dedupe(
        [
            row
            for row in pool
            if row.scorer_correct
            and row.family is not QuestionFamily.VALVES_ON_PATH
            and row.question_id not in used_questions
        ]
    )
    chosen = stratified_cut(controls, N_CONTROLS, seed, "pilot_control")
    _require_count(chosen, N_CONTROLS, "control")
    return (
        [AuditItem(stratum="pilot_defect_valves", row=row) for row in valves]
        + [AuditItem(stratum="pilot_defect_parse", row=row) for row in parse]
        + [AuditItem(stratum="pilot_control", row=row) for row in chosen]
    )
