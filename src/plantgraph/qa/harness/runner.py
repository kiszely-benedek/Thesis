"""The harness: questions x strategies x repeats -> `answers.jsonl` (`qa-system.md` §11).

One loop serves every mode. A **live** run (`--allow-paid-calls`) fills the
LLM cache as it goes; a **replay** run is the same code with a cache-only
client, so it reproduces a finished run's `answers.jsonl` byte for byte. A
**resume** is the same code again, skipping rows already on disk.

Order is corpus, then strategy, then question, then repeat. `concurrency` > 1
answers several items at once but writes the rows in that same order (`fill.py`).
"""

from __future__ import annotations

from pathlib import Path

import httpx2

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.attempt import LoadedCorpus
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.corpus_record import build_corpus_record
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory, open_checked_neo4j_view
from plantgraph.qa.harness.fill import Invocation, ProgressSink, fill_answers
from plantgraph.qa.harness.freeze import check_reportable, prompt_hashes, question_set_sha256
from plantgraph.qa.harness.gold import build_gold_scoring
from plantgraph.qa.harness.pool import MAX_CONCURRENCY
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.routing_gold import build_routing_gold
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.summary import RunSummary, summarize_rows
from plantgraph.qa.models import Question, RunConfig
from plantgraph.qa.strategies.cypher_rag import CypherRag


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
    concurrency: int = 1,
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
        concurrency: items answered at once (1 to 8); rows are still written in order.
        progress: receives one-line status messages.
        cypher_source_factory: opens and checks the database for a run that
            includes CypherRAG; tests pass a stub, the default uses `NEO4J_*`.

    Raises:
        ValueError: a concurrency outside 1 to 8, a paid run with more than one worker and
            no cost-per-question estimate, a reported run with an incomplete config, inputs that no
            longer match the frozen hashes, or an unknown strategy name.
        StoreMismatch: CypherRAG is in the run and the database is not exactly
            the run's corpus (`neo4j_view.check_store`).
        CacheMiss: a replay run needs a response the cache does not hold.
    """
    check_reportable(config)  # before anything is read or written
    _require_cap_for_paid_run(config)
    _check_concurrency(config, concurrency, cost_per_question_usd)
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
        n_new_rows, stopped_by_cap = fill_answers(
            config,
            Invocation(allow_paid_calls, max_spend_usd, cost_per_question_usd, concurrency),
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


def _check_concurrency(
    config: RunConfig, concurrency: int, cost_per_question_usd: float | None
) -> None:
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"expected --concurrency from 1 to {MAX_CONCURRENCY}, found {concurrency}")
    if concurrency > 1 and config.allow_paid_calls and cost_per_question_usd is None:
        raise ValueError(
            "expected --cost-per-question-usd together with --concurrency > 1 on a paid run "
            "(the spend cap reserves that much for each item in flight); found none, so "
            "nothing was started"
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
