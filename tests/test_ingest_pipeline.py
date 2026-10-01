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
from plantgraph.eval.graph_equality import graph_differences, to_original_ids, visible_view
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import (
    _MAX_UNMERGED_EXAMPLES,
    build_proteus_corpus,
    build_synthetic_corpus,
    run_proteus,
    run_synthetic,
)
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

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


# --- QA-T0: build_synthetic_corpus / build_proteus_corpus, the one shared path ------------


def test_run_synthetic_tiny_plant_numbers_match_the_pre_qa_t0_refactor() -> None:
    """A golden-value regression check: these numbers were captured before the T0 refactor.

    If a future change to `run_synthetic`'s wiring silently changed what it
    computes, this test — not just "the pipeline still runs" — would catch
    it. `stage_seconds` is excluded: it is wall-clock timing, never repeatable.
    """
    result = _tiny_synthetic(check=True)

    assert result.counts.model_dump() == {
        "n_sheets": 8,
        "n_nodes": 106,
        "n_relationships": 210,
        "n_connector_pairs_predicted": 15,
        "n_unresolved": 0,
    }
    assert result.resolution.model_dump() == {
        "n_sheets": 8,
        "n_occurrences": 97,
        "n_connectors": 30,
        "pairs_by_rule": {"connector_number": 15},
        "unresolved_by_reason": {},
        "n_identity_groups": 0,
        "ambiguous_tag_keys": 0,
        "edge_attribute_conflicts": 0,
    }
    assert result.gate_equal is True


def test_build_synthetic_corpus_reproduces_the_plant_it_was_built_from() -> None:
    """The same check gate G1 runs, but directly against `build_synthetic_corpus`'s own output."""
    generator_config = GeneratorConfig(n_units=4, seed=0)
    split_config = SplitConfig(sheet_equipment_budget=3, seed=0)

    corpus = build_synthetic_corpus(generator_config, split_config)

    actual = to_original_ids(corpus.resolution.plant, corpus.occurrence_map)
    expected = visible_view(corpus.plant)
    assert graph_differences(actual, expected) == []


def test_build_synthetic_corpus_is_deterministic_for_the_same_configuration() -> None:
    """Same config in, same `LoadPlan` and the same occurrence uids out — twice in a row."""
    generator_config = GeneratorConfig(n_units=4, seed=0)
    split_config = SplitConfig(sheet_equipment_budget=3, seed=0)

    first = build_synthetic_corpus(generator_config, split_config)
    second = build_synthetic_corpus(generator_config, split_config)
    first_plan = build_load_plan(_CORPUS_ID, first.localized_sheets, first.resolution)
    second_plan = build_load_plan(_CORPUS_ID, second.localized_sheets, second.resolution)

    assert first_plan.expected_node_labels == second_plan.expected_node_labels
    assert first_plan.expected_relationship_types == second_plan.expected_relationship_types
    assert _all_node_uids(first_plan) == _all_node_uids(second_plan)


def _all_node_uids(plan: LoadPlan) -> set[str]:
    """Every node row's `uid`, across every batched node statement."""
    uids: set[str] = set()
    for statement in plan.node_statements:
        rows = statement.parameters["rows"]
        assert isinstance(rows, list)
        uids.update(row["props"]["uid"] for row in rows)
    return uids


def test_run_synthetic_uses_build_synthetic_corpus_under_the_hood() -> None:
    """`run_synthetic`'s plant/resolution match a direct `build_synthetic_corpus` call.

    Guards against the two ever drifting apart again (design `qa-system.md`
    §18.1 item 1) — this is the failure T0 exists to close.
    """
    generator_config = GeneratorConfig(n_units=4, seed=0)
    split_config = SplitConfig(sheet_equipment_budget=3, seed=0)

    via_run_synthetic = run_synthetic(
        corpus_id=_CORPUS_ID,
        generator_config=generator_config,
        split_config=split_config,
        check=True,
        settings=None,
    )
    corpus = build_synthetic_corpus(generator_config, split_config)

    assert via_run_synthetic.counts.n_sheets == len(corpus.sheets)
    assert via_run_synthetic.resolution == corpus.resolution.report


def test_build_proteus_corpus_matches_run_proteus() -> None:
    path = _ex01_or_skip()

    corpus = build_proteus_corpus(path)
    result = run_proteus(corpus_id="pytest-ingest-ex01-t0", path=path, settings=None)

    assert result.import_report == corpus.imported.report
    assert result.resolution == corpus.resolution.report


# --- gate G1 with inexact tags: an unmerged identity group is reported, not raised --------


def _duplicated_synthetic(*, exact_match_tags: bool) -> IngestResult:
    return run_synthetic(
        corpus_id=_CORPUS_ID,
        generator_config=GeneratorConfig(n_units=4, seed=0),
        split_config=SplitConfig(
            sheet_equipment_budget=3,
            seed=0,
            duplication_rate=0.5,
            exact_match_tags=exact_match_tags,
        ),
        check=True,
        settings=None,
    )


def test_gate_reports_an_unmerged_identity_group_instead_of_crashing() -> None:
    result = _duplicated_synthetic(exact_match_tags=False)

    assert result.gate_equal is False
    assert result.gate_differences[0].startswith("identity group left unmerged:")
    assert "map to several resolved nodes" in result.gate_differences[0]
    # header plus at most the bounded number of examples
    assert 2 <= len(result.gate_differences) <= 1 + _MAX_UNMERGED_EXAMPLES


def test_resolution_score_is_present_when_the_gate_fails() -> None:
    result = _duplicated_synthetic(exact_match_tags=False)

    score = result.resolution_score
    assert score is not None
    assert score.identity.recall is not None
    assert score.identity.recall < 1.0
    assert score.connector_pairs.f1 == 1.0


def test_gate_still_passes_with_exact_tags_and_duplication() -> None:
    result = _duplicated_synthetic(exact_match_tags=True)

    assert result.gate_equal is True
    assert result.gate_differences == []
    assert result.resolution_score is not None
