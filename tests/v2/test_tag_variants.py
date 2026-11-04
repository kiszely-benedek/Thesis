"""The v2 tag-variant generator: operators, invariants, synonym guard, split unchanged (X-T1)."""

from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

import pytest
from plant_v2 import graph_of

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.tag_variants import (
    CLASS_SYNONYMS,
    OPERATORS,
    VariantConfig,
    VariantDraw,
    _Context,
    applicable_operators,
    apply_tag_variants,
    class_uses_code,
    split_equipment_tag,
)
from plantgraph.benchmark.v2.vocabulary import EQUIPMENT_TYPE_CODES
from plantgraph.graph.schema import CLASS_SPECS, EQUIPMENT_CLASSES
from plantgraph.graph.schema_classes import NodeClass
from plantgraph.ingest.headline_v2 import HeadlinePresetV2

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_OPERATOR_NAMES = [operator.name for operator in OPERATORS]


def _apply_one(name: str, tag: str, node_class: str, seed: int = 0) -> str | None:
    """Run one operator by name; None when it does not apply."""
    operator = next(op for op in OPERATORS if op.name == name)
    return operator.apply(_Context(split_equipment_tag(tag), node_class, random.Random(seed)))


# --- each operator on fixed inputs -------------------------------------------------------------


@pytest.mark.parametrize(
    ("operator", "tag", "node_class", "expected"),
    [
        ("drop_separator", "P-1203A", "CentrifugalPump", "P1203A"),
        ("split_number", "P-1203A", "CentrifugalPump", "P-12-03A"),
        ("split_number", "TK-1202", "Tank", "TK-12-02"),
        ("unpad_sequence", "P-1203A", "CentrifugalPump", "P-123A"),
        ("unpad_sequence", "P-1210", "CentrifugalPump", None),  # no leading zero
        ("spare_separator", "P-1203A", "CentrifugalPump", "P-1203-A"),
        ("spare_separator", "P-1203", "CentrifugalPump", None),  # no spare letter
        ("case", "P-1203A", "CentrifugalPump", "p-1203a"),
        ("class_synonym", "P-1203A", "CentrifugalPump", "PU-1203A"),
        ("class_synonym", "E-1201", "TubularHeatExchanger", "HX-1201"),
        ("class_synonym", "K-1201", "CentrifugalCompressor", "C-1201"),
        ("class_synonym", "TK-1201", "Tank", None),  # code not in the table
    ],
)
def test_operator_on_fixed_input(
    operator: str, tag: str, node_class: str, expected: str | None
) -> None:
    assert _apply_one(operator, tag, node_class) == expected


def test_swap_separator_gives_space_or_dot() -> None:
    results = {_apply_one("swap_separator", "P-1203A", "CentrifugalPump", s) for s in range(20)}
    assert results == {"P 1203A", "P.1203A"}


def test_unit_prefix_gives_plain_or_u_prefixed_unit() -> None:
    results = {_apply_one("unit_prefix", "P-1203A", "CentrifugalPump", s) for s in range(20)}
    assert results == {"12-P-03A", "U12-P-03A"}


def test_non_equipment_tag_is_refused() -> None:
    with pytest.raises(ValueError, match="v2 equipment tag"):
        split_equipment_tag("FIC-12014")


# --- invariants over every v2 equipment code ---------------------------------------------------


def _non_zero_digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit() and ch != "0")


def _classes_and_codes() -> list[tuple[str, str]]:
    """Every (equipment class, code it is written with) pair of the v2 vocabulary."""
    pairs = []
    for node_class in sorted(EQUIPMENT_CLASSES):
        for code in sorted(EQUIPMENT_TYPE_CODES):
            if class_uses_code(node_class, code):
                pairs.append((node_class, code))
    return pairs


