"""`qa.corpus.load_corpus_artifacts` — rebuilding a corpus from a saved `ingest.json` (QA-T0).

The round trip is the main property under test: writing an `IngestResult` to
disk with `--out` and reading it back with `load_corpus_artifacts` must give
the same plant, manifest, sheets and resolution a fresh in-memory build would
(`qa-system.md` §18.1 item 1) — never a re-implementation that could drift.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.eval.graph_equality import graph_differences
from plantgraph.ingest.__main__ import main as ingest_main
from plantgraph.ingest.pipeline import build_proteus_corpus, build_synthetic_corpus, run_synthetic
from plantgraph.qa.corpus import load_corpus_artifacts

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

_GENERATOR_CONFIG = GeneratorConfig(n_units=4, seed=0)
_SPLIT_CONFIG = SplitConfig(sheet_equipment_budget=3, seed=0)


def _write_synthetic_ingest_json(corpus_id: str, out_dir: Path) -> None:
    ingest_main(
        [
            "synthetic",
            "--n-units",
            str(_GENERATOR_CONFIG.n_units),
            "--budget",
            str(_SPLIT_CONFIG.sheet_equipment_budget),
            "--seed",
            str(_GENERATOR_CONFIG.seed),
            "--corpus-id",
            corpus_id,
            "--no-neo4j",
            "--check",
            "--out",
            str(out_dir),
        ]
    )


def test_round_trips_a_synthetic_corpus(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    corpus_id = "pytest-qa-corpus-synthetic"
    _write_synthetic_ingest_json(corpus_id, tmp_path)
    capsys.readouterr()  # discard stdout; only the file matters here
    fresh = build_synthetic_corpus(_GENERATOR_CONFIG, _SPLIT_CONFIG)

    artifacts = load_corpus_artifacts(corpus_id, tmp_path / "ingest.json")

    assert artifacts.corpus_id == corpus_id
    assert artifacts.generator_config == _GENERATOR_CONFIG
    assert artifacts.split_config == _SPLIT_CONFIG
    assert artifacts.source_path is None
    assert graph_differences(artifacts.gold.plant, fresh.plant) == []
    # `created_at` is a wall-clock timestamp (`SplitManifest`'s default factory) and is the one
    # field two otherwise-identical builds can never share; everything else must match exactly.
    assert artifacts.gold.manifest is not None
    assert fresh.manifest is not None
    assert (
        artifacts.gold.manifest.model_copy(update={"created_at": fresh.manifest.created_at})
        == fresh.manifest
    )
    assert artifacts.gold.occurrence_map == fresh.occurrence_map
    assert [sheet.sheet_id for sheet in artifacts.localized_sheets] == [
        sheet.sheet_id for sheet in fresh.localized_sheets
    ]
    assert artifacts.resolution.report == fresh.resolution.report
    assert graph_differences(artifacts.resolution.plant, fresh.resolution.plant) == []
    assert artifacts.load_plan.corpus_id == corpus_id


def test_load_plan_counts_match_the_saved_ingest_json(tmp_path: Path) -> None:
    corpus_id = "pytest-qa-corpus-counts"
    result = run_synthetic(
        corpus_id=corpus_id,
        generator_config=_GENERATOR_CONFIG,
        split_config=_SPLIT_CONFIG,
        check=True,
        settings=None,
    )
    ingest_json_path = tmp_path / "ingest.json"
    ingest_json_path.write_text(result.model_dump_json(), encoding="utf-8")

    artifacts = load_corpus_artifacts(corpus_id, ingest_json_path)

    assert artifacts.load_plan_counts == result.counts


def test_refuses_a_mismatched_corpus_id(tmp_path: Path) -> None:
    result = run_synthetic(
        corpus_id="pytest-qa-corpus-actual",
        generator_config=_GENERATOR_CONFIG,
        split_config=_SPLIT_CONFIG,
        check=False,
        settings=None,
    )
    ingest_json_path = tmp_path / "ingest.json"
    ingest_json_path.write_text(result.model_dump_json(), encoding="utf-8")

    with pytest.raises(ValueError, match="pytest-qa-corpus-actual"):
        load_corpus_artifacts("pytest-qa-corpus-expected", ingest_json_path)


def test_refuses_a_stale_ingest_json(tmp_path: Path) -> None:
    """A hand-tampered `counts` field must be caught, not silently trusted."""
    corpus_id = "pytest-qa-corpus-stale"
    result = run_synthetic(
        corpus_id=corpus_id,
        generator_config=_GENERATOR_CONFIG,
        split_config=_SPLIT_CONFIG,
        check=False,
        settings=None,
    )
    payload = json.loads(result.model_dump_json())
    payload["counts"]["n_nodes"] = payload["counts"]["n_nodes"] + 1
    ingest_json_path = tmp_path / "ingest.json"
    ingest_json_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="rebuilding the corpus"):
        load_corpus_artifacts(corpus_id, ingest_json_path)


def test_round_trips_a_proteus_corpus(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    corpus_id = "pytest-qa-corpus-ex01"
    ingest_main(
        ["proteus", str(_EX01_PATH), "--corpus-id", corpus_id, "--no-neo4j", "--out", str(tmp_path)]
    )
    capsys.readouterr()
    fresh = build_proteus_corpus(_EX01_PATH)

    artifacts = load_corpus_artifacts(corpus_id, tmp_path / "ingest.json")

    assert artifacts.generator_config is None
    assert artifacts.split_config is None
    assert artifacts.source_path == str(_EX01_PATH)
    assert artifacts.gold.plant is None
    assert artifacts.gold.manifest is None
    assert artifacts.gold.occurrence_map == fresh.occurrence_map
    assert [sheet.sheet_id for sheet in artifacts.localized_sheets] == [
        sheet.sheet_id for sheet in fresh.localized_sheets
    ]
    assert artifacts.resolution.report == fresh.resolution.report
