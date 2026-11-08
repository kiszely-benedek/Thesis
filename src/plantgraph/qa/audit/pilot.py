"""The 45-row pilot of gate G2 (review-fixes §5.3, step 1 of the budget order).

The pilot tests the judge on first-measurement rows whose truth is already known:

- 13 VALVES_ON_PATH agent rows where the benchmark's count and the item-level count differ;
- 12 rows whose numeric-list answer the old parser rejected (the F1 parser now reads them);
- 20 control rows that are right under any definition.

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

N_VALVES = 13
N_PARSE = 12
N_CONTROLS = 20


def parse_failure_candidates(run: LoadedRun) -> list[SourceRow]:
    """Stored parse failures whose raw reply the current parser reads as an answer."""
    candidates = []
    for row in source_rows(run):
        result = run.results[(row.question_id, row.strategy)]
        raw_reply = result.trace.get("raw_reply")
        if row.outcome is not Outcome.PARSE_FAILURE or raw_reply is None:
            continue
        answer_type = run.questions[row.question_id].answer_type
        if to_outcome(str(raw_reply), answer_type)[0] is Outcome.ANSWERED:
            candidates.append(row)
    return candidates


def _require_count(rows: list[SourceRow], expected: int, what: str) -> None:
    if len(rows) != expected:
        raise ValueError(f"expected {expected} {what} rows for the pilot, found {len(rows)}")


def build_pilot_set(
    pool: list[SourceRow],
    parse_failures: list[SourceRow],
    defect_valves_question_ids: set[str],
    seed: int,
) -> list[AuditItem]:
    """The 45 pilot rows: valves defects, parse defects, then seeded controls.

    Raises:
        ValueError: a group does not hold exactly its registered number of rows.
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
    _require_count(valves, N_VALVES, "VALVES_ON_PATH defect")
    _require_count(parse, N_PARSE, "parse-failure defect")
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