def test_every_equipment_class_has_a_code_so_the_invariant_sweep_is_not_empty() -> None:
    classes_covered = {node_class for node_class, _ in _classes_and_codes()}
    taggable = {c for c in EQUIPMENT_CLASSES if CLASS_SPECS[NodeClass(c)].tag_prefix is not None}
    assert classes_covered == taggable


@pytest.mark.parametrize("tag_suffix", ["1203A", "1203", "1210", "10002B"])
def test_operators_change_the_tag_and_keep_the_blocking_key(tag_suffix: str) -> None:
    for node_class, code in _classes_and_codes():
        tag = f"{code}-{tag_suffix}"
        for seed in range(4):
            for family in ("format", "naming"):
                for name, variant in applicable_operators(
                    family, tag, node_class, random.Random(seed)
                ):
                    assert variant != tag, (name, tag)
                    assert _non_zero_digits(variant) == _non_zero_digits(tag), (name, tag)


@pytest.mark.parametrize("family", ["format", "naming"])
def test_every_code_has_an_operator_in_each_family(family: str) -> None:
    for node_class, code in _classes_and_codes():
        options = applicable_operators(family, f"{code}-1203A", node_class, random.Random(0))  # type: ignore[arg-type]
        assert options, (family, node_class, code)


# --- synonym guard -----------------------------------------------------------------------------


def test_no_synonym_equals_a_code_its_class_already_uses() -> None:
    for node_class, code in _classes_and_codes():
        options = applicable_operators("naming", f"{code}-1203", node_class, random.Random(0))
        for name, variant in options:
            if name == "class_synonym":
                synonym = variant.split("-")[0]
                assert not class_uses_code(node_class, synonym), (node_class, code, synonym)


def test_pressure_vessel_codes_come_from_the_vocabulary_not_a_hand_list() -> None:
    assert {c for c in "VRD" if class_uses_code("PressureVessel", c)} == {"V", "R", "D"}
    assert not class_uses_code("PressureVessel", "P")


def test_guard_blocks_a_synonym_the_class_already_uses() -> None:
    # `Compressor` is written with C; a (hypothetical) K tag on it must not become C
    assert class_uses_code("Compressor", "C")
    assert _apply_one("class_synonym", "K-1201", "Compressor") is None
    assert _apply_one("class_synonym", "K-1201", "CentrifugalCompressor") == "C-1201"


def test_synonym_table_is_the_accepted_one() -> None:
    assert CLASS_SYNONYMS == {"P": "PU", "E": "HX", "K": "C"}


# --- the transform on a small v2 plant ---------------------------------------------------------


def _split_small_plant() -> tuple[list[SheetGraph], SplitManifest]:
    plant, _ = graph_of(1, 6)
    config = HeadlinePresetV2(duplication_rate=1.0).split_config(seed=11)
    return split(plant, config)


@pytest.fixture(scope="module")
def small_split() -> tuple[list[SheetGraph], SplitManifest]:
    sheets, manifest = _split_small_plant()
    assert manifest.identity_groups, "the small plant must have duplicated equipment"
    return sheets, manifest


def _config(**changes: object) -> VariantConfig:
    return VariantConfig(profile="exp0004", seed=5, **changes)


def _tags(sheets: list[SheetGraph]) -> dict[tuple[str, str], str]:
    return {(s.sheet_id, n): str(a.get("tag")) for s in sheets for n, a in s.graph.nodes(data=True)}


def _without_tag_variants(manifest: SplitManifest) -> dict[str, object]:
    dump = manifest.model_dump(mode="json")
    for group in dump["identity_groups"]:
        group["tag_variants"] = {}
    return dump


def test_manifest_is_equal_modulo_tags(small_split: tuple[list[SheetGraph], SplitManifest]) -> None:
    sheets, manifest = small_split
    _, new_manifest, draws = apply_tag_variants(sheets, manifest, _config())
    assert draws
    assert _without_tag_variants(new_manifest) == _without_tag_variants(manifest)
    for group in new_manifest.identity_groups:
        assert set(group.tag_variants) == set(group.references)  # rate 1.0 varies every reference


