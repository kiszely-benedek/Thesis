"""`--store-profile`: CLI default, `IngestResult` fields, and the qa rebuild matching the load."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.ingest import __main__ as ingest_main
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.qa.corpus import load_corpus_artifacts

_GENERATOR_CONFIG = GeneratorConfig(n_units=4, seed=0)
_SPLIT_CONFIG = SplitConfig(sheet_equipment_budget=3, seed=0, duplication_rate=0.5)


def _run(profile: str) -> IngestResult:
    return run_synthetic(
        corpus_id="pytest-store-profile",
        generator_config=_GENERATOR_CONFIG,
        split_config=_SPLIT_CONFIG,
        check=False,
        settings=None,
        store_profile=profile,  # type: ignore[arg-type]
    )


def test_the_cli_default_is_both_for_synthetic_and_proteus() -> None:
    synthetic = ingest_main._parse_args(["synthetic", "--n-units", "4"])
    proteus = ingest_main._parse_args(["proteus", "some.xml"])
    assert synthetic.store_profile == "both"
    assert proteus.store_profile == "both"


def test_the_cli_rejects_an_unknown_profile() -> None:
    with pytest.raises(SystemExit):
        ingest_main._parse_args(["synthetic", "--n-units", "4", "--store-profile", "merged"])


def test_the_pipeline_default_stays_occurrence() -> None:
    result = run_synthetic(
        corpus_id="pytest-store-profile",
        generator_config=_GENERATOR_CONFIG,
        split_config=_SPLIT_CONFIG,
        check=False,
        settings=None,
    )
    assert result.store_profile == "occurrence"


def test_occurrence_layer_counts_have_no_items() -> None:
    layers = _run("occurrence").layer_counts
    assert layers is not None
    assert (layers.n_plant_items, layers.n_drawn_as, layers.n_invariants) == (0, 0, 0)
    assert layers.n_occurrences > 0


def test_plant_layer_counts_have_no_occurrences() -> None:
    layers = _run("plant").layer_counts
    assert layers is not None
    assert layers.n_occurrences == 0
    assert layers.n_plant_items > 0
    assert layers.n_drawn_as == 0
    assert layers.n_invariants == 2


def test_both_layer_counts_add_up_and_link_every_occurrence_but_paired_stubs() -> None:
    result = _run("both")
    layers = result.layer_counts
    assert layers is not None
    assert layers.n_invariants == 7
    total = layers.n_occurrences + layers.n_plant_items + layers.n_structure_nodes
    assert total == result.counts.n_nodes
    paired_stubs = 2 * result.counts.n_connector_pairs_predicted
    assert layers.n_drawn_as == layers.n_occurrences - paired_stubs


def test_the_occurrence_node_count_is_the_same_in_every_profile() -> None:
    occurrence = _run("occurrence").layer_counts
    both = _run("both").layer_counts
    assert occurrence is not None
    assert both is not None
    assert both.n_occurrences == occurrence.n_occurrences


def test_the_qa_rebuild_uses_the_recorded_profile(tmp_path: Path) -> None:
    """A `both` ingest.json must rebuild a `both` plan, or its counts could never match."""
    result = _run("both")
    ingest_json_path = tmp_path / "ingest.json"
    ingest_json_path.write_text(result.model_dump_json(), encoding="utf-8")

    artifacts = load_corpus_artifacts("pytest-store-profile", ingest_json_path)

    assert artifacts.load_plan.profile == "both"
    assert artifacts.load_plan_counts == result.counts


def test_an_old_ingest_json_without_the_new_fields_reads_back_as_occurrence() -> None:
    payload = _run("occurrence").model_dump(exclude={"store_profile", "layer_counts"})
    old = IngestResult.model_validate(payload)
    assert old.store_profile == "occurrence"
    assert old.layer_counts is None
