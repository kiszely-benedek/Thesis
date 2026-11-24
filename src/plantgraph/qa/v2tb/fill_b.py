"""Answering every pending row of a B run: the B twin of `harness/fill.py`.

The frozen `fill_answers` builds its strategies with the A registry and answers through the A
`attempt`, both by name. So the three functions that reach them are copied (`fill_answers_b`,
`_jobs_b`, `_work_items_b`), and `_PassB` swaps the one method that calls `attempt`. The pool, the
spend guard, the row writer and the retry pass are the frozen ones.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ProviderError
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.harness.attempt import (
    LoadedCorpus,
    WorkItem,
    active_remaining_s,
    sender_factory,
)
from plantgraph.qa.harness.fill import (
    FillResult,
    Invocation,
    Outcome,
    ProgressSink,
    _announce_mode,
    _Job,
    _Pass,
    spend_guard_for_resume,
)
from plantgraph.qa.harness.registry import CypherDeps, LlmDeps
from plantgraph.qa.harness.row_order import restore_row_order
from plantgraph.qa.harness.run_dir import RowKey, RunDir, row_key
from plantgraph.qa.harness.spend_cap import Reservation, SpendCapReached
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.models import Question, RunConfig
from plantgraph.qa.v2tb.attempt_b import LoadedCorpusB, attempt_b
from plantgraph.qa.v2tb.registry_b import build_strategy_b


class _PassB(_Pass):
    """The frozen pass, answering each job with `attempt_b`."""

    def _answer(self, job: _Job, reservation: Reservation) -> Outcome:
        """Copy of `_Pass._answer`, calling `attempt_b`."""
        meter = UsageMeter(
            self._guard, reservation=reservation, deadline_s=self._config.question_deadline_s
        )
        try:
            corpus = self._corpora[job.corpus_id]
            if not isinstance(corpus, LoadedCorpusB):
                raise TypeError(f"expected a LoadedCorpusB for {job.corpus_id!r}, found {corpus!r}")
            return attempt_b(job.item, self._config, corpus, self._client, meter)
        finally:
            self._guard.release(reservation, meter.spent_usd)


def fill_answers_b(
    config: RunConfig,
    invocation: Invocation,
    questions: list[Question],
    corpora: Mapping[str, LoadedCorpusB],
    run_dir: RunDir,
    client: ChatClient,
    progress: ProgressSink,
) -> FillResult:
    """Copy of `fill_answers`: answer every pending row with the B strategies and scorer."""
    dropped = run_dir.drop_provider_error_rows()
    rows_on_disk = run_dir.read_rows()
    done = {row_key(row) for row in rows_on_disk}
    guard = spend_guard_for_resume(invocation, rows_on_disk, run_dir.spent_usd())
    client.on_late_response = guard.charge_late
    jobs = _jobs_b(config, questions, corpora, done, sender_factory(client, config))
    progress(f"run {config.run_id}: {len(jobs)} rows to answer, {len(done)} already on disk")
    if dropped:
        progress(f"re-queued {dropped} rows that ended in PROVIDER_ERROR last time")
    _announce_mode(invocation, len(jobs), progress)

    shared: dict[str, LoadedCorpus] = dict(corpora)  # the frozen pass takes the base type
    pass_ = _PassB(config, invocation.concurrency, shared, client, guard, run_dir)
    retry_later: list[_Job] = []

    def write_or_defer(job: _Job, outcome: Outcome) -> None:
        if isinstance(outcome, ProviderError):
            retry_later.append(job)  # asked again after the first pass, in the same order
        else:
            pass_.write_answered(outcome)

    blocker = pass_.run(jobs, write_or_defer)
    if blocker is None:  # one more try each, then record the error
        blocker = pass_.run(retry_later, pass_.write_retry)
    if blocker is not None and not isinstance(blocker, SpendCapReached):
        raise blocker
    restore_row_order(run_dir, config, questions)
    if blocker is not None:
        progress(f"STOPPED by the spend cap: {blocker}. Rerun with the same --run-id to resume.")
    return FillResult(pass_.written, blocker is not None, guard.late_usd)


def _jobs_b(
    config: RunConfig,
    questions: list[Question],
    corpora: Mapping[str, LoadedCorpusB],
    done: set[RowKey],
    sender_for: Callable[[str], SendChatRequest],
) -> list[_Job]:
    """Copy of `_jobs`: every pending item in commit order, a strategy's first marked warm-up."""
    jobs: list[_Job] = []
    for corpus_id in config.corpora:
        items = _work_items_b(config, corpus_id, questions, corpora[corpus_id], done, sender_for)
        seen_strategies: set[str] = set()
        for item in items:
            first = item.strategy.name not in seen_strategies
            seen_strategies.add(item.strategy.name)
            jobs.append(_Job(corpus_id, item, first))
    return jobs


def _work_items_b(
    config: RunConfig,
    corpus_id: str,
    questions: list[Question],
    corpus: LoadedCorpusB,
    done: set[RowKey],
    sender_for: Callable[[str], SendChatRequest],
) -> Iterator[WorkItem]:
    """Copy of `_work_items`, building each strategy with `build_strategy_b`."""
    corpus_questions = [q for q in questions if q.corpus_id == corpus_id]
    for name, params in config.strategies.items():
        cypher = (
            CypherDeps(corpus.cypher, config.answer_pin, sender_for(name), config.primer)
            if corpus.cypher is not None
            else None
        )
        llm = LlmDeps(config.answer_pin, sender_for(name), config.primer, active_remaining_s)
        strategy = build_strategy_b(name, params, corpus.view, cypher, llm)
        for question in corpus_questions:
            for repeat in range(config.repeats):
                if (question.question_id, name, repeat) not in done:
                    yield WorkItem(strategy, question, repeat)
