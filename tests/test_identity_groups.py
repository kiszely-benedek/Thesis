"""Invariants of identity-based cross-referencing (IdentityGroup) — splitter.md open question 3.

This is the benchmark's other half besides the off-page connector: instead of a
cut edge, it describes a node drawn twice. The round-trip test (see
test_splitter.py) cannot check this half structurally, because
_copy_sheet_into (rejoin.py) deliberately discards a reference occurrence's
attributes and the home occurrence supplies them back — so a wrong tag,
node_class, or tag_variants on the reference side would leave the round-trip
test green regardless. That is why we must look directly at the IdentityGroups
and the sheets' contents.
"""

from __future__ import annotations

import random

from plant_fixtures import make_plant_graph
from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.strategies import STRATEGIES


def _split_with_full_duplication(
    exact_match_tags: bool = True,
) -> tuple[object, list[SheetGraph], SplitManifest, SplitConfig]:
    """duplication_rate=1.0: every eligible equipment gets duplicated, so the list is non-empty."""
    plant = make_plant_graph(chain_length=6, branches=2, utility_fanout=6)
    config = SplitConfig(
        sheet_equipment_budget=2, seed=17, duplication_rate=1.0, exact_match_tags=exact_match_tags
    )
    sheets, manifest = split(plant, config)
    return plant, sheets, manifest, config


def _sheet_by_id(sheets: list[SheetGraph], sheet_id: str) -> SheetGraph:
    return next(sheet for sheet in sheets if sheet.sheet_id == sheet_id)


def test_reference_occurrence_carries_only_tag_and_node_class() -> None:
    # splitter.md open question 3: home = full attributes, reference = "the tag
    # and little else". 'manufacturer' appears only on the home in the fixture —
    # if a reference got it too, this assert would fail.
    plant, sheets, manifest, _ = _split_with_full_duplication()
    assert manifest.identity_groups, "the fixture must produce at least one identity group"
    for group in manifest.identity_groups:
        home_node_id = group.home.split(":", 1)[1]
        assert "manufacturer" in plant.nodes[home_node_id]
        for reference in group.references:
            sheet_id, node_id = reference.split(":", 1)
            reference_attrs = _sheet_by_id(sheets, sheet_id).graph.nodes[node_id]
            assert set(reference_attrs) == {"tag", "node_class"}


def test_tag_variants_populated_and_differ_from_home_when_not_exact_match() -> None:
    _, sheets, manifest, _ = _split_with_full_duplication(exact_match_tags=False)
    assert manifest.identity_groups
    for group in manifest.identity_groups:
        # every reference's tag differs from the home tag — this is the "must not
        # be trivially matchable" requirement (splitter.md open question 3)
        assert set(group.tag_variants) == set(group.references)
        for reference in group.references:
            sheet_id, node_id = reference.split(":", 1)
            reference_tag = _sheet_by_id(sheets, sheet_id).graph.nodes[node_id]["tag"]
            assert reference_tag == group.tag_variants[reference]
            assert reference_tag != group.tag


def test_tag_variants_empty_and_tags_exact_when_exact_match_enabled() -> None:
    _, sheets, manifest, _ = _split_with_full_duplication(exact_match_tags=True)
    assert manifest.identity_groups
    for group in manifest.identity_groups:
        assert group.tag_variants == {}
        for reference in group.references:
            sheet_id, node_id = reference.split(":", 1)
            reference_tag = _sheet_by_id(sheets, sheet_id).graph.nodes[node_id]["tag"]
            assert reference_tag == group.tag


def test_identity_group_shape_is_a_usable_gold_set() -> None:
    _, sheets, manifest, _ = _split_with_full_duplication()
    assert manifest.identity_groups
    for group in manifest.identity_groups:
        home_sheet_id, home_node_id = group.home.split(":", 1)
        reference_sheets = [reference.split(":", 1)[0] for reference in group.references]

        # the home's sheet differs from every reference's sheet
        assert home_sheet_id not in reference_sheets
        # at most one occurrence of the same group appears on a given sheet
        assert len(reference_sheets) == len(set(reference_sheets))
        # every occurrence key points to a real node on the sheet it names
        assert home_node_id in _sheet_by_id(sheets, home_sheet_id).graph.nodes
        for reference in group.references:
            sheet_id, node_id = reference.split(":", 1)
            assert node_id in _sheet_by_id(sheets, sheet_id).graph.nodes


def test_duplication_rate_zero_yields_no_identity_groups() -> None:
    plant = make_plant_graph(chain_length=6, branches=2, utility_fanout=6)
    config = SplitConfig(sheet_equipment_budget=2, seed=17, duplication_rate=0.0)
    _, manifest = split(plant, config)
    assert manifest.identity_groups == []


def test_duplication_rate_one_selects_exactly_the_eligible_equipment() -> None:
    # duplication_rate=1.0 must duplicate every piece of equipment that has a
    # neighbour on another sheet — no more, no fewer.
    plant, _, manifest, config = _split_with_full_duplication()
    node_sheet = STRATEGIES[config.strategy](plant, config, random.Random(config.seed))

    eligible = set()
    for node_id, attrs in plant.nodes(data=True):
        if attrs.get("node_class") not in config.equipment_classes:
            continue
        neighbours = set(plant.predecessors(node_id)) | set(plant.successors(node_id))
        if any(node_sheet[neighbour] != node_sheet[node_id] for neighbour in neighbours):
            eligible.add(node_id)

    duplicated = {group.home.split(":", 1)[1] for group in manifest.identity_groups}
    assert duplicated == eligible
