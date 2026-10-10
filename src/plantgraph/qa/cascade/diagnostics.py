"""Report-only diagnostics of a policy's answers, borrowed from arXiv 2609.05880.

These read gold (`correct`, the reference answer), so they live on the evaluation side: no
policy decision ever sees them. Two checks need data the runs do not record and are skipped:
a "named tag was touched" test (a step records plant-item keys, not tags, so the mapping needs
the graph) and the share of wrong answers that cite evidence (an answer is only `{answer,
not_present}`). In the first one's place: answers where no plant item was touched at all.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from plantgraph.qa.cascade.evaluate import Evaluation
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.report_models import AgentDiagnostics, Cell, PolicyDiagnostics
from plantgraph.qa.models import AnswerType, Outcome, Question, QuestionResult

AGENT_STRATEGIES = ("graph_agent", "graph_agent_low_steps", "hier_agent")
_YES_WORDS = ("yes", "true", "1")


def _agent_steps(row: QuestionResult) -> list[dict[str, Any]] | None:
    """The agent's recorded steps; `None` for a row that kept none (e.g. a cut-off row)."""
    retrieval = row.trace.get("retrieval")
    steps = retrieval.get("agent_steps") if isinstance(retrieval, dict) else None
    return steps if isinstance(steps, list) else None


def _stop_reason(row: QuestionResult) -> str:
    retrieval = row.trace.get("retrieval")
    reason = retrieval.get("stop_reason") if isinstance(retrieval, dict) else None
    if isinstance(reason, str):
        return reason
    return "timed_out" if row.outcome is Outcome.TIMED_OUT else "unrecorded"


def _says_yes(row: QuestionResult) -> bool:
    answer = row.final_answer.answer if row.final_answer is not None else None
    return row.outcome is Outcome.ANSWERED and str(answer).strip().lower() in _YES_WORDS


def _cell(rows: list[QuestionResult]) -> Cell:
    return Cell(correct=sum(r.correct for r in rows), total=len(rows))


def agent_diagnostics(joined: JoinedCorpus, evaluation: Evaluation) -> AgentDiagnostics | None:
    """Stop reasons and tool-use checks over the questions that tried the policy's agent tier."""
    tier = next((t for t in joined.policy.tiers if t.strategy in AGENT_STRATEGIES), None)
    if tier is None:
        return None
    tried = [
        joined.runs[tier.name].rows[s.decision.question_id]
        for s in evaluation.scored
        if tier.name in s.decision.tiers_tried
    ]
    answered = [r for r in tried if r.outcome is Outcome.ANSWERED and _agent_steps(r) is not None]
    no_tool_call = [r for r in answered if not any(s.get("tool") for s in _agent_steps(r) or [])]
    no_item = [r for r in answered if not any(s.get("touched_keys") for s in _agent_steps(r) or [])]
    return AgentDiagnostics(
        tier=tier.name,
        n_tried=len(tried),
        stop_reasons=dict(Counter(_stop_reason(r) for r in tried)),
        answered_without_tool_call=_cell(no_tool_call),
        answered_touching_no_item=_cell(no_item),
    )


def policy_diagnostics(
    joined: JoinedCorpus, evaluation: Evaluation, questions: Mapping[str, Question]
) -> PolicyDiagnostics:
    """The made-up-yes count on gold-"no" BOOLEAN questions, plus the agent tier's checks."""
    n_no = n_yes = 0
    for scored in evaluation.scored:
        decision = scored.decision
        question = questions[decision.question_id]
        if question.answer_type is not AnswerType.BOOLEAN or question.reference != "no":
            continue
        n_no += 1
        if decision.answered_by is not None:
            n_yes += _says_yes(joined.runs[decision.answered_by].rows[decision.question_id])
    return PolicyDiagnostics(
        policy=evaluation.summary.policy,
        boolean_no_questions=n_no,
        boolean_no_answered_yes=n_yes,
        agent=agent_diagnostics(joined, evaluation),
    )
