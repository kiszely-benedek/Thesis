"""The harness: questions x strategies x repeats -> `answers.jsonl` (`qa-system.md` §11).

One loop serves every mode. A **live** run (`--allow-paid-calls`) fills the
LLM cache as it goes; a **replay** run is the same code with a cache-only
client, so it reproduces a finished run's `answers.jsonl` byte for byte. A
**resume** is the same code again, skipping rows already on disk.

Order is corpus, then strategy, then question, then repeat, sequentially.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx2

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ChatRequest, ChatResponse, ProviderError
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.corpus_record import build_corpus_record
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory, open_checked_neo4j_view
from plantgraph.qa.harness.freeze import check_reportable, prompt_hashes, question_set_sha256
from plantgraph.qa.harness.gold import (
    ROUTING_HIT_TRACE_KEY,
    GoldScoring,
    build_gold_scoring,
    routing_hit,
)
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.registry import CypherDeps, build_strategy
from plantgraph.qa.harness.run_dir import RowKey, RunDir, row_key
from plantgraph.qa.harness.summary import RunSummary, summarize_rows
from plantgraph.qa.models import CorpusRecord, Outcome, Question, QuestionResult, RunConfig
from plantgraph.qa.scoring import score_answer
from plantgraph.qa.strategies.base import Strategy, answer_question
from plantgraph.qa.strategies.cypher_rag import CypherRag

ProgressSink = Callable[[str], None]


@dataclass(frozen=True)
class _Corpus:
    """One corpus's view for the strategies and its gold scoring inputs for the harness."""

    view: NetworkxGraphView
    gold: GoldScoring
    record: CorpusRecord
    #: The checked database for CypherRAG; `None` when the run does not include it.
    cypher: CypherSource | None


@dataclass(frozen=True)
class _WorkItem:
    strategy: Strategy
    question: Question
    repeat: int


def run_harness(
    *,
    config: RunConfig,
    corpus_roles: dict[str, str],
    corpora_root: Path,
    questions_root: Path,
    runs_root: Path,
    cache_path: Path,
    http_client: httpx2.Client | None = None,
    cost_per_question_usd: float | None = None,
    progress: ProgressSink = print,
    cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view,
) -> RunSummary:
    """Run (or resume, or replay) the run `config` describes.

    Args:
        config: the run to start; on a resume, the stored config wins.
        corpus_roles: corpus id -> `"dev"` or `"test"`, for the corpus records.
        corpora_root: holds `<corpus_id>/ingest.json` for every corpus.
        questions_root: holds `<corpus_id>/questions.jsonl` for every corpus.
        runs_root: the run's directory is `runs_root/<run_id>`.
        cache_path: the LLM response cache (SQLite file).
        http_client: the HTTP layer; tests pass the fake transport here.
        cost_per_question_usd: the pilot's estimate, echoed before a paid run.
        progress: receives one-line status messages.
        cypher_source_factory: opens and checks the database for a run that
            includes CypherRAG; tests pass a stub, the default uses `NEO4J_*`.

    Raises:
        ValueError: a reported run with an incomplete config, inputs that no
            longer match the frozen hashes, or an unknown strategy name.
        StoreMismatch: CypherRAG is in the run and the database is not exactly
            the run's corpus (`neo4j_view.check_store`).
        CacheMiss: a replay run needs a response the cache does not hold.
    """
    check_reportable(config)  # before anything is read or written
    questions = _load_all_questions(config, questions_root)
    _check_inputs_match_config(config, questions_root)
    corpora = _load_corpora(config, corpus_roles, corpora_root, cypher_source_factory)
    run_dir = RunDir(runs_root / config.run_id)
    # The guard is this invocation's flag, never a stored one: a run started
    # with --allow-paid-calls and resumed without it must not call out.
    allow_paid_calls = config.allow_paid_calls
    config = run_dir.freeze(config)  # from here on, nothing may change the config
    run_dir.write_corpus_records([corpus.record for corpus in corpora.values()])

    client, cache = build_chat_client(
        pin=config.answer_pin,
        allow_paid_calls=allow_paid_calls,
        cache_path=cache_path,
        calls_log_path=run_dir.calls_path,
        http_client=http_client,
    )
    try:
        n_new_rows = _fill_answers(
            config,
            allow_paid_calls,
            questions,
            corpora,
            run_dir,
            client,
            cost_per_question_usd,
            progress,
        )
    finally:
        cache.close()
        _close_cypher_sources(corpora)
    return summarize_rows(config.run_id, run_dir.read_rows(), questions, n_new_rows)


