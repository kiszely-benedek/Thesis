"""The B harness entry: the B twin of `harness/runner.run_harness` (design §10 R6).

Same steps, in the same order, with the frozen checks, run directory, LLM client and summary. What
differs is what the run is built from: corpora loaded with their positions (`corpus_b.py`), `*_b`
strategies (`registry_b.py`) and the B final step and scorer (`attempt_b.py`, `fill_b.py`). No
`RunConfig` field says "B": a B run is told apart by its corpus ids (ending in `B`) and its
strategy names (ending in `_b`), and this runner accepts nothing else unless `require_b` is off.
"""

from __future__ import annotations

from pathlib import Path

import httpx2

from plantgraph.infra.environment import collect_run_environment
from plantgraph.qa.harness.clients import build_chat_client
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory
from plantgraph.qa.harness.fill import Invocation, ProgressSink
from plantgraph.qa.harness.freeze import check_reportable
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.runner import (
    _REPO_ROOT,
    _check_concurrency,
    _check_inputs_match_config,
    _load_all_questions,
    _require_cap_for_paid_run,
)
from plantgraph.qa.harness.summary import RunSummary, summarize_rows
from plantgraph.qa.models import RunConfig
from plantgraph.qa.v2tb.attempt_b import LoadedCorpusB
from plantgraph.qa.v2tb.corpus_b import B_CORPUS_SUFFIX, load_corpus_b, open_checked_neo4j_view_b
from plantgraph.qa.v2tb.fill_b import fill_answers_b
from plantgraph.qa.v2tb.registry_b import B_STRATEGY_NAMES
from plantgraph.qa.v2tb.strategies_b import CYPHER_RAG_LINES_B_NAME


def check_b_run(config: RunConfig) -> None:
    """Refuse a run that is not purely B: a corpus id not ending in `B`, or a non-B strategy.

    Raises:
        ValueError: naming what was expected and what the config holds.
    """
    not_b = [c for c in config.corpora if not c.endswith(B_CORPUS_SUFFIX)]
    if not_b:
        raise ValueError(
            f"expected only B corpora (ids ending in {B_CORPUS_SUFFIX!r}), found {not_b}"
        )
    _check_b_strategies(config)


def _check_b_strategies(config: RunConfig) -> None:
    unknown = sorted(set(config.strategies) - set(B_STRATEGY_NAMES))
    if unknown:
        raise ValueError(f"expected only strategies in {sorted(B_STRATEGY_NAMES)}, found {unknown}")


def run_harness_b(
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
    cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view_b,
    require_b: bool = True,
) -> RunSummary:
    """Copy of `run_harness`: run (or resume, or replay) the B run `config` describes.

    The arguments are `run_harness`'s, plus `require_b`: refuse a config that holds an A corpus
    (on by default; off only for the runner-equivalence test, which runs the B code over an A
    corpus). Raises `ValueError` as `run_harness` does, and for a config that is not purely B.
    """
    check_reportable(config)
    if require_b:
        check_b_run(config)
    else:
        _check_b_strategies(config)
    _require_cap_for_paid_run(config)
    _check_concurrency(config, concurrency, cost_per_question_usd)
    questions = _load_all_questions(config, questions_root)
    _check_inputs_match_config(config, questions_root, corpora_root)
    corpora = _load_corpora_b(config, corpus_roles, corpora_root, cypher_source_factory, require_b)
    run_dir = RunDir(runs_root / config.run_id)
    # the guard is this invocation's flag, never a stored one (see `run_harness`)
    allow_paid_calls = config.allow_paid_calls
    max_spend_usd = config.max_spend_usd
    config = run_dir.freeze(config)
    run_dir.write_corpus_records([corpus.record for corpus in corpora.values()])
    run_dir.append_environment(collect_run_environment(_REPO_ROOT, concurrency))

    client, cache = build_chat_client(
        pin=config.answer_pin,
        allow_paid_calls=allow_paid_calls,
        cache_path=cache_path,
        calls_log_path=run_dir.calls_path,
        http_client=http_client,
    )
    try:
        filled = fill_answers_b(
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
        filled.n_new_rows,
        stopped_by_spend_cap=filled.stopped_by_spend_cap,
        late_after_timeout_usd=filled.late_after_timeout_usd,
    )


def _load_corpora_b(
    config: RunConfig,
    corpus_roles: dict[str, str],
    corpora_root: Path,
    cypher_source_factory: CypherSourceFactory,
    require_b: bool,
) -> dict[str, LoadedCorpusB]:
    """Rebuild each corpus once; a corpus that fails its check frees the earlier ones' databases."""
    needs_cypher = CYPHER_RAG_LINES_B_NAME in config.strategies
    corpora: dict[str, LoadedCorpusB] = {}
    try:
        for corpus_id in config.corpora:
            corpora[corpus_id] = load_corpus_b(
                corpus_id,
                corpus_roles[corpus_id],
                corpora_root,
                cypher_source_factory=cypher_source_factory,
                needs_cypher=needs_cypher,
                require_b=require_b,
            )
    except Exception:
        _close_cypher_sources(corpora)
        raise
    return corpora


def _close_cypher_sources(corpora: dict[str, LoadedCorpusB]) -> None:
    for corpus in corpora.values():
        if corpus.cypher is not None:
            corpus.cypher.close()
