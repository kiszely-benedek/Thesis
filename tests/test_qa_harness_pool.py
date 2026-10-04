"""The ordered thread pool and the spend guard's reservations (ADR-0043), without any model."""

from __future__ import annotations

import threading
import time
from datetime import datetime

import pytest

from plantgraph.llm.models import ChatResponse
from plantgraph.qa.harness.pool import run_in_order
from plantgraph.qa.harness.spend_cap import SpendCapReached, SpendGuard


def _run(
    jobs: list[int],
    *,
    concurrency: int,
    work_s: dict[int, float] | None = None,
    fail_on: int | None = None,
    refuse_at: int | None = None,
    warmups: frozenset[int] = frozenset(),
) -> tuple[list[int], BaseException | None]:
    """Run integer jobs; returns the committed jobs, in commit order, and the pass's error."""
    committed: list[int] = []

    def admit(job: int) -> None:
        if job == refuse_at:
            raise SpendCapReached("refused")

    def work(job: int, _ticket: None) -> int:
        time.sleep((work_s or {}).get(job, 0.0))
        if job == fail_on:
            raise RuntimeError(f"job {job} failed")
        return job * 10

    error = run_in_order(
        jobs,
        concurrency=concurrency,
        admit=admit,
        work=work,
        commit=lambda job, _result: committed.append(job),
        is_warmup=lambda job: job in warmups,
    )
    return committed, error


def test_results_are_committed_in_job_order_whatever_finishes_first() -> None:
    slow_first = {0: 0.06, 1: 0.04, 2: 0.02, 3: 0.0}

    committed, error = _run([0, 1, 2, 3, 4, 5], concurrency=4, work_s=slow_first)

    assert (committed, error) == ([0, 1, 2, 3, 4, 5], None)


def test_a_failed_job_blocks_the_commits_behind_it() -> None:
    committed, error = _run(list(range(8)), concurrency=4, fail_on=3)

    assert committed == [0, 1, 2]  # a gap-free prefix, even if jobs 4 to 7 had finished
    assert isinstance(error, RuntimeError)


def test_a_refused_job_ends_the_pass_with_the_prefix_committed() -> None:
    committed, error = _run(list(range(8)), concurrency=4, refuse_at=5)

    assert committed == [0, 1, 2, 3, 4]
    assert isinstance(error, SpendCapReached)


def test_a_warmup_job_runs_alone() -> None:
    running, overlaps = 0, []
    lock = threading.Lock()

    def work(job: int, _ticket: None) -> int:
        nonlocal running
        with lock:
            running += 1
            overlaps.append((job, running))
        time.sleep(0.02)
        with lock:
            running -= 1
        return job

    run_in_order(
        list(range(6)),
        concurrency=4,
        admit=lambda _job: None,
        work=work,
        commit=lambda _job, _result: None,
        is_warmup=lambda job: job in (0, 3),
    )

    assert [count for job, count in overlaps if job in (0, 3)] == [1, 1]
    assert max(count for _job, count in overlaps) > 1  # the others did overlap


# ------------------------------------------------------------ reservations


def _live_response(cost: float) -> ChatResponse:
    return ChatResponse(
        text="x",
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=cost,
        latency_s=0.0,
        provider_response_id=None,
        finish_reason="stop",
        from_cache=False,
        created_at=datetime(2026, 10, 3),
    )


def test_open_reservations_count_against_the_cap() -> None:
    guard = SpendGuard(0.05, estimate_usd=0.02)
    first, _second = guard.reserve(), guard.reserve()  # 0 spent + 0.04 reserved + 0.02 >= 0.05

    with pytest.raises(SpendCapReached, match="reserved by items in flight"):
        guard.reserve()

    guard.release(first, 0.0)  # an item that spent nothing frees its share
    guard.reserve()


def test_a_calling_item_does_not_count_its_own_reservation_twice() -> None:
    guard = SpendGuard(0.05, estimate_usd=0.02)
    mine, _other = guard.reserve(), guard.reserve()
    guard.add(_live_response(0.01))

    guard.check_before_call(mine)  # 0.01 spent + 0.02 (the other) + 0.01 call < 0.05
    with pytest.raises(SpendCapReached):
        guard.check_before_call()  # counting both reservations: 0.01 + 0.04 + 0.01 >= 0.05