def _load_all_questions(config: RunConfig, questions_root: Path) -> list[Question]:
    questions: list[Question] = []
    for corpus_id in config.corpora:
        questions.extend(load_questions(questions_path(questions_root, corpus_id), corpus_id))
    return questions


def _check_inputs_match_config(config: RunConfig, questions_root: Path) -> None:
    """The frozen hashes must describe the files about to be used."""
    files = [questions_path(questions_root, corpus_id) for corpus_id in config.corpora]
    if question_set_sha256(files) != config.question_set_sha256:
        raise ValueError(
            f"expected the question files {[str(f) for f in files]} to hash to the config's "
            f"question_set_sha256 {config.question_set_sha256!r}; they changed since freezing"
        )
    if prompt_hashes() != config.prompt_hashes:
        raise ValueError("expected the prompt templates to hash as in the config; they changed")


def _load_corpora(
    config: RunConfig,
    corpus_roles: dict[str, str],
    corpora_root: Path,
    cypher_source_factory: CypherSourceFactory,
) -> dict[str, _Corpus]:
    """Rebuild each corpus once: the view for strategies, gold for scoring, its record."""
    corpora: dict[str, _Corpus] = {}
    try:
        for corpus_id in config.corpora:
            corpora[corpus_id] = _load_corpus(
                config, corpus_id, corpus_roles, corpora_root, cypher_source_factory
            )
    except Exception:
        _close_cypher_sources(corpora)  # a later corpus failed its check: free the earlier ones
        raise
    return corpora


def _load_corpus(
    config: RunConfig,
    corpus_id: str,
    corpus_roles: dict[str, str],
    corpora_root: Path,
    cypher_source_factory: CypherSourceFactory,
) -> _Corpus:
    ingest_path = corpora_root / corpus_id / "ingest.json"
    artifacts = load_corpus_artifacts(corpus_id, ingest_path)
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(f"expected a ground-truth plant for {corpus_id!r}, found none")
    view = NetworkxGraphView(corpus_id, artifacts.localized_sheets, artifacts.resolution)
    # the pre-check: opened and verified here, before the run is frozen or any call is made
    wants_cypher = CypherRag.name in config.strategies
    return _Corpus(
        view=view,
        gold=build_gold_scoring(plant, view),
        record=build_corpus_record(artifacts, ingest_path, corpus_roles[corpus_id]),
        cypher=cypher_source_factory(artifacts.load_plan) if wants_cypher else None,
    )


def _close_cypher_sources(corpora: dict[str, _Corpus]) -> None:
    for corpus in corpora.values():
        if corpus.cypher is not None:
            corpus.cypher.close()


def _fill_answers(
    config: RunConfig,
    allow_paid_calls: bool,
    questions: list[Question],
    corpora: dict[str, _Corpus],
    run_dir: RunDir,
    client: ChatClient,
    cost_per_question_usd: float | None,
    progress: ProgressSink,
) -> int:
    """Answer every row not yet on disk; return how many rows this call wrote."""
    dropped = run_dir.drop_provider_error_rows()
    done = {row_key(row) for row in run_dir.read_rows()}
    cypher_send = _cypher_sender(client, config)
    items = {
        corpus_id: list(
            _work_items(config, corpus_id, questions, corpora[corpus_id], done, cypher_send)
        )
        for corpus_id in config.corpora
    }
    n_pending = sum(len(corpus_items) for corpus_items in items.values())
    progress(f"run {config.run_id}: {n_pending} rows to answer, {len(done)} already on disk")
    if dropped:
        progress(f"re-queued {dropped} rows that ended in PROVIDER_ERROR last time")
    _announce_mode(allow_paid_calls, n_pending, cost_per_question_usd, progress)

    written = 0
    retry_later: list[tuple[str, _WorkItem]] = []
    for corpus_id, corpus_items in items.items():
        for item in corpus_items:
            outcome = _attempt(item, config, corpora[corpus_id], client)
            if isinstance(outcome, ProviderError):
                retry_later.append((corpus_id, item))
                continue
            run_dir.append_row(outcome)
            written += 1
    for corpus_id, item in retry_later:  # one more try each, then record the error
        outcome = _attempt(item, config, corpora[corpus_id], client)
        run_dir.append_row(
            _provider_error_row(item, config, outcome)
            if isinstance(outcome, ProviderError)
            else outcome
        )
        written += 1
    return written


