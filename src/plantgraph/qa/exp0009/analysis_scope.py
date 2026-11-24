"""Which questions each claim counts: scope R, scope X, and how A2 and B rows are paired.

**Scope R** is the question set of EXP-0008 on a v2.2 plant, the five X families left out. Its
claims count what EXP-0008's `headline` scope counted: the three headline splits, with the
family LOOP_ACTUATED_VALVE left out (ADR-0044 U2). **Scope X** is the five extension families.
Its **isolation** families (which valves to close) are asked of both arms; POSITION_OF_VALVE only
of B.

A2 reads `questions/<A id>/`, B reads `questions/<A id>B/`. The two files hold the same R and X
isolation questions under ids that differ by the corpus prefix only, so a pair is found by the id
with that prefix cut off.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from plantgraph.qa.cascade.report_claims import HEADLINE_EXCLUDED_FAMILY, HEADLINE_SPLITS
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.scope_x import SCOPE_X_FAMILIES

X_FAMILIES: frozenset[QuestionFamily] = frozenset(SCOPE_X_FAMILIES)
X_ISOLATION_FAMILIES: frozenset[QuestionFamily] = X_FAMILIES - {QuestionFamily.POSITION_OF_VALVE}


def stripped_id(question_id: str) -> str:
    """The id without its corpus prefix: `H100g22p1B:FLOW_PATH:3` -> `FLOW_PATH:3`.

    Raises:
        ValueError: the id has no `corpus:` prefix.
    """
    prefix, colon, rest = question_id.partition(":")
    if not colon or not prefix or not rest:
        raise ValueError(f"expected a question id like '<corpus>:<rest>', found {question_id!r}")
    return rest


def r_headline_ids(questions: Sequence[Question], splits: Mapping[str, str]) -> frozenset[str]:
    """Scope R as the claims count it: no X family, a headline split, not the excluded family."""
    return frozenset(
        q.question_id
        for q in questions
        if q.family not in X_FAMILIES
        and q.family is not HEADLINE_EXCLUDED_FAMILY
        and splits.get(q.question_id) in HEADLINE_SPLITS
    )


def x_ids(
    questions: Sequence[Question], families: frozenset[QuestionFamily] = X_FAMILIES
) -> frozenset[str]:
    """The questions of the given X families (all five by default)."""
    return frozenset(q.question_id for q in questions if q.family in families)


def stripped(ids: frozenset[str]) -> frozenset[str]:
    """Every id of `ids` without its corpus prefix."""
    return frozenset(stripped_id(qid) for qid in ids)
