"""Loading the report's files from disk, and the `infra-report` command end to end."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infra_report_builders import corpus
from plantgraph.infra.report_inputs import (
    REPLAY_CHECK_FILE,
    ReportRequest,
    load_report_inputs,
    load_run_data,
)
from plantgraph.qa.cascade.cli import main
from plantgraph.qa.harness.runner import run_harness
from qa_harness_toy import CORPUS_ID, Toy, abstaining_transport, build_toy, make_config


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("report-toy"))


def _make_run(toy: Toy, runs_root: Path, run_id: str) -> Path:
    """A finished toy run whose strategy is renamed to one the report knows."""
    fake = abstaining_transport()
    run_harness(
        config=make_config(toy, allow_paid_calls=True).model_copy(update={"run_id": run_id}),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=runs_root,
        cache_path=runs_root / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
        concurrency=1,
        cost_per_question_usd=0.01,
    )
    config_path = runs_root / run_id / "run_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["strategies"] = {"cypher_rag_plant": {}}
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return runs_root / run_id


def _write_corpus_files(root: Path, corpus_id: str, scale: float) -> None:
    data = corpus(corpus_id, scale)
    for number, ingest in enumerate(data.ingests, start=1):
        path = root / "ingest" / corpus_id / f"rep{number}" / "ingest.json"
        path.parent.mkdir(parents=True)
        path.write_text(ingest.model_dump_json(), encoding="utf-8")
    probe_dir = root / "probe" / corpus_id
    probe_dir.mkdir(parents=True)
    for number, startup in enumerate(data.startups, start=1):
        (probe_dir / f"rep{number}.json").write_text(startup.model_dump_json(), encoding="utf-8")
    assert data.memory is not None
    (probe_dir / "memory.json").write_text(data.memory.model_dump_json(), encoding="utf-8")


def test_a_replay_without_its_check_file_is_refused(toy: Toy, tmp_path: Path) -> None:
    run_dir = _make_run(toy, tmp_path, "INF-X-D100")
    with pytest.raises(FileNotFoundError, match=REPLAY_CHECK_FILE):
        load_run_data(tmp_path, run_dir.name, "x", "D100", "replay")


def test_an_unknown_word_in_the_check_file_is_refused(toy: Toy, tmp_path: Path) -> None:
    run_dir = _make_run(toy, tmp_path, "INF-X-D100")
    (run_dir / REPLAY_CHECK_FILE).write_text("maybe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="maybe"):
        load_run_data(tmp_path, run_dir.name, "x", "D100", "replay")


def test_run_data_reads_status_timings_and_answer_totals(toy: Toy, tmp_path: Path) -> None:
    run_dir = _make_run(toy, tmp_path, "INF-X-D100")
    (run_dir / REPLAY_CHECK_FILE).write_text("identical\n", encoding="utf-8")
    data = load_run_data(tmp_path, run_dir.name, "x", "D100", "replay")
    assert data.replay_status == "identical"
    assert len(data.timings) == len(toy.questions)
    assert data.environments and data.environments[0].clock == "perf_counter"


def test_a_missed_replay_falls_back_to_the_named_old_run(toy: Toy, tmp_path: Path) -> None:
    replays, old = tmp_path / "replays", tmp_path / "old"
    replay_dir = _make_run(toy, replays, "INF-X-D100")
    _make_run(toy, old, "X-D100")
    (replay_dir / REPLAY_CHECK_FILE).write_text("cache_miss\n", encoding="utf-8")
    _write_corpus_files(tmp_path, "D100", 1.0)
    request = ReportRequest(
        ingest_root=tmp_path / "ingest",
        probe_root=tmp_path / "probe",
        runs_root=replays,
        corpora=["D100"],
        compute_corpora=["D100"],
        replay_templates={"x": "INF-X-{c}"},
        old_run_templates={"x": "X-{c}"},
        old_runs_root=old,
        price_json=None,
    )
    inputs = load_report_inputs(request)
    assert [run.basis for run in inputs.runs] == ["old_run"]
    assert inputs.price is None


def test_infra_report_command_writes_markdown_and_json(
    toy: Toy, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for corpus_id, scale in (("D100", 1.0), ("D1000", 4.0)):
        _write_corpus_files(tmp_path, corpus_id, scale)
        run_dir = _make_run(toy, tmp_path / "runs", f"INF-X-{corpus_id}")
        (run_dir / REPLAY_CHECK_FILE).write_text("identical\n", encoding="utf-8")
    out = tmp_path / "report.md"
    main(
        [
            "infra-report",
            "--ingest-root", str(tmp_path / "ingest"),
            "--probe-root", str(tmp_path / "probe"),
            "--runs-root", str(tmp_path / "runs"),
            "--corpus", "D100", "--corpus", "D1000",
            "--compute-corpus", "D100", "--compute-corpus", "D1000",
            "--run", "x=INF-X-{c}",
            "--out", str(out),
        ]
    )  # fmt: skip
    text = out.read_text(encoding="utf-8")
    assert "## I2" in text and "D1000" in text
    assert out.with_suffix(".json").is_file()
    assert "wrote" in capsys.readouterr().out
