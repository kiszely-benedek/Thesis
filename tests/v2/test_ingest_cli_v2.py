"""`ingest synthetic --headline-v2`: the acceptance command, its flags and a corpus round trip."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plantgraph.ingest import __main__ as ingest_main
from plantgraph.ingest.models import IngestResult
from plantgraph.qa.corpus import load_corpus_artifacts

_ACCEPTANCE = ["synthetic", "--headline-v2", "--target-sheets", "10", "--no-neo4j"]


@pytest.fixture(autouse=True)
def _no_neo4j_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any attempt to read Neo4j settings fails the test: `--no-neo4j` must never get that far."""

    def refuse() -> None:
        raise AssertionError("the run asked for Neo4j settings")

    monkeypatch.setattr(ingest_main, "_settings_from_env_or_raise", refuse)


def _run(argv: list[str], out: Path, capsys: pytest.CaptureFixture[str]) -> IngestResult:
    ingest_main.main([*argv, "--out", str(out)])
    stdout = capsys.readouterr().out.strip()
    assert "\n" not in stdout, "stdout must stay one JSON line"
    return IngestResult.model_validate_json(stdout)


def test_the_acceptance_command_writes_a_ten_sheet_v2_corpus_without_neo4j(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _run(_ACCEPTANCE, tmp_path, capsys)

    assert result.corpus_id == "H10g2"
    assert result.counts.n_sheets == 10
    assert result.counts.n_nodes > 0 and result.counts.n_relationships > 0
    assert result.load_report is None  # nothing was loaded
    assert result.config["generator"]["generator_version"] == "v2"
    assert result.config["split"]["duplication_rate"] == 0.25
    assert (tmp_path / "ingest.json").exists()
    assert (
        json.loads((tmp_path / "ingest.json").read_text(encoding="utf-8"))["corpus_id"] == "H10g2"
    )


def test_a_stored_v2_ingest_json_rebuilds_the_same_corpus_through_the_dispatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _run(
        ["synthetic", "--headline-v2", "--n-units", "3", "--no-neo4j", "--check"], tmp_path, capsys
    )
    assert result.gate_equal is True

    artifacts = load_corpus_artifacts(result.corpus_id, tmp_path / "ingest.json")  # checks counts
    assert artifacts.generator_config is not None
    assert artifacts.generator_config.generator_version == "v2"  # type: ignore[union-attr]


def test_the_headline_duplication_rate_flag_reaches_the_split_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["synthetic", "--headline-v2", "--n-units", "2", "--no-neo4j"]
    result = _run([*argv, "--headline-duplication-rate", "0.0"], tmp_path, capsys)
    assert result.config["split"]["duplication_rate"] == 0.0


def test_a_dev_seed_names_the_corpus_d_and_the_size_search_hits_the_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _run([*_ACCEPTANCE, "--seed", "1"], tmp_path, capsys)
    assert result.corpus_id == "D10g2"
    assert result.counts.n_sheets >= 10


@pytest.mark.parametrize(
    "argv",
    [
        ["synthetic", "--headline", "--headline-v2", "--n-units", "2", "--no-neo4j"],
        ["synthetic", "--target-sheets", "10", "--no-neo4j"],
        ["synthetic", "--headline-v2", "--n-units", "2", "--eq-min", "5", "--no-neo4j"],
    ],
)
def test_conflicting_flags_stop_with_a_message(argv: list[str]) -> None:
    with pytest.raises(SystemExit, match="error"):
        ingest_main.main(argv)


def _ingest_json_without_timings(out: Path, hash_seed: int) -> dict[str, object]:
    env = {**os.environ, "PYTHONHASHSEED": str(hash_seed)}
    command = [sys.executable, "-m", "plantgraph.ingest", *_ACCEPTANCE, "--out", str(out)]
    subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    data = json.loads((out / "ingest.json").read_text(encoding="utf-8"))
    del data["stage_seconds"]
    return data  # type: ignore[no-any-return]


def test_the_ingest_json_is_identical_under_hash_seeds_0_and_999(tmp_path: Path) -> None:
    first = _ingest_json_without_timings(tmp_path / "a", 0)
    second = _ingest_json_without_timings(tmp_path / "b", 999)
    assert first == second
