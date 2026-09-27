"""`run_synthetic` / `run_proteus` — pure orchestration, called with `settings=None` (no Neo4j).

The CLI's own argument parsing and printing are covered separately
(`test_ingest_cli.py`); this module only checks the pipeline functions
themselves, the way any other caller (e.g. a future experiment script) would
use them (design `kg-construction.md` §8, T8 acceptance: "a pipeline test
calls `run_synthetic` without Neo4j").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import run_proteus, run_synthetic

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

_CORPUS_ID = "pytest-ingest-pipeline"


def _tiny_synthetic(*, check: bool) -> IngestResult:
    return run_synthetic(
        corpus_id=_CORPUS_ID,
        generator_config=GeneratorConfig(n_units=4, seed=0),
        split_config=SplitConfig(sheet_equipment_budget=3, seed=0),
        check=check,
        settings=None,
    )


def test_run_synthetic_without_neo4j_and_with_check_passes_the_gate() -> None:
    result = _tiny_synthetic(check=True)

    assert result.gate_equal is True
    assert result.gate_differences == []
    assert result.resolution_score is not None
    assert result.load_report is None
    assert result.neo4j_version is None


def test_run_synthetic_without_check_leaves_the_gate_unset() -> None:
    result = _tiny_synthetic(check=False)

    assert result.gate_equal is None
    assert result.resolution_score is None
    assert "check" not in result.stage_seconds


def test_run_synthetic_stage_seconds_cover_every_pipeline_step_but_no_load_steps() -> None:
    result = _tiny_synthetic(check=True)

    assert set(result.stage_seconds) == {
        "generate",
        "split",
        "localize",
        "resolve",
        "check",
        "plan",
    }
    assert all(seconds >= 0 for seconds in result.stage_seconds.values())


def test_run_synthetic_counts_match_an_independent_tally() -> None:
    """Recomputed from scratch, not from the plan the pipeline itself built — a real cross-check."""
    result = _tiny_synthetic(check=True)

    # a corpus and sheet node each, plus one node per occurrence — see neo4j_plan.py's store shape
    assert result.counts.n_sheets > 0
    assert result.counts.n_nodes == result.resolution.n_occurrences + result.counts.n_sheets + 1
    assert result.counts.n_connector_pairs_predicted == sum(
        result.resolution.pairs_by_rule.values()
    )
    assert result.counts.n_unresolved == sum(result.resolution.unresolved_by_reason.values())


def _ex01_or_skip() -> Path:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    return _EX01_PATH


def test_run_proteus_without_neo4j_has_no_gate_but_has_an_import_report() -> None:
    path = _ex01_or_skip()

    result = run_proteus(corpus_id="pytest-ingest-ex01", path=path, settings=None)

    assert result.gate_equal is None
    assert result.resolution_score is None
    assert result.import_report is not None
    assert result.load_report is None
    assert set(result.stage_seconds) == {"import", "localize", "resolve", "plan"}
