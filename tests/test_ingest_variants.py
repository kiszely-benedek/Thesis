"""EXP-0004 wiring (X-T4): tag variants and identity links through ingest, default-off.

The golden test is the freeze-E8 proof (design `exp0004-v2.md` section 8, point 4): a v2 corpus
ingested with none of the new options gives the same `ingest.json` bytes as before the wiring
existed (stage seconds excepted). The pinned hash was taken on the code before X-T4.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from identity_oracle import oracle_links
from plantgraph.benchmark.tag_variants import VariantConfig
from plantgraph.ingest import __main__ as ingest_main
from plantgraph.ingest.headline_v2 import HeadlinePresetV2
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus, run_synthetic
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.resolution.identity_links import IdentityLinkSet
from plantgraph.store.neo4j_plan import build_load_plan

_SEED = 1
_N_UNITS = 6  # 10 sheets, 11 identity groups: small, but references exist
_PRESET = HeadlinePresetV2(duplication_rate=1.0)
_GENERATOR = _PRESET.generator_config(_N_UNITS, _SEED)
_SPLIT = _PRESET.split_config(_SEED)
_VARIANTS = VariantConfig(profile="exp0004", seed=_SEED)

# sha256 of the default-path IngestResult JSON (indent=2, stage_seconds emptied) before X-T4
_DEFAULT_GOLDEN_SHA256 = "799f378e3890e244f824e582b6462e16d8139b19add024d43f896cff287ffa26"


@pytest.fixture(scope="module")
def variant_corpus() -> SyntheticCorpus:
    """Variants on, exact-tag resolver (decider D0): every reference stays unmerged."""
    return build_synthetic_corpus(_GENERATOR, _SPLIT, _VARIANTS)


def test_default_path_is_byte_identical_to_the_pre_wiring_golden() -> None:
    result = run_synthetic(
        corpus_id="golden-v2",
        generator_config=_GENERATOR,
        split_config=_SPLIT,
        check=True,
        settings=None,
        store_profile="plant",
    )
    text = result.model_copy(update={"stage_seconds": {}}).model_dump_json(indent=2)

    assert hashlib.sha256(text.encode()).hexdigest() == _DEFAULT_GOLDEN_SHA256
    assert set(result.config) == {"generator", "split"}  # no variants / identity keys


def test_default_corpus_has_no_variant_stage_and_no_draws() -> None:
    corpus = build_synthetic_corpus(_GENERATOR, _SPLIT)

    assert "variants" not in corpus.stage_seconds
    assert corpus.variant_draws == []


def test_variants_with_the_exact_resolver_leave_one_unmerged_item_per_reference_group(
    variant_corpus: SyntheticCorpus,
) -> None:
    result = _run_with_variants(None)
    n_groups = len(variant_corpus.manifest.identity_groups)

    assert result.gate_equal is False
    assert f"identity group left unmerged: {n_groups} original items" in result.gate_differences[0]
    assert result.config["variants"] == _VARIANTS.model_dump(mode="json")
    assert "identity" not in result.config


def test_oracle_links_restore_the_gate(variant_corpus: SyntheticCorpus, tmp_path: Path) -> None:
    link_file = _write_links(oracle_links(variant_corpus), tmp_path)

    result = _run_with_variants(link_file)

    assert result.gate_equal is True
    assert result.gate_differences == []
    assert set(result.config["identity"]) == {"path", "sha256"}


def test_plant_profile_load_plan_builds_for_variants_with_d0(
    variant_corpus: SyntheticCorpus,
) -> None:
    # unmerged references are orphans without a unit_id; the plant profile must still build
    plan = build_load_plan(
        "variants-d0", variant_corpus.localized_sheets, variant_corpus.resolution, profile="plant"
    )

    assert plan.node_statements


def test_rebuild_honours_variants_and_links_and_refuses_a_changed_link_file(
    variant_corpus: SyntheticCorpus, tmp_path: Path
) -> None:
    link_file = _write_links(oracle_links(variant_corpus), tmp_path)
    result = _run_with_variants(link_file)
    ingest_json = tmp_path / "ingest.json"
    ingest_json.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    rebuilt = load_corpus_artifacts(result.corpus_id, ingest_json)  # counts must match
    assert rebuilt.resolution.report.n_identity_groups == result.resolution.n_identity_groups

    link_file.write_text(link_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        load_corpus_artifacts(result.corpus_id, ingest_json)


def test_cli_variant_flags_build_a_config_and_default_to_none() -> None:
    off = ingest_main._parse_args(["synthetic", "--n-units", "4"])
    on = ingest_main._parse_args(
        [
            "synthetic",
            "--n-units",
            "4",
            "--seed",
            "7",
            "--tag-variants",
            "--variant-families",
            "format",
        ]
        + ["--variant-rate", "0.5"]
    )

    assert ingest_main._variant_config_from_flags(off) is None
    assert off.identity_links is None
    config = ingest_main._variant_config_from_flags(on)
    assert config == VariantConfig(profile="exp0004", families=("format",), rate=0.5, seed=7)


def test_cli_refuses_variant_options_without_the_switch() -> None:
    args = ingest_main._parse_args(["synthetic", "--n-units", "4", "--variant-rate", "0.5"])

    with pytest.raises(SystemExit, match="--tag-variants"):
        ingest_main._variant_config_from_flags(args)


def _run_with_variants(link_file: Path | None) -> IngestResult:
    return run_synthetic(
        corpus_id="variants-test",
        generator_config=_GENERATOR,
        split_config=_SPLIT,
        check=True,
        settings=None,
        store_profile="plant",
        variants=_VARIANTS,
        identity_links_path=link_file,
    )


def _write_links(links: IdentityLinkSet, directory: Path) -> Path:
    path = directory / "links.json"
    path.write_text(links.model_dump_json(indent=2), encoding="utf-8")
    return path
