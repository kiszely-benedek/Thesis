"""A harness run writes precise-clock timing rows and `environment.jsonl`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.harness.usage_meter import TimingRow
from qa_harness_toy import (
    CORPUS_ID,
    Toy,
    abstaining_transport,
    build_toy,
    make_config,
)


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("timing-toy"))


def _run(toy: Toy, tmp_path: Path, fake: FakeTransport, runs_name: str, paid: bool) -> None:
    run_harness(
        config=make_config(toy, allow_paid_calls=paid),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / runs_name,
        cache_path=tmp_path / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
        concurrency=2,
        cost_per_question_usd=0.01 if paid else None,  # a paid run reserves it per item
    )


def test_timing_rows_use_the_precise_clock_and_keep_the_parts_inside_the_whole(
    toy: Toy, tmp_path: Path
) -> None:
    _run(toy, tmp_path, abstaining_transport(), "runs", paid=True)
    lines = (tmp_path / "runs" / "toy" / "timings.jsonl").read_text("utf-8").splitlines()
    rows = [TimingRow.model_validate_json(line) for line in lines]
    assert len(rows) == len(toy.questions)
    for row in rows:
        assert row.clock == "perf_counter"
        assert row.wall_s is not None and row.wall_s >= row.local_compute_s >= 0.0
        assert row.db_client_s + row.graph_api_s <= row.local_compute_s + 0.001
        assert row.n_db_queries == 0  # context_rag asks the database nothing


def test_each_invocation_appends_one_environment_line(toy: Toy, tmp_path: Path) -> None:
    _run(toy, tmp_path, abstaining_transport(), "runs", paid=True)
    _run(toy, tmp_path, abstaining_transport(), "runs", paid=False)  # a resume
    lines = (tmp_path / "runs" / "toy" / "environment.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["concurrency"] == 2
    assert first["clock"] == "perf_counter"
    assert first["machine"]["ram_bytes"] > 0


def test_replay_with_the_timer_active_gives_identical_answers(toy: Toy, tmp_path: Path) -> None:
    _run(toy, tmp_path, abstaining_transport(), "live", paid=True)
    replay_fake = abstaining_transport()
    # the replay reads the live run's cache (same file): no network, same bytes
    _run(toy, tmp_path, replay_fake, "replayed", paid=False)
    live = (tmp_path / "live" / "toy" / "answers.jsonl").read_bytes()
    assert (tmp_path / "replayed" / "toy" / "answers.jsonl").read_bytes() == live
    assert replay_fake.requests == []
