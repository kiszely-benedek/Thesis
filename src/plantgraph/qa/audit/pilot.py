"""The pilot of gate G2 (review-fixes §5.3, step 1 of the budget order).

The pilot tests the judge on first-measurement rows whose truth is already known:

- every VALVES_ON_PATH agent row the scorer called wrong although the system gave an item-level
  count (the benchmark's own count was taken along another route);
- every row whose numeric-list answer the old parser rejected (the F1 parser now reads them);
- 20 control rows that are right under any definition.

Each defect group must hold at least MIN_DEFECTS_PER_GROUP rows. The design note guessed 13 and 12;
the real first-measurement data holds 16 and about 9, so the pilot takes all of them.

G2 passes if the judge calls at least 80 % of the first two groups "correct" or
"ambiguous_question" and at least 80 % of the controls "correct". The item-level counts cannot
be recomputed here (the first-measurement plants cannot be rebuilt by this code), so the caller
gives them per question id; everything else is derived from the stored rows.

A row of such a question is a defect only if the system's count is one of the item-level counts.
The first pilot (2026-11-11) took every wrong row of the named questions, and 5 of its 21 rows
were plain wrong answers ("not present", or a count on no route), which no judge should accept.
"""

from __future__ import annotations

import json

from plantgraph.qa.audit.models import AuditItem, SourceRow
from plantgraph.qa.audit.select import dedupe, stratified_cut
from plantgraph.qa.audit.sources import LoadedRun, source_rows
from plantgraph.qa.final_answer import to_outcome
from plantgraph.qa.models import Outcome, QuestionFamily
from plantgraph.qa.scoring import score_answer

MIN_DEFECTS_PER_GROUP = 8
N_CONTROLS = 20


def parse_valve_counts(text: str) -> dict[str, frozenset[int]]:
    """Question id -> its item-level valve counts, from lines `<question id> <count>[,<count>]`.

    Raises:
        ValueError: a line is not an id followed by whole numbers.
    """
    counts: dict[str, frozenset[int]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not all(c.isdigit() for c in parts[1].split(",")):
            raise ValueError(f"expected '<question id> <count>[,<count>]', got {line!r}")
        counts[parts[0]] = frozenset(int(c) for c in parts[1].split(","))
    return counts


def _answered_count(row: SourceRow) -> int | None:
    """The whole number the system answered; `None` for "not present" or an unparsed reply."""
    if row.answer_key.startswith("raw:"):
        return None
    key = json.loads(row.answer_key)
    answer = key["answer"]
    is_count = isinstance(answer, int) and not isinstance(answer, bool) and not key["not_present"]
    return answer if is_count else None


def _is_valves_defect(row: SourceRow, item_counts: dict[str, frozenset[int]]) -> bool:
    """A VALVES_ON_PATH row the scorer called wrong although its count is an item-level one."""
    if row.family is not QuestionFamily.VALVES_ON_PATH or row.scorer_correct:
        return False
    return _answered_count(row) in item_counts.get(row.question_id, frozenset())


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
    valves_item_counts: dict[str, frozenset[int]],
    seed: int,
) -> list[AuditItem]:
    """Every known defect row (valves, then parse) plus N_CONTROLS seeded controls.

    Args:
        pool: every judgeable row of the pilot's runs.
        parse_failures: the rows `parse_failure_candidates` found.
        valves_item_counts: per VALVES_ON_PATH question id, its item-level valve counts.
        seed: seed of the control draw.

    Raises:
        ValueError: a defect group has fewer than MIN_DEFECTS_PER_GROUP rows, or the
            controls cannot reach N_CONTROLS.
    """
    valves = dedupe([row for row in pool if _is_valves_defect(row, valves_item_counts)])
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