def test_only_reference_tags_change_and_inputs_are_untouched(
    small_split: tuple[list[SheetGraph], SplitManifest],
) -> None:
    sheets, manifest = small_split
    before = _tags(sheets)
    new_sheets, new_manifest, draws = apply_tag_variants(sheets, manifest, _config())
    assert _tags(sheets) == before  # input not modified
    changed = {key for key, tag in _tags(new_sheets).items() if tag != before[key]}
    expected = {tuple(draw.reference_key.split(":", 1)) for draw in draws}
    assert changed == expected
    for group in new_manifest.identity_groups:
        for key, variant in group.tag_variants.items():
            sheet_id, node_id = key.split(":", 1)
            assert _tags(new_sheets)[(sheet_id, node_id)] == variant


def test_draws_record_original_and_variant(
    small_split: tuple[list[SheetGraph], SplitManifest],
) -> None:
    sheets, manifest = small_split
    _, _, draws = apply_tag_variants(sheets, manifest, _config(families=("format",)))
    group_tags = {g.tag for g in manifest.identity_groups}
    assert all(isinstance(d, VariantDraw) and d.family == "format" for d in draws)
    assert all(d.original_tag in group_tags and d.variant_tag != d.original_tag for d in draws)


def test_rate_zero_changes_nothing(small_split: tuple[list[SheetGraph], SplitManifest]) -> None:
    sheets, manifest = small_split
    new_sheets, new_manifest, draws = apply_tag_variants(sheets, manifest, _config(rate=0.0))
    assert draws == []
    assert _tags(new_sheets) == _tags(sheets)
    assert new_manifest.model_dump_json() == manifest.model_dump_json()


def test_same_seed_gives_same_bytes(small_split: tuple[list[SheetGraph], SplitManifest]) -> None:
    sheets, manifest = small_split
    first = apply_tag_variants(sheets, manifest, _config())
    second = apply_tag_variants(sheets, manifest, _config())
    assert first[1].model_dump_json() == second[1].model_dump_json()
    assert _tags(first[0]) == _tags(second[0])
    assert [d.model_dump_json() for d in first[2]] == [d.model_dump_json() for d in second[2]]
    other = apply_tag_variants(sheets, manifest, VariantConfig(profile="exp0004", seed=6))
    assert [d.variant_tag for d in other[2]] != [d.variant_tag for d in first[2]]


def test_a_reference_draw_does_not_depend_on_the_other_references(
    small_split: tuple[list[SheetGraph], SplitManifest],
) -> None:
    sheets, manifest = small_split
    _, _, draws = apply_tag_variants(sheets, manifest, _config())
    drop_first_group = manifest.model_copy(update={"identity_groups": manifest.identity_groups[1:]})
    _, _, fewer = apply_tag_variants(sheets, drop_first_group, _config())
    assert [d.model_dump_json() for d in fewer] == [
        d.model_dump_json() for d in draws[-len(fewer) :]
    ]


def test_already_varied_manifest_is_refused(
    small_split: tuple[list[SheetGraph], SplitManifest],
) -> None:
    sheets, manifest = small_split
    _, varied, _ = apply_tag_variants(sheets, manifest, _config())
    with pytest.raises(ValueError, match="exact reference tags"):
        apply_tag_variants(sheets, varied, _config())


def test_config_rejects_empty_or_repeated_families() -> None:
    with pytest.raises(ValueError, match="distinct families"):
        _config(families=())
    with pytest.raises(ValueError, match="distinct families"):
        _config(families=("format", "format"))


# --- the split code is untouched ---------------------------------------------------------------


def test_splitter_is_untouched() -> None:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    result = subprocess.run(
        [git, "diff", "HEAD", "--", "src/plantgraph/benchmark/splitter.py"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"not a git checkout: {result.stderr.strip()}")
    assert result.stdout == ""
