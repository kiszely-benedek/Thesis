"""Small in-memory runs, questions and subgraphs for the scorer-audit tests (F14)."""

from __future__ import annotations

from plantgraph.qa.audit.excerpt import QuestionSubgraph, SubgraphEdge, SubgraphNode
from plantgraph.qa.audit.models import SourceRow
from plantgraph.qa.audit.sources import LoadedRun, answer_key, scale_of
from plantgraph.qa.models import (
    AnswerType,
    FinalAnswer,
    Outcome,
    Question,
    QuestionFamily,
    QuestionResult,
)

CORPUS = "H100g21p1"


def make_question(
    number: int,
    family: QuestionFamily = QuestionFamily.LOOKUP_TYPE,
    corpus_id: str = CORPUS,
    answer_type: AnswerType = AnswerType.CLASS_NAME,
) -> Question:
    return Question(
        question_id=f"{corpus_id}:{family.value}:{number}",
        corpus_id=corpus_id,
        family=family,
        template_id="t",
        template_version="1",
        text=f"What is part number {number}?",
        answer_type=answer_type,
        answerable=True,
        reference="Pump",
        generator_seed=0,
    )


def make_result(
    question: Question,
    *,
    strategy: str = "agent",
    correct: bool = True,
    answer: str | None = "Pump",
    outcome: Outcome = Outcome.ANSWERED,
    raw_reply: str | None = None,
) -> QuestionResult:
    final = FinalAnswer(answer=answer, not_present=False) if outcome is Outcome.ANSWERED else None
    trace = {} if raw_reply is None else {"raw_reply": raw_reply}
    return QuestionResult(
        run_id="run-a",
        question_id=question.question_id,
        strategy=strategy,
        repeat=0,
        outcome=outcome,
        final_answer=final,
        correct=correct,
        f1=None,
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=0.0,
        latency_s=1.0,
        context_chars=10,
        trace=trace,
    )


def make_run(run_id: str, pairs: list[tuple[Question, QuestionResult]]) -> LoadedRun:
    results = {
        (q.question_id, r.strategy): r.model_copy(update={"run_id": run_id}) for q, r in pairs
    }
    return LoadedRun(run_id, results, {q.question_id: q for q, _ in pairs})


def make_source_row(
    number: int,
    *,
    family: QuestionFamily = QuestionFamily.LOOKUP_TYPE,
    correct: bool = True,
    scale_corpus: str = CORPUS,
    run_id: str = "run-a",
    strategy: str = "agent",
    answer: str = "Pump",
) -> SourceRow:
    question = make_question(number, family, scale_corpus)
    result = make_result(question, strategy=strategy, correct=correct, answer=answer)
    return SourceRow(
        run_id=run_id,
        strategy=strategy,
        question_id=question.question_id,
        corpus_id=scale_corpus,
        family=family,
        scale=scale_of(scale_corpus),
        outcome=Outcome.ANSWERED,
        scorer_correct=correct,
        answer_key=answer_key(result, question.answer_type),
    )


def make_subgraph(question_id: str) -> QuestionSubgraph:
    """P-1 -> tee -> reducer -> V-1 -> TK-9 (the tank is one hop beyond the evidence)."""
    nodes = [
        SubgraphNode(id="a", node_class="Pump", tag="P-1", unit_id="1", distance=0),
        SubgraphNode(id="b", node_class="PipeTee", distance=0),
        SubgraphNode(id="c", node_class="PipeReducer", distance=0),
        SubgraphNode(id="d", node_class="Valve", tag="V-1", unit_id="1", distance=0),
        SubgraphNode(id="e", node_class="Tank", tag="TK-9", distance=1),
    ]
    flow = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
    edges = [
        SubgraphEdge(source=s, target=t, relation="send_to", properties={"line_number": "L1"})
        for s, t in flow
    ]
    return QuestionSubgraph(
        question_id=question_id,
        corpus_id=CORPUS,
        evidence_ids=["a", "d"],
        nodes=nodes,
        edges=edges,
    )
