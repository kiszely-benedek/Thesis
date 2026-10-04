"""The harness end to end (`qa-system.md` §18 QA-T10), offline with the fake transport.

`allow_paid_calls=True` appears below only together with an injected
`FakeTransport`, which answers from a script and opens no socket; no test
passes the CLI flag or touches the network.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.llm.models import CacheMiss, ContextWall
from plantgraph.qa.harness.cli import main as cli_main
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.harness.summary import RunSummary
from plantgraph.qa.models import CorpusRecord, Outcome, QuestionResult, RunConfig
from qa_harness_toy import (
    CORPUS_ID,
    Toy,
    abstaining_transport,
    build_toy,
    make_config,
    pin,
    seed_cache,
)


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("harness-toy"))


def _run(
    toy: Toy,
    config: RunConfig,
    tmp_path: Path,
    fake: FakeTransport,
    *,
    runs_name: str = "runs",
) -> RunSummary:
    return run_harness(
        config=config,
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / runs_name,
        cache_path=tmp_path / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
    )


def _rows(tmp_path: Path, runs_name: str = "runs", run_id: str = "toy") -> list[QuestionResult]:
    lines = (tmp_path / runs_name / run_id / "answers.jsonl").read_text("utf-8").splitlines()
    return [QuestionResult.model_validate_json(line) for line in lines]


def test_toy_run_end_to_end(toy: Toy, tmp_path: Path) -> None:
    fake = abstaining_transport()
    summary = _run(toy, make_config(toy, allow_paid_calls=True), tmp_path, fake)

    rows = _rows(tmp_path)
    assert len(rows) == len(toy.questions) == summary.n_rows
    assert {row.outcome for row in rows} == {Outcome.ANSWERED}
    answerable = {q.question_id: q.answerable for q in toy.questions}
    assert all(row.correct == (not answerable[row.question_id]) for row in rows)
    assert len(fake.requests) == len(rows)

    run_dir = tmp_path / "runs" / "toy"
    assert len((run_dir / "calls.jsonl").read_text("utf-8").splitlines()) == len(rows)
    assert (
        RunConfig.model_validate_json((run_dir / "run_config.json").read_text("utf-8")).run_id
        == "toy"
    )
    by_bin = summary.outcomes_by_k_bin["context_rag"]
    assert sum(sum(outcomes.values()) for outcomes in by_bin.values()) == len(rows)


def test_replay_reproduces_answers_byte_for_byte(toy: Toy, tmp_path: Path) -> None:
    _run(toy, make_config(toy, allow_paid_calls=True), tmp_path, abstaining_transport())

    replay_fake = abstaining_transport()
    _run(toy, make_config(toy), tmp_path, replay_fake, runs_name="replayed")

    original = (tmp_path / "runs" / "toy" / "answers.jsonl").read_bytes()
    assert (tmp_path / "replayed" / "toy" / "answers.jsonl").read_bytes() == original
    assert replay_fake.requests == []


def test_interrupted_run_resumes_without_duplicate_rows(toy: Toy, tmp_path: Path) -> None:
    done = toy.questions[:3]
    seed_cache(toy, tmp_path / "cache.sqlite", done)

    # a replay run with a partly filled cache stops at the first miss, like an interrupt
    stopped = abstaining_transport()
    with pytest.raises(CacheMiss):
        _run(toy, make_config(toy), tmp_path, stopped)
    before = (tmp_path / "runs" / "toy" / "answers.jsonl").read_bytes()
    assert len(_rows(tmp_path)) == len(done)

    resume_fake = abstaining_transport()
    _run(toy, make_config(toy, allow_paid_calls=True), tmp_path, resume_fake)

    after = (tmp_path / "runs" / "toy" / "answers.jsonl").read_bytes()
    assert after.startswith(before)
    ids = [row.question_id for row in _rows(tmp_path)]
    assert sorted(ids) == sorted(q.question_id for q in toy.questions)
    assert len(resume_fake.requests) == len(toy.questions) - len(done)


def _wall_for_other_model() -> ContextWall:
    return ContextWall(
        pin_hash="some-other-pin",
        max_ok_chars=10,
        measured_at=datetime(2026, 10, 1),
        probe_corpus_ids=["D10"],
    )


@pytest.mark.parametrize(
    ("overrides", "complaint"),
    [
        ({}, "no context wall"),
        ({"prompt_hashes": {}}, "no prompt hashes"),
        ({"question_set_sha256": ""}, "no question-set hash"),
    ],
)
def test_reported_run_refuses_without_a_frozen_config(
    toy: Toy, tmp_path: Path, overrides: dict[str, Any], complaint: str
) -> None:
    fake = abstaining_transport()
    config = make_config(toy, reported=True, allow_paid_calls=True, **overrides)

    with pytest.raises(ValueError, match=complaint):
        _run(toy, config, tmp_path, fake)

    assert not (tmp_path / "runs").exists()  # nothing was frozen or written
    assert fake.requests == []


def test_reported_run_refuses_a_wall_measured_for_another_pin(toy: Toy, tmp_path: Path) -> None:
    config = make_config(toy, reported=True, context_wall=_wall_for_other_model())
    with pytest.raises(ValueError, match="not the answer pin"):
        _run(toy, config, tmp_path, abstaining_transport())


def test_without_allow_paid_calls_nothing_is_sent(
    toy: Toy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def key_must_not_be_read() -> None:
        raise AssertionError("a free run must not even read the API key settings")

    monkeypatch.setattr("plantgraph.llm.openrouter_settings.from_env", key_must_not_be_read)
    fake = abstaining_transport()

    with pytest.raises(CacheMiss):  # empty cache, replay mode: stop at the first miss
        _run(toy, make_config(toy), tmp_path, fake)

    assert fake.requests == []


def test_a_frozen_run_rejects_a_resume_with_different_measured_fields(
    toy: Toy, tmp_path: Path
) -> None:
    _run(toy, make_config(toy, allow_paid_calls=True), tmp_path, abstaining_transport())
    with pytest.raises(ValueError, match="already frozen"):
        _run(toy, make_config(toy, repeats=2), tmp_path, abstaining_transport())


def test_persistent_provider_errors_are_requeued_once_then_recorded(
    toy: Toy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("plantgraph.llm.client.time.sleep", lambda _seconds: None)
    broken = abstaining_transport(fail_times=10**6, fail_status=500)
    summary = _run(toy, make_config(toy, allow_paid_calls=True), tmp_path, broken)
    assert summary.n_provider_errors == len(toy.questions)
    assert {row.outcome for row in _rows(tmp_path)} == {Outcome.PROVIDER_ERROR}

    # a later resume asks those questions again and replaces the error rows
    healthy = abstaining_transport()
    summary = _run(toy, make_config(toy, allow_paid_calls=True), tmp_path, healthy)
    assert summary.n_provider_errors == 0
    assert len(_rows(tmp_path)) == len(toy.questions)


def test_corpus_record_is_filled_from_ingest_json(toy: Toy, tmp_path: Path) -> None:
    _run(toy, make_config(toy, allow_paid_calls=True), tmp_path, abstaining_transport())

    text = (tmp_path / "runs" / "toy" / "corpora.json").read_text("utf-8")
    records = [CorpusRecord.model_validate(item) for item in json.loads(text)]
    ingest = json.loads((toy.corpora_root / CORPUS_ID / "ingest.json").read_text("utf-8"))
    (record,) = records
    assert record.role == "dev"
    assert record.n_sheets == ingest["counts"]["n_sheets"]
    assert record.n_store_nodes == ingest["counts"]["n_nodes"]
    assert record.stage_seconds == ingest["stage_seconds"]
    assert record.n_plant_nodes > 0 and record.n_plant_edges > 0


def test_cli_without_the_flag_is_replay_only_and_stops_at_a_cache_miss(
    toy: Toy, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(pin().model_dump_json(), encoding="utf-8")
    argv = ["--run-id", "cli-toy", "--experiment", "TOOLING", "--corpus", f"{CORPUS_ID}:dev"]
    argv += ["--strategy", "context_rag", "--pin-json", str(pin_path)]
    argv += ["--corpora-root", str(toy.corpora_root), "--questions-root", str(toy.questions_root)]
    argv += ["--runs-root", str(tmp_path / "runs"), "--cache-path", str(tmp_path / "cache.sqlite")]

    with pytest.raises(SystemExit) as stopped:
        cli_main(argv)

    assert stopped.value.code == 2
    assert "replay mode" in capsys.readouterr().out
    config_text = (tmp_path / "runs" / "cli-toy" / "run_config.json").read_text("utf-8")
    assert RunConfig.model_validate_json(config_text).allow_paid_calls is False


def _stored_primer_after_cli_run(toy: Toy, tmp_path: Path, *extra: str) -> bool:
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(pin().model_dump_json(), encoding="utf-8")
    argv = ["--run-id", "cli-primer", "--experiment", "TOOLING", "--corpus", f"{CORPUS_ID}:dev"]
    argv += ["--strategy", "context_rag", "--pin-json", str(pin_path), *extra]
    argv += ["--corpora-root", str(toy.corpora_root), "--questions-root", str(toy.questions_root)]
    argv += ["--runs-root", str(tmp_path / "runs"), "--cache-path", str(tmp_path / "cache.sqlite")]
    with pytest.raises(SystemExit):  # replay mode stops at the first cache miss; the config is kept
        cli_main(argv)
    config_text = (tmp_path / "runs" / "cli-primer" / "run_config.json").read_text("utf-8")
    return RunConfig.model_validate_json(config_text).primer


def test_cli_turns_the_primer_on_by_default(toy: Toy, tmp_path: Path) -> None:
    assert _stored_primer_after_cli_run(toy, tmp_path) is True


def test_cli_no_primer_flag_turns_it_off_and_records_that(toy: Toy, tmp_path: Path) -> None:
    assert _stored_primer_after_cli_run(toy, tmp_path, "--no-primer") is False
