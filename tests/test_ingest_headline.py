"""The headline preset, the size search and their CLI flags (design realism note §4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.ingest import __main__ as ingest_main
from plantgraph.ingest.headline import (
    HeadlinePreset,
    SizeSearchResult,
    check_realized_sheets,
    smallest_n_units,
)
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import build_synthetic_corpus
from plantgraph.qa.corpus import load_corpus_artifacts

# a small preset so the real builds in these tests stay fast
_SMALL = HeadlinePreset(
    equipment_per_unit_min=4, equipment_per_unit_max=9, sheet_equipment_budget=4
)


def _brute_force_n_units(target_sheets: int, preset: HeadlinePreset, seed: int) -> int:
    """Build ever larger real corpora until one reaches the target — the search's oracle."""
    for n_units in range(1, target_sheets + 1):
        corpus = build_synthetic_corpus(
            preset.generator_config(n_units, seed), preset.split_config(seed)
        )
        if len(corpus.sheets) >= target_sheets:
            return n_units
    raise AssertionError("no corpus reached the target")


@pytest.mark.parametrize("target_sheets", [3, 6, 9])
def test_smallest_n_units_equals_a_brute_force_scan_of_real_builds(target_sheets: int) -> None:
    search = smallest_n_units(target_sheets, _SMALL, seed=0)

    assert search.n_units == _brute_force_n_units(target_sheets, _SMALL, seed=0)
    built = build_synthetic_corpus(
        _SMALL.generator_config(search.n_units, 0), _SMALL.split_config(0)
    )
    assert len(built.sheets) == search.predicted_sheets
    assert search.predicted_sheets >= target_sheets > search.predicted_sheets_one_unit_fewer


def test_smallest_n_units_rejects_a_target_below_one() -> None:
    with pytest.raises(ValueError, match="target_sheets >= 1"):
        smallest_n_units(0, _SMALL, seed=0)


def test_default_preset_holds_the_amended_headline_values() -> None:
    preset = HeadlinePreset()

    assert (preset.equipment_per_unit_min, preset.equipment_per_unit_max) == (18, 36)
    assert (preset.strategy, preset.sheet_equipment_budget) == ("by_unit", 18)
    assert preset.connector_label_detail is ConnectorLabelDetail.DRAWING_ONLY
    assert preset.duplication_rate == 0.25
    assert preset.exact_match_tags is True


def test_generator_defaults_are_unchanged() -> None:
    config = GeneratorConfig()

    assert (config.equipment_per_unit_min, config.equipment_per_unit_max) == (3, 8)


def test_check_realized_sheets_accepts_the_prediction_and_rejects_a_mismatch() -> None:
    search = SizeSearchResult(
        target_sheets=5, n_units=3, predicted_sheets=6, predicted_sheets_one_unit_fewer=4
    )

    check_realized_sheets(search, 6)
    with pytest.raises(ValueError, match="built 5"):
        check_realized_sheets(search, 5)


def test_check_realized_sheets_rejects_a_search_that_was_not_minimal() -> None:
    search = SizeSearchResult(
        target_sheets=5, n_units=3, predicted_sheets=7, predicted_sheets_one_unit_fewer=5
    )

    with pytest.raises(ValueError, match="n_units - 1"):
        check_realized_sheets(search, 7)


# --- the CLI ------------------------------------------------------------------------------


def _run_headline_cli(tmp_path: Path, *extra: str) -> IngestResult:
    ingest_main.main(["synthetic", "--headline", "--no-neo4j", "--out", str(tmp_path), *extra])
    return IngestResult.model_validate_json((tmp_path / "ingest.json").read_text(encoding="utf-8"))


def test_headline_with_n_units_writes_the_preset_values_and_round_trips(tmp_path: Path) -> None:
    written = _run_headline_cli(tmp_path, "--n-units", "2", "--check")

    preset = HeadlinePreset()
    assert written.config["generator"] == preset.generator_config(2, 0).model_dump(mode="json")
    assert written.config["split"] == preset.split_config(0).model_dump(mode="json")
    assert written.gate_equal is True
    # qa/corpus.py rebuilds the same corpus from that file (it checks the counts itself)
    artifacts = load_corpus_artifacts(written.corpus_id, tmp_path / "ingest.json")
    assert artifacts.load_plan_counts == written.counts
    assert artifacts.split_config == preset.split_config(0)


def test_headline_with_target_sheets_runs_the_search(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    written = _run_headline_cli(tmp_path, "--target-sheets", "3")

    search = smallest_n_units(3, HeadlinePreset(), seed=0)
    assert written.config["generator"]["n_units"] == search.n_units
    assert written.counts.n_sheets == search.predicted_sheets >= 3
    assert "size search" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["--headline"],  # neither size flag
        ["--headline", "--n-units", "2", "--target-sheets", "3"],  # both
        ["--target-sheets", "3"],  # search without the preset
        ["--headline", "--n-units", "2", "--eq-min", "5"],  # range clashes with the preset
    ],
)
def test_conflicting_size_flags_are_refused(argv: list[str]) -> None:
    with pytest.raises(SystemExit, match="error"):
        ingest_main.main(["synthetic", "--no-neo4j", *argv])


def test_eq_flags_override_the_generator_range_without_headline(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ingest_main.main(
        ["synthetic", "--n-units", "2", "--eq-min", "5", "--eq-max", "6", "--no-neo4j"]
    )

    generator = json.loads(capsys.readouterr().out)["config"]["generator"]
    assert (generator["equipment_per_unit_min"], generator["equipment_per_unit_max"]) == (5, 6)


def test_split_config_round_trips_through_json() -> None:
    config = HeadlinePreset().split_config(3)

    assert SplitConfig.model_validate_json(config.model_dump_json()) == config
