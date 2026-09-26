"""`resolve()` end to end, and the three gate checks of design `kg-construction.md` §5.6.

- **G1** equality: `resolve(localize(split(plant)))`, translated back to
  original ids, matches the original plant graph — across every strategy and
  both duplication rates.
- **G2** renaming: two different `localize` salts give the same (translated)
  result — none of the resolver's decisions may depend on the occurrence id.
- **G4** harder dials: the weaker labelling/numbering conventions run to
  completion without exception, and whatever the resolver pairs is always
  correct (precision 1.0) — coverage is not asserted here, only reported (§5.2).
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plant_fixtures import make_plant_graph
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import (
    ConnectorPair,
    IdentityGroup,
    SplitManifest,
    UnresolvedConnector,
)
from plantgraph.benchmark.split_models import ConnectorLabelDetail, NumberingScheme, SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.strategies import STRATEGIES
from plantgraph.eval.graph_equality import graph_differences, to_original_ids, visible_view
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.models import Resolution
from plantgraph.resolution.resolver import resolve

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"


def _generated_plant(seed: int = 8) -> nx.DiGraph[str]:
    """A 4-unit synthetic plant — the default of n_units (`GeneratorConfig`)."""
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


def _resolve_from_scratch(
    plant: nx.DiGraph[str], config: SplitConfig, salt: str = ""
) -> tuple[Resolution, OccurrenceMap, SplitManifest]:
    sheets, manifest = split(plant, config)
    localized, occurrence_map = localize(sheets, salt=salt)
    return resolve(localized), occurrence_map, manifest


# --- G1: resolve(localize(split(plant))) == plant, across every strategy and duplication rate ---


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_g1_on_the_hand_built_fixture(strategy_name: str, duplication_rate: float) -> None:
    plant = make_plant_graph(chain_length=6, branches=2, utility_fanout=6)
    config = SplitConfig(
        strategy=strategy_name, sheet_equipment_budget=2, seed=7, duplication_rate=duplication_rate
    )
    _assert_g1(plant, config)


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_g1_on_a_generated_plant(strategy_name: str, duplication_rate: float) -> None:
    plant = _generated_plant()
    config = SplitConfig(
        strategy=strategy_name, sheet_equipment_budget=3, seed=0, duplication_rate=duplication_rate
    )
    _assert_g1(plant, config)


def _assert_g1(plant: nx.DiGraph[str], config: SplitConfig) -> None:
    resolution, occurrence_map, _manifest = _resolve_from_scratch(plant, config)
    actual = to_original_ids(resolution.plant, occurrence_map)
    expected = visible_view(plant)
    differences = graph_differences(actual, expected)
    assert differences == [], differences


# --- G2: a different localize salt gives the same (translated-to-original-keys) result ---


def test_g2_a_different_salt_gives_the_same_resolution_up_to_the_mapping() -> None:
    plant = _generated_plant()
    config = SplitConfig(sheet_equipment_budget=3, seed=0, duplication_rate=0.5)
    sheets, _manifest = split(plant, config)

    plain, plain_map = localize(sheets, salt="")
    salted, salted_map = localize(sheets, salt="renamed")
    plain_resolution = resolve(plain)
    salted_resolution = resolve(salted)

    plain_plant = to_original_ids(plain_resolution.plant, plain_map)
    salted_plant = to_original_ids(salted_resolution.plant, salted_map)
    assert graph_differences(salted_plant, plain_plant) == []

    assert _mapped_pairs(plain_resolution.connector_pairs, plain_map) == _mapped_pairs(
        salted_resolution.connector_pairs, salted_map
    )
    assert _mapped_groups(plain_resolution.identity_groups, plain_map) == _mapped_groups(
        salted_resolution.identity_groups, salted_map
    )
    assert _mapped_unresolved(plain_resolution.unresolved, plain_map) == _mapped_unresolved(
        salted_resolution.unresolved, salted_map
    )


def _mapped_pairs(
    pairs: list[ConnectorPair], occurrence_map: OccurrenceMap
) -> set[tuple[str, str, str]]:
    return {
        (
            occurrence_map.original_key(pair.from_key),
            occurrence_map.original_key(pair.to_key),
            pair.match_rule.value,
        )
        for pair in pairs
    }


def _mapped_groups(
    groups: list[IdentityGroup], occurrence_map: OccurrenceMap
) -> set[tuple[str, frozenset[str]]]:
    return {
        (
            occurrence_map.original_key(group.home),
            frozenset(occurrence_map.original_key(reference) for reference in group.references),
        )
        for group in groups
    }


def _mapped_unresolved(
    unresolved: list[UnresolvedConnector], occurrence_map: OccurrenceMap
) -> set[tuple[str, str]]:
    return {(occurrence_map.original_key(entry.from_key), entry.reason) for entry in unresolved}


# --- G4: harder dials run to completion without exception, and precision is always 1.0 ---


def _to_original_pair(pair: ConnectorPair, occurrence_map: OccurrenceMap) -> frozenset[str]:
    return frozenset(
        {occurrence_map.original_key(pair.from_key), occurrence_map.original_key(pair.to_key)}
    )


@pytest.mark.parametrize(
    "config",
    [
        SplitConfig(
            sheet_equipment_budget=3,
            seed=0,
            connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY,
        ),
        SplitConfig(sheet_equipment_budget=3, seed=0, duplication_rate=0.5, exact_match_tags=False),
        SplitConfig(sheet_equipment_budget=3, seed=0, numbering_scheme=NumberingScheme.PID_STYLE),
        SplitConfig(sheet_equipment_budget=3, seed=0, use_grid_reference=True),
    ],
    ids=["drawing_only", "exact_match_tags_false", "pid_style", "grid_reference"],
)
def test_g4_harder_dials_run_to_completion_with_perfect_pair_precision(config: SplitConfig) -> None:
    plant = _generated_plant()
    resolution, occurrence_map, manifest = _resolve_from_scratch(plant, config)  # does not raise

    accounted = {pair.from_key for pair in resolution.connector_pairs}
    accounted |= {pair.to_key for pair in resolution.connector_pairs}
    accounted |= {entry.from_key for entry in resolution.unresolved}
    assert len(accounted) == resolution.report.n_connectors, "egy csatlakozó sem tűnhet el csendben"

    predicted_original = {
        _to_original_pair(pair, occurrence_map) for pair in resolution.connector_pairs
    }
    gold_pairs = {frozenset({pair.from_key, pair.to_key}) for pair in manifest.connector_pairs}
    assert predicted_original <= gold_pairs, predicted_original - gold_pairs


# --- design §10 T4b/T1b acceptance: the imported EX01 sheet has 36 nodes, 0 pairs ---
# (before T1b we expected 23 nodes — the off-page connector classes used to be dropped
# on import back then; since ADR-0016's fallback, all 36 nodes are present (test_proteus_import.py)


def test_resolve_on_the_imported_ex01_sheet() -> None:
    """Since the generic fallback (ADR-0016), all 36 nodes are present, but the two connector
    nodes are left without a referenced drawing number (§11 OQ1b) — the resolver must report
    this as unresolved, never with an exception."""
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    imported = import_proteus_sheet(_EX01_PATH)

    localized, _occurrence_map = localize([imported.sheet])
    resolution = resolve(localized)

    assert resolution.plant.number_of_nodes() == 36
    assert resolution.connector_pairs == []
    assert len(resolution.unresolved) == 2
    assert {entry.reason for entry in resolution.unresolved} == {"no reference label"}
