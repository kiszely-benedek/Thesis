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
from plantgraph.llm.models import ProviderError
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.attempt import (
    Answered,
    LoadedCorpus,
    WorkItem,
    attempt,
    provider_error_row,
    sender_factory,
)
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.corpus_record import build_corpus_record
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory, open_checked_neo4j_view
from plantgraph.qa.harness.freeze import check_reportable, prompt_hashes, question_set_sha256
from plantgraph.qa.harness.gold import build_gold_scoring
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.registry import CypherDeps, LlmDeps, build_strategy
from plantgraph.qa.harness.routing_gold import build_routing_gold
from plantgraph.qa.harness.run_dir import RowKey, RunDir, row_key
from plantgraph.qa.harness.spend_cap import SpendCapReached, SpendGuard
from plantgraph.qa.harness.summary import RunSummary, summarize_rows
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.models import Question, QuestionResult, RunConfig
from plantgraph.qa.strategies.cypher_rag import CypherRag

ProgressSink = Callable[[str], None]


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
    _require_cap_for_paid_run(config)
    questions = _load_all_questions(config, questions_root)
    _check_inputs_match_config(config, questions_root)
    corpora = _load_corpora(config, corpus_roles, corpora_root, cypher_source_factory)
    run_dir = RunDir(runs_root / config.run_id)
    # The guard is this invocation's flag, never a stored one: a run started
    # with --allow-paid-calls and resumed without it must not call out.
    allow_paid_calls = config.allow_paid_calls
    max_spend_usd = config.max_spend_usd  # likewise: a resume may raise the cap
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
        n_new_rows, stopped_by_cap = _fill_answers(
            config,
            _Invocation(allow_paid_calls, max_spend_usd, cost_per_question_usd),
            questions,
            corpora,
            run_dir,
            client,
            progress,
        )
    finally:
        cache.close()
        _close_cypher_sources(corpora)
    return summarize_rows(
        config.run_id,
        run_dir.read_rows(),
        questions,
        n_new_rows,
        stopped_by_spend_cap=stopped_by_cap,
    )


def _require_cap_for_paid_run(config: RunConfig) -> None:
    if config.allow_paid_calls and config.max_spend_usd is None:
        raise ValueError(
            "expected --max-spend-usd together with --allow-paid-calls (a paid run needs a "
            "hard spend cap); found none, so nothing was started"
        )


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
) -> dict[str, LoadedCorpus]:
    """Rebuild each corpus once: the view for strategies, gold for scoring, its record."""
    corpora: dict[str, LoadedCorpus] = {}
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
) -> LoadedCorpus:
    ingest_path = corpora_root / corpus_id / "ingest.json"
    artifacts = load_corpus_artifacts(corpus_id, ingest_path)
    plant = artifacts.gold.plant
    if plant is None:
        raise ValueError(f"expected a ground-truth plant for {corpus_id!r}, found none")
    manifest = artifacts.gold.manifest
    if manifest is None:
        raise ValueError(f"expected a split manifest for {corpus_id!r}, found none")
    view = NetworkxGraphView(corpus_id, artifacts.localized_sheets, artifacts.resolution)
    # the pre-check: opened and verified here, before the run is frozen or any call is made
    wants_cypher = CypherRag.name in config.strategies
    return LoadedCorpus(
        view=view,
        gold=build_gold_scoring(plant, view),
        routing_gold=build_routing_gold(
            plant, artifacts.gold.sheets, manifest, artifacts.gold.occurrence_map
        ),
        record=build_corpus_record(artifacts, ingest_path, corpus_roles[corpus_id]),
        cypher=cypher_source_factory(artifacts.load_plan) if wants_cypher else None,
    )


def _close_cypher_sources(corpora: dict[str, LoadedCorpus]) -> None:
    for corpus in corpora.values():
        if corpus.cypher is not None:
            corpus.cypher.close()


@dataclass(frozen=True)
class _Invocation:
    """Settings of this call that a resume may change; the frozen config does not decide them."""

    allow_paid_calls: bool
    max_spend_usd: float | None
    cost_per_question_usd: float | None


