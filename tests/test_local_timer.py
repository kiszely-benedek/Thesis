"""`LocalTimer`: exact sums with a fake clock, nesting, and no effect without an active timer."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from plantgraph.qa.harness.usage_meter import TimingRow
from plantgraph.qa.local_timer import (
    LocalTimer,
    active_local_timer,
    add_local_seconds,
    deactivate,
    local_timer,
)
from plantgraph.qa.neo4j_view import _server_seconds


class FakeClock:
    """A clock that moves only when the test says so."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_block_adds_its_seconds_and_one_call_each() -> None:
    clock = FakeClock()
    timer = LocalTimer(clock=clock)
    token = timer.activate()
    try:
        with local_timer("graph_api"):
            clock.now += 0.25
        with local_timer("graph_api"):
            clock.now += 0.5
    finally:
        deactivate(token)
    assert timer.seconds_of("graph_api") == pytest.approx(0.75)
    assert timer.calls_of("graph_api") == 2


def test_different_kinds_nest_and_both_are_counted() -> None:
    clock = FakeClock()
    timer = LocalTimer(clock=clock)
    token = timer.activate()
    try:
        with local_timer("db_client"):
            clock.now += 1.0
            with local_timer("graph_api"):
                clock.now += 2.0
    finally:
        deactivate(token)
    assert timer.seconds_of("db_client") == pytest.approx(3.0)
    assert timer.seconds_of("graph_api") == pytest.approx(2.0)


def test_a_nested_block_of_the_same_kind_is_not_counted_twice() -> None:
    clock = FakeClock()
    timer = LocalTimer(clock=clock)
    token = timer.activate()
    try:
        with local_timer("graph_api"):
            clock.now += 1.0
            with local_timer("graph_api"):
                clock.now += 1.0
    finally:
        deactivate(token)
    assert timer.seconds_of("graph_api") == pytest.approx(2.0)
    assert timer.calls_of("graph_api") == 1


def test_an_exception_still_records_the_time_and_closes_the_block() -> None:
    clock = FakeClock()
    timer = LocalTimer(clock=clock)
    token = timer.activate()
    try:
        with pytest.raises(ValueError), local_timer("db_client"):
            clock.now += 0.5
            raise ValueError("boom")
        with local_timer("db_client"):
            clock.now += 0.5
    finally:
        deactivate(token)
    assert timer.seconds_of("db_client") == pytest.approx(1.0)
    assert timer.calls_of("db_client") == 2


def test_without_an_active_timer_everything_is_a_no_op() -> None:
    assert active_local_timer() is None
    with local_timer("graph_api"):
        pass
    add_local_seconds("db_server", 1.0)  # must not raise
    assert active_local_timer() is None


def test_deactivate_restores_the_previous_timer() -> None:
    timer = LocalTimer()
    token = timer.activate()
    assert active_local_timer() is timer
    deactivate(token)
    assert active_local_timer() is None


def test_server_seconds_added_directly_are_counted() -> None:
    timer = LocalTimer()
    token = timer.activate()
    try:
        add_local_seconds("db_server", 0.02)
    finally:
        deactivate(token)
    assert timer.seconds_of("db_server") == pytest.approx(0.02)
    assert timer.seconds_of("never_used") == 0.0


def test_an_old_timing_line_parses_as_monotonic_with_zero_splits() -> None:
    old = (
        '{"question_id":"q1","strategy":"context_rag","repeat":0,'
        '"local_compute_s":0.015625,"spent_usd":0.0,"n_cached_retrieval_calls":0}'
    )
    row = TimingRow.model_validate_json(old)
    assert row.clock == "monotonic"
    assert row.wall_s is None
    assert (row.db_client_s, row.db_server_s, row.graph_api_s) == (0.0, 0.0, 0.0)
    assert (row.n_db_queries, row.n_graph_api_calls) == (0, 0)


def test_a_new_timing_row_round_trips() -> None:
    row = TimingRow(
        question_id="q1",
        strategy="cypher_rag_plant",
        repeat=0,
        local_compute_s=0.3,
        spent_usd=0.0,
        n_cached_retrieval_calls=1,
        clock="perf_counter",
        wall_s=1.5,
        db_client_s=0.2,
        db_server_s=0.05,
        n_db_queries=2,
        graph_api_s=0.01,
        n_graph_api_calls=3,
    )
    assert TimingRow.model_validate_json(row.model_dump_json()) == row


def test_server_seconds_sum_the_summary_milliseconds_and_tolerate_missing_parts() -> None:
    both = SimpleNamespace(result_available_after=19, result_consumed_after=1)
    neither = SimpleNamespace(result_available_after=None, result_consumed_after=None)
    assert _server_seconds(both) == pytest.approx(0.02)  # type: ignore[arg-type]
    assert _server_seconds(neither) == 0.0  # type: ignore[arg-type]
