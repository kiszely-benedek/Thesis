"""Report-only diagnostics of a policy's answers, borrowed from arXiv 2609.05880.

These read gold (`correct`, the reference answer), so they live on the evaluation side: no
policy decision ever sees them. One check needs data the runs do not record and is skipped:
the share of wrong answers that cite evidence (an answer is only `{answer, not_present}`).
The "named tag was touched" test needs the corpus item graph (a step records plant-item keys,
not tags), so it runs only when the graph is given; without it, see "no plant item touched".
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from plantgraph.demo.app.evidence import tags_in_text
from plantgraph.qa.cascade.corpus_checks import control_valve_tags, isolation_scores
from plantgraph.qa.cascade.evaluate import Evaluation
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.report_models import AgentDiagnostics, Cell, PolicyDiagnostics
from plantgraph.qa.models import AnswerType, Outcome, Question, QuestionResult
from plantgraph.qa.plant_api.item_graph import ItemGraph

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


def _touched_item_ids(row: QuestionResult, graph: ItemGraph) -> set[str]:
    """Items whose drawings any step of the row touched (a stub that vanishes maps to none)."""
    keys = {key for step in _agent_steps(row) or [] for key in step.get("touched_keys") or []}
    return {item_id for key in keys if (item_id := graph.item_of_key(key)) is not None}


def _leaves_named_tag_untouched(question: Question, row: QuestionResult, graph: ItemGraph) -> bool:
    """True when a plant tag the question text names was never touched by the agent's steps."""
    touched = _touched_item_ids(row, graph)
    named = tags_in_text(question.text, graph)
    return any(touched.isdisjoint(graph.ids_for_tag(tag)) for tag in named)


def _named_tag_cells(
    tried: list[QuestionResult], questions: Mapping[str, Question], graph: ItemGraph
) -> tuple[Cell, int]:
    """(never-touched cell, number of tried questions that name a plant tag), over agent rows."""
    with_steps = [r for r in tried if _agent_steps(r) is not None]
    with_tags = [r for r in with_steps if tags_in_text(questions[r.question_id].text, graph)]
    untouched = [
        r for r in with_tags if _leaves_named_tag_untouched(questions[r.question_id], r, graph)
    ]
    return _cell(untouched), len(with_tags)


def agent_diagnostics(
    joined: JoinedCorpus,
    evaluation: Evaluation,
    questions: Mapping[str, Question],
    graph: ItemGraph | None = None,
) -> AgentDiagnostics | None:
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
    named_cell, n_named = (None, 0) if graph is None else _named_tag_cells(tried, questions, graph)
    return AgentDiagnostics(
        tier=tier.name,
        n_tried=len(tried),
        stop_reasons=dict(Counter(_stop_reason(r) for r in tried)),
        answered_without_tool_call=_cell(no_tool_call),
        answered_touching_no_item=_cell(no_item),
        named_tag_never_touched=named_cell,
        n_with_named_tags=n_named,
    )


def policy_diagnostics(
    joined: JoinedCorpus,
    evaluation: Evaluation,
    questions: Mapping[str, Question],
    graph: ItemGraph | None = None,
) -> PolicyDiagnostics:
    """The made-up-yes count on gold-"no" BOOLEAN questions, plus the agent tier's checks.

    `graph` (the corpus item graph) adds the named-tag check (D1) and the isolation score (U4).
    """
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
        agent=agent_diagnostics(joined, evaluation, questions, graph),
        isolation=None
        if graph is None
        else isolation_scores(joined, evaluation, questions, control_valve_tags(graph)),
    )
