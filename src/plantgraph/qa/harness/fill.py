"""Answer every row not yet on disk: the work list, the pool, the in-order writes.

Split out of `runner.py`, which loads and checks the inputs. The order of rows in
`answers.jsonl` is corpus, then strategy, then question, then repeat, whatever the
pool size (`pool.py`); the provider-error retry pass comes after the first pass.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from plantgraph.llm.client import ChatClient
from plantgraph.llm.models import ProviderError
from plantgraph.qa.final_answer import SendChatRequest
from plantgraph.qa.harness.attempt import (
    Answered,
    LoadedCorpus,
    WorkItem,
    active_remaining_s,
    attempt,
    provider_error_row,
    sender_factory,
)
from plantgraph.qa.harness.pool import run_in_order
from plantgraph.qa.harness.registry import CypherDeps, LlmDeps, build_strategy
from plantgraph.qa.harness.run_dir import RowKey, RunDir, row_key
from plantgraph.qa.harness.spend_cap import Reservation, SpendCapReached, SpendGuard
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.models import Question, QuestionResult, RunConfig

ProgressSink = Callable[[str], None]
Outcome = Answered | ProviderError


@dataclass(frozen=True)
class Invocation:
    """Settings of this call that a resume may change; the frozen config does not decide them."""

    allow_paid_calls: bool
    max_spend_usd: float | None
    cost_per_question_usd: float | None
    concurrency: int = 1


@dataclass(frozen=True)
class _Job:
    """A work item with the corpus it belongs to and whether it is its strategy's first."""

    corpus_id: str
    item: WorkItem
    is_first_of_strategy: bool


def fill_answers(
    config: RunConfig,
    invocation: Invocation,
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
    client.on_late_response = guard.charge_late  # money an abandoned call costs still counts
    jobs = _jobs(config, questions, corpora, done, sender_factory(client, config))
    progress(f"run {config.run_id}: {len(jobs)} rows to answer, {len(done)} already on disk")
    if dropped:
        progress(f"re-queued {dropped} rows that ended in PROVIDER_ERROR last time")
    _announce_mode(invocation, len(jobs), progress)

    pass_ = _Pass(config, invocation.concurrency, corpora, client, guard, run_dir)
    retry_later: list[_Job] = []

    def write_or_defer(job: _Job, outcome: Outcome) -> None:
        if isinstance(outcome, ProviderError):
            retry_later.append(job)  # asked again after the first pass, in the same order
        else:
            pass_.write_answered(outcome)

    blocker = pass_.run(jobs, write_or_defer)
    if blocker is None:  # one more try each, then record the error
        blocker = pass_.run(retry_later, pass_.write_retry)
    if blocker is None:
        return pass_.written, False
    if isinstance(blocker, SpendCapReached):
        # rows are appended whole and the cache keeps unwritten items' calls, so a resume is clean
        progress(f"STOPPED by the spend cap: {blocker}. Rerun with the same --run-id to resume.")
        return pass_.written, True
    raise blocker


class _Pass:
    """The shared state of the passes over job lists: pool size, run services, the row writer."""

    def __init__(
        self,
        config: RunConfig,
        concurrency: int,
        corpora: dict[str, LoadedCorpus],
        client: ChatClient,
        guard: SpendGuard,
        run_dir: RunDir,
    ) -> None:
        self._config = config
        self._concurrency = concurrency
        self._corpora = corpora
        self._client = client
        self._guard = guard
        self._run_dir = run_dir
        self.written = 0  # rows this invocation has appended

    def run(
        self, jobs: list[_Job], commit: Callable[[_Job, Outcome], None]
    ) -> BaseException | None:
        """One pass; returns the error that stopped it, if any (see `run_in_order`)."""
        return run_in_order(
            jobs,
            concurrency=self._concurrency,
            admit=lambda _job: self._guard.reserve(),
            work=self._answer,
            commit=commit,
            is_warmup=lambda job: job.is_first_of_strategy,
        )

    def _answer(self, job: _Job, reservation: Reservation) -> Outcome:
        """Runs on a worker thread: its own meter, and the reservation is always released."""
        meter = UsageMeter(
            self._guard, reservation=reservation, deadline_s=self._config.question_deadline_s
        )
        try:
            corpus = self._corpora[job.corpus_id]
            return attempt(job.item, self._config, corpus, self._client, meter)
        finally:
            self._guard.release(reservation, meter.spent_usd)

    def write_answered(self, answered: Answered) -> None:
        self._run_dir.append_row(answered.row)
        self._run_dir.append_timing(answered.timing)
        self.written += 1

    def write_retry(self, job: _Job, outcome: Outcome) -> None:
        """Second pass: an error that survives is recorded as a `PROVIDER_ERROR` row."""
        if isinstance(outcome, ProviderError):
            self._run_dir.append_row(provider_error_row(job.item, self._config, outcome))
            self.written += 1
        else:
            self.write_answered(outcome)


def _spend_guard(invocation: Invocation, rows_on_disk: list[QuestionResult]) -> SpendGuard:
    """Seed the guard with what earlier invocations recorded as their total cost."""
    totals = [row.total_cost_usd or 0.0 for row in rows_on_disk]
    return SpendGuard(
        invocation.max_spend_usd if invocation.allow_paid_calls else None,
        recorded_usd=sum(totals),
        max_question_usd=max(totals, default=0.0),
        estimate_usd=invocation.cost_per_question_usd,
    )


def _announce_mode(invocation: Invocation, n_pending: int, progress: ProgressSink) -> None:
    """Say before the first call whether this run can spend money, and roughly how much."""
    if invocation.concurrency > 1:
        progress(f"concurrency {invocation.concurrency}: up to that many questions in flight")
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


def _jobs(
    config: RunConfig,
    questions: list[Question],
    corpora: dict[str, LoadedCorpus],
    done: set[RowKey],
    sender_for: Callable[[str], SendChatRequest],
) -> list[_Job]:
    """Every pending item in commit order, the first of each strategy marked as warm-up."""
    jobs: list[_Job] = []
    for corpus_id in config.corpora:
        items = _work_items(config, corpus_id, questions, corpora[corpus_id], done, sender_for)
        seen_strategies: set[str] = set()
        for item in items:
            first = item.strategy.name not in seen_strategies
            seen_strategies.add(item.strategy.name)
            jobs.append(_Job(corpus_id, item, first))
    return jobs


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
    for name, params in config.strategies.items():
        cypher = (
            CypherDeps(corpus.cypher, config.answer_pin, sender_for(name), config.primer)
            if corpus.cypher is not None
            else None
        )
        llm = LlmDeps(config.answer_pin, sender_for(name), config.primer, active_remaining_s)
        strategy = build_strategy(name, params, corpus.view, cypher, llm)
        for question in corpus_questions:
            for repeat in range(config.repeats):
                if (question.question_id, name, repeat) not in done:
                    yield WorkItem(strategy, question, repeat)
