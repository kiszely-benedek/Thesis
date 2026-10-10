"""One corpus, loaded for the demo: item graph, drawing pages, questions and its cascades.

Loading rebuilds the plant from its ingest file (about 5 s for 100 sheets, 50 s for 1,000), so the
app does it in a background thread. Benchmark questions are held with their gold: the
app layer shows it, but the cascade is only ever handed the question text.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx2

from plantgraph.demo.app.api_models import RecordedAnswer
from plantgraph.demo.app.cascade_pool import CascadePool, CascadeSource, PoolSettings
from plantgraph.demo.app.config import DemoConfig, DemoCorpus
from plantgraph.demo.app.models import CostEstimate
from plantgraph.demo.drawing.models import DrawingIndex
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory, open_checked_neo4j_view
from plantgraph.qa.harness.gold import GoldScoring, build_gold_scoring
from plantgraph.qa.harness.question_set import load_questions
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.models import Question
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph


@dataclass
class LoadedCorpus:
    """Everything the app needs to answer questions about one corpus."""

    config: DemoCorpus
    item_graph: ItemGraph
    #: Sheet id -> 1-based page of the drawing PDF.
    pages: dict[str, int]
    questions: dict[str, Question]
    recorded: dict[str, tuple[RecordedAnswer, ...]]
    gold: GoldScoring
    estimate: CostEstimate
    source: CascadeSource


#: Turns a corpus entry of the config into a loaded corpus; tests pass their own.
CorpusLoadFn = Callable[[DemoCorpus], LoadedCorpus]


class CorpusLoader:
    """Loads corpora for one server run; holds what is shared between them."""

    def __init__(
        self,
        config: DemoConfig,
        policy: CascadePolicy,
        estimates: dict[str, CostEstimate],
        guard: SpendGuard,
        *,
        allow_paid_calls: bool,
        cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view,
        http_client: httpx2.Client | None = None,
    ) -> None:
        self._config = config
        self._policy = policy
        self._estimates = estimates
        self._guard = guard
        self._allow_paid_calls = allow_paid_calls
        self._factory = cypher_source_factory
        self._http_client = http_client

    def __call__(self, corpus: DemoCorpus) -> LoadedCorpus:
        """Rebuild the corpus and open its replay cascade.

        Raises:
            FileNotFoundError: the ingest file, the PDF index or the question file is missing.
            ValueError: benchmark questions are configured for a corpus with no answer key.
        """
        artifacts = load_corpus_artifacts(corpus.corpus_id, corpus.ingest_json)
        view = NetworkxGraphView(corpus.corpus_id, artifacts.localized_sheets, artifacts.resolution)
        questions = _read_questions(corpus)
        plant = artifacts.gold.plant
        if plant is None and questions:
            raise ValueError(
                f"expected an answer key (plant graph) for {corpus.corpus_id}, found none"
            )
        source = CascadePool(
            PoolSettings(
                corpus_id=corpus.corpus_id,
                policy=self._policy,
                view=view,
                load_plan=artifacts.load_plan,
                tier_run_dirs=corpus.tier_runs,
                cache_path=self._config.cache_path,
                calls_log_path=self._config.calls_log_path,
                cutoff_s=self._config.question_deadline_s,
                guard=self._guard,
                allow_paid_calls=self._allow_paid_calls,
                cypher_source_factory=self._factory,
                http_client=self._http_client,
            )
        )
        return LoadedCorpus(
            config=corpus,
            item_graph=build_item_graph(view),
            pages=_read_pages(corpus),
            questions={q.question_id: q for q in questions},
            recorded=_read_recorded(corpus.recorded_runs),
            gold=build_gold_scoring(plant, view)
            if plant is not None
            else GoldScoring(frozenset(), frozenset()),
            estimate=self._estimates[corpus.corpus_id],
            source=source,
        )


def read_drawing_index(corpus: DemoCorpus) -> DrawingIndex:
    """The drawing export's sidecar for the corpus.

    Raises:
        FileNotFoundError: the sidecar does not exist (the drawing was not exported).
    """
    if not corpus.index_path.exists():
        raise FileNotFoundError(
            f"expected {corpus.index_path} (run the drawing export first), found no such file"
        )
    return DrawingIndex.model_validate_json(corpus.index_path.read_text(encoding="utf-8"))


def _read_pages(corpus: DemoCorpus) -> dict[str, int]:
    return read_drawing_index(corpus).pages


def _read_questions(corpus: DemoCorpus) -> list[Question]:
    if corpus.questions_jsonl is None:
        return []
    return load_questions(corpus.questions_jsonl, corpus.corpus_id)


def _read_recorded(run_dirs: tuple[Path, ...]) -> dict[str, tuple[RecordedAnswer, ...]]:
    """Every row of the recorded runs, by question id."""
    by_question: dict[str, list[RecordedAnswer]] = defaultdict(list)
    for run_dir in run_dirs:
        for row in RunDir(run_dir).read_rows():
            by_question[row.question_id].append(
                RecordedAnswer(
                    run_id=row.run_id,
                    strategy=row.strategy,
                    outcome=row.outcome,
                    correct=row.correct,
                    answer=None if row.final_answer is None else row.final_answer.answer,
                    cost_usd=row.total_cost_usd,
                    latency_s=row.total_llm_latency_s,
                )
            )
    return {question_id: tuple(rows) for question_id, rows in by_question.items()}