def _fill_answers(
    config: RunConfig,
    invocation: _Invocation,
    questions: list[Question],
    corpora: dict[str, LoadedCorpus],
    run_dir: RunDir,
    client: ChatClient,
    progress: ProgressSink,
) -> tuple[int, bool]:
    """Answer every row not yet on disk.

    Returns:
        How many rows this call wrote, and whether the spend cap stopped it early.
    """
    dropped = run_dir.drop_provider_error_rows()
    rows_on_disk = run_dir.read_rows()
    done = {row_key(row) for row in rows_on_disk}
    guard = _spend_guard(invocation, rows_on_disk)
    meter = UsageMeter(guard)
    sender_for = sender_factory(client, config, meter)
    items = {
        corpus_id: list(
            _work_items(config, corpus_id, questions, corpora[corpus_id], done, sender_for)
        )
        for corpus_id in config.corpora
    }
    n_pending = sum(len(corpus_items) for corpus_items in items.values())
    progress(f"run {config.run_id}: {n_pending} rows to answer, {len(done)} already on disk")
    if dropped:
        progress(f"re-queued {dropped} rows that ended in PROVIDER_ERROR last time")
    _announce_mode(invocation, n_pending, progress)

    written = 0
    retry_later: list[tuple[str, WorkItem]] = []
    try:
        for corpus_id, corpus_items in items.items():
            for item in corpus_items:
                guard.check_before_question()
                outcome = attempt(item, config, corpora[corpus_id], client, meter)
                if isinstance(outcome, ProviderError):
                    retry_later.append((corpus_id, item))
                    continue
                _record(run_dir, guard, outcome)
                written += 1
        for corpus_id, item in retry_later:  # one more try each, then record the error
            guard.check_before_question()
            outcome = attempt(item, config, corpora[corpus_id], client, meter)
            if isinstance(outcome, ProviderError):
                run_dir.append_row(provider_error_row(item, config, outcome))
            else:
                _record(run_dir, guard, outcome)
            written += 1
    except SpendCapReached as stop:
        # rows are appended whole and the cache keeps this question's calls, so a resume is clean
        progress(f"STOPPED by the spend cap: {stop}. Rerun with the same --run-id to resume.")
        return written, True
    return written, False


def _spend_guard(invocation: _Invocation, rows_on_disk: list[QuestionResult]) -> SpendGuard:
    """Seed the guard with what earlier invocations recorded as their total cost."""
    totals = [row.total_cost_usd or 0.0 for row in rows_on_disk]
    return SpendGuard(
        invocation.max_spend_usd if invocation.allow_paid_calls else None,
        recorded_usd=sum(totals),
        max_question_usd=max(totals, default=0.0),
        estimate_usd=invocation.cost_per_question_usd,
    )


def _record(run_dir: RunDir, guard: SpendGuard, answered: Answered) -> None:
    run_dir.append_row(answered.row)
    run_dir.append_timing(answered.timing)
    guard.end_question(answered.timing.spent_usd)


def _announce_mode(invocation: _Invocation, n_pending: int, progress: ProgressSink) -> None:
    """Say before the first call whether this run can spend money, and roughly how much."""
    if not invocation.allow_paid_calls:
        progress("replay mode: cache only, no network; stops at the first cache miss")
        return
    progress(
        f"paid mode: up to {n_pending} model calls; hard spend cap {invocation.max_spend_usd} USD"
    )
    cost_per_question_usd = invocation.cost_per_question_usd
    if cost_per_question_usd is None:
        progress("no cost-per-question estimate given (the pilot has not provided one)")
    else:
        progress(f"estimated cost: {n_pending * cost_per_question_usd:.4f} USD")


def _work_items(
    config: RunConfig,
    corpus_id: str,
    questions: list[Question],
    corpus: LoadedCorpus,
    done: set[RowKey],
    sender_for: Callable[[str], SendChatRequest],
) -> Iterator[WorkItem]:
    """Strategy, then question, then repeat, skipping rows already on disk."""
    corpus_questions = [q for q in questions if q.corpus_id == corpus_id]
    cypher = (
        CypherDeps(corpus.cypher, config.answer_pin, sender_for(CypherRag.name))
        if corpus.cypher is not None
        else None
    )
    for name, params in config.strategies.items():
        llm = LlmDeps(config.answer_pin, sender_for(name))
        strategy = build_strategy(name, params, corpus.view, cypher, llm)
        for question in corpus_questions:
            for repeat in range(config.repeats):
                if (question.question_id, name, repeat) not in done:
                    yield WorkItem(strategy, question, repeat)
