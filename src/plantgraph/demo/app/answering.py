"""From a request to the answer shown: pick the question, add the sheets and the benchmark facts.

The cascade gets only the question text and answer shape. Gold (reference answer, evidence
sheets, k) is read here, after the answer exists, and is only displayed and scored.
"""

from __future__ import annotations

from plantgraph.demo.app.api_models import AskRequest, BenchmarkView, DemoAnswer
from plantgraph.demo.app.corpus_runtime import LoadedCorpus
from plantgraph.demo.app.evidence import answer_sheet_links, read_sheet_links
from plantgraph.qa.cascade.live_models import FreeTextQuestion, LiveAnswer
from plantgraph.qa.models import Outcome, Question
from plantgraph.qa.scoring import score_answer
from plantgraph.qa.strategies.base import AskedQuestion


class UnknownBenchmarkQuestion(LookupError):
    """The request names a benchmark question the corpus does not have."""


def asked_question(corpus: LoadedCorpus, request: AskRequest) -> AskedQuestion:
    """The question to run: the benchmark question itself, or the typed text.

    Raises:
        UnknownBenchmarkQuestion: the benchmark id is not in the corpus.
    """
    if request.benchmark_question_id is None:
        return FreeTextQuestion.from_text(request.text.strip(), request.answer_type)
    return benchmark_question(corpus, request.benchmark_question_id)


def benchmark_question(corpus: LoadedCorpus, question_id: str) -> Question:
    """The corpus's benchmark question with this id.

    Raises:
        UnknownBenchmarkQuestion: no such question.
    """
    question = corpus.questions.get(question_id)
    if question is None:
        raise UnknownBenchmarkQuestion(
            f"expected a benchmark question of {corpus.config.corpus_id}, found {question_id!r}"
        )
    return question


def benchmark_view(
    corpus: LoadedCorpus, question: Question, correct: bool | None = None
) -> BenchmarkView:
    """The question's reference and gold sheets (as pages), k and the recorded answers."""
    return BenchmarkView(
        question_id=question.question_id,
        family=question.family,
        text=question.text,
        answer_type=question.answer_type,
        answerable=question.answerable,
        reference=question.reference,
        gold_sheets=read_sheet_links(question.evidence_sheets, corpus.pages),
        k=question.k,
        k_connector=question.k_connector,
        k_identity=question.k_identity,
        u=question.u,
        correct=correct,
        recorded=corpus.recorded.get(question.question_id, ()),
    )


def demo_answer(corpus: LoadedCorpus, live: LiveAnswer, asked: AskedQuestion) -> DemoAnswer:
    """The live answer with its sheets and, for a benchmark question, the verdict."""
    return DemoAnswer(
        live=live,
        answer_sheets=answer_sheet_links(
            live.question_text, live.answer_type, live.final_answer, corpus.item_graph, corpus.pages
        ),
        read_sheets=read_sheet_links(live.trace_sheets, corpus.pages),
        benchmark=_benchmark_for(corpus, live, asked),
    )


def _benchmark_for(
    corpus: LoadedCorpus, live: LiveAnswer, asked: AskedQuestion
) -> BenchmarkView | None:
    if not isinstance(asked, Question):
        return None
    return benchmark_view(corpus, asked, correct=_is_correct(corpus, live, asked))


def _is_correct(corpus: LoadedCorpus, live: LiveAnswer, question: Question) -> bool:
    """Score the live answer as the experiments score a row; a late answer is wrong."""
    if live.outcome is not Outcome.ANSWERED:
        return False
    return score_answer(
        question,
        live.outcome,
        live.final_answer,
        connector_tags=corpus.gold.connector_tags,
        valid_edges=corpus.gold.valid_edges,
    ).correct