def _announce_mode(
    allow_paid_calls: bool,
    n_pending: int,
    cost_per_question_usd: float | None,
    progress: ProgressSink,
) -> None:
    """Say before the first call whether this run can spend money, and roughly how much."""
    if not allow_paid_calls:
        progress("replay mode: cache only, no network; stops at the first cache miss")
        return
    progress(f"paid mode: up to {n_pending} model calls")
    if cost_per_question_usd is None:
        progress("no cost-per-question estimate given (the pilot has not provided one)")
    else:
        progress(f"estimated cost: {n_pending * cost_per_question_usd:.4f} USD")


def _work_items(
    config: RunConfig,
    corpus_id: str,
    questions: list[Question],
    corpus: _Corpus,
    done: set[RowKey],
    cypher_send: SendChatRequest,
) -> Iterator[_WorkItem]:
    """Strategy, then question, then repeat, skipping rows already on disk."""
    corpus_questions = [q for q in questions if q.corpus_id == corpus_id]
    cypher = (
        CypherDeps(corpus.cypher, config.answer_pin, cypher_send)
        if corpus.cypher is not None
        else None
    )
    for name, params in config.strategies.items():
        strategy = build_strategy(name, params, corpus.view, cypher)
        for question in corpus_questions:
            for repeat in range(config.repeats):
                if (question.question_id, name, repeat) not in done:
                    yield _WorkItem(strategy, question, repeat)


def _cypher_sender(client: ChatClient, config: RunConfig) -> SendChatRequest:
    """Sends CypherRAG's query-writing call through the run's client (cache, guard and log)."""

    def send(request: ChatRequest) -> ChatResponse:
        # retrieval sees only the question text, so the call is logged without a question id
        return client.complete(request, run_id=config.run_id, strategy=CypherRag.name)

    return send


def _attempt(
    item: _WorkItem, config: RunConfig, corpus: _Corpus, client: ChatClient
) -> QuestionResult | ProviderError:
    """Answer one item; a provider error that outlived the transport retries is returned."""

    def send(request: ChatRequest) -> ChatResponse:
        return client.complete(
            request,
            run_id=config.run_id,
            question_id=item.question.question_id,
            strategy=item.strategy.name,
        )

    try:
        step = answer_question(
            item.strategy,
            item.question,
            pin=config.answer_pin,
            wall=config.context_wall,
            send=send,
        )
    except ProviderError as error:
        return error
    scored = score_answer(
        item.question,
        step.outcome,
        step.final_answer,
        connector_tags=corpus.gold.connector_tags,
        valid_edges=corpus.gold.valid_edges,
    )
    trace = dict(step.trace)
    hit = routing_hit(item.question, trace)
    if hit is not None:
        trace[ROUTING_HIT_TRACE_KEY] = hit
    response = step.response
    return QuestionResult(
        run_id=config.run_id,
        question_id=item.question.question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        outcome=step.outcome,
        final_answer=step.final_answer,
        correct=scored.correct,
        f1=scored.f1,
        prompt_tokens=response.prompt_tokens if response else 0,
        completion_tokens=response.completion_tokens if response else 0,
        cost_usd=response.cost_usd if response else None,
        latency_s=response.latency_s if response else 0.0,
        # 0 when retrieval failed before any prompt was built
        context_chars=int(trace.get("prompt_chars", 0)),
        trace=trace,
    )


def _provider_error_row(item: _WorkItem, config: RunConfig, error: ProviderError) -> QuestionResult:
    return QuestionResult(
        run_id=config.run_id,
        question_id=item.question.question_id,
        strategy=item.strategy.name,
        repeat=item.repeat,
        outcome=Outcome.PROVIDER_ERROR,
        final_answer=None,
        correct=False,
        f1=None,
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        latency_s=0.0,
        context_chars=0,
        trace={"provider_error": str(error)},
    )
