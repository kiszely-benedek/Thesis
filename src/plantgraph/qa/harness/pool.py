"""Run jobs on a bounded thread pool and commit their results strictly in job order (ADR-0043).

Workers may finish in any order; `commit` is still called for job 0, then 1, then 2 ...
from the calling thread, so what the commit writes (`answers.jsonl`) is the same for
every pool size. A job that fails, or that `admit` refuses, blocks the commits behind
it: the committed rows are always a gap-free prefix, which is what resume relies on.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass

#: The most workers `--concurrency` may ask for (ADR-0043).
MAX_CONCURRENCY = 8


@dataclass(frozen=True)
class _Failed:
    """A job's exception, held in the reorder buffer until its turn to block the commits."""

    error: BaseException


class _InOrderCommitter[Job, Result]:
    """Buffers finished results and commits the next one in line, as soon as it is there."""

    def __init__(self, jobs: Sequence[Job], commit: Callable[[Job, Result], None]) -> None:
        self._jobs = jobs
        self._commit = commit
        self._finished: dict[int, Result | _Failed] = {}
        self._next = 0  # position of the next job to commit
        #: The exception of the first failed job, once the commits have reached it.
        self.blocker: BaseException | None = None

    def finish(self, position: int, outcome: Result | _Failed) -> None:
        self._finished[position] = outcome
        while self.blocker is None and self._next in self._finished:
            outcome = self._finished.pop(self._next)
            if isinstance(outcome, _Failed):
                self.blocker = outcome.error  # later results stay buffered, never committed
                return
            self._commit(self._jobs[self._next], outcome)
            self._next += 1


def run_in_order[Job, Ticket, Result](
    jobs: Sequence[Job],
    *,
    concurrency: int,
    admit: Callable[[Job], Ticket],
    work: Callable[[Job, Ticket], Result],
    commit: Callable[[Job, Result], None],
    is_warmup: Callable[[Job], bool],
) -> BaseException | None:
    """Run `work` on up to `concurrency` threads and `commit` the results in job order.

    Args:
        jobs: in the order their results must be committed.
        concurrency: pool size; 1 runs one job at a time, in order.
        admit: called here, before a job starts; raising refuses it and every later job.
            Its return value (a spend reservation) is passed on to `work`.
        work: runs on a worker thread and must release whatever `admit` took.
        commit: called here, once per job, in job order.
        is_warmup: a warm-up job runs alone, so the lazy caches it builds (a routing
            graph, an item graph) are built once and are complete before others read them.

    Returns:
        `None` if every job was committed; else the error that stopped the pass:
        the first failed job's exception, or `admit`'s refusal. Jobs after it are
        not committed (their model calls are cached, so a resume replays them free).
    """
    committer = _InOrderCommitter[Job, Result](jobs, commit)
    refusal: BaseException | None = None
    in_flight: dict[Future[Result], int] = {}  # future -> job position
    next_to_start = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        while True:
            while refusal is None and committer.blocker is None and next_to_start < len(jobs):
                job = jobs[next_to_start]
                if not _may_start(
                    job, [jobs[p] for p in in_flight.values()], concurrency, is_warmup
                ):
                    break
                try:
                    ticket = admit(job)
                except Exception as error:  # noqa: BLE001 - any refusal ends the pass the same way
                    refusal = error
                    break
                in_flight[executor.submit(work, job, ticket)] = next_to_start
                next_to_start += 1
            if not in_flight:
                break
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:  # `done` is a set; the committer restores the order
                outcome = _outcome_of(future)
                committer.finish(in_flight.pop(future), outcome)
    return committer.blocker or refusal


def _may_start[Job](
    job: Job, running: list[Job], concurrency: int, is_warmup: Callable[[Job], bool]
) -> bool:
    if len(running) >= concurrency:
        return False
    if any(is_warmup(other) for other in running):
        return False  # a warm-up job is still building caches: nothing starts beside it
    return not (is_warmup(job) and running)  # a warm-up job waits for the pool to empty


def _outcome_of[Result](future: Future[Result]) -> Result | _Failed:
    error = future.exception()
    return _Failed(error) if error is not None else future.result()
