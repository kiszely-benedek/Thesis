"""`resolve()` végponttól végpontig, és a design `kg-construction.md` §5.6 három kapuja.

- **G1** egyenlőség: `resolve(localize(split(plant)))`, eredeti id-kre fordítva,
  megegyezik az eredeti üzemgráffal — minden stratégián és mindkét
  duplikációs rátán.
- **G2** átnevezés: két különböző `localize`-salt ugyanazt a (fordított)
  eredményt adja — a resolver egyetlen döntése sem függhet az occurrence
  id-től.
- **G4** nehezebb dial-ok: a gyengébb feliratozási/számozási konvenciók
  kivétel nélkül lefutnak, és amit a resolver párba tesz, az mindig helyes
  (pontosság 1.0) — a fedettséget itt nem állítjuk, csak jelentjük (§5.2).
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
    """Egy 4-egységes szintetikus üzem — n_units alapértéke (`GeneratorConfig`)."""
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


# --- G1: resolve(localize(split(plant))) == plant, minden stratégián és dup-rátán ---


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


# --- G2: egy másik localize-salt ugyanazt az (eredeti kulcsokra fordított) eredményt adja ---


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


# --- G4: nehezebb dial-ok kivétel nélkül lefutnak, és a pontosság mindig 1.0 ---


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
    resolution, occurrence_map, manifest = _resolve_from_scratch(plant, config)  # nem dob kivételt

    accounted = {pair.from_key for pair in resolution.connector_pairs}
    accounted |= {pair.to_key for pair in resolution.connector_pairs}
    accounted |= {entry.from_key for entry in resolution.unresolved}
    assert len(accounted) == resolution.report.n_connectors, "egy csatlakozó sem tűnhet el csendben"

    predicted_original = {
        _to_original_pair(pair, occurrence_map) for pair in resolution.connector_pairs
    }
    gold_pairs = {frozenset({pair.from_key, pair.to_key}) for pair in manifest.connector_pairs}
    assert predicted_original <= gold_pairs, predicted_original - gold_pairs


# --- design §10 T4b/T1b elfogadás: az importált EX01 lapon 36 csomópont, 0 pár ---
# (T1b előtt 23 csomópontot vártunk — az off-page connector osztályok akkor még kiestek
# importáláskor; ADR-0016 fallbackje óta mind a 36 csomópont megvan, lásd test_proteus_import.py)


def test_resolve_on_the_imported_ex01_sheet() -> None:
    """A generikus fallback (ADR-0016) óta mind a 36 csomópont megvan, a két connector-csomópont
    viszont hivatkozott rajzszám nélkül maradt (§11 OQ1b) — a resolvernek ezt megoldatlanként
    kell jelentenie, sosem kivétellel."""
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    imported = import_proteus_sheet(_EX01_PATH)

    localized, _occurrence_map = localize([imported.sheet])
    resolution = resolve(localized)

    assert resolution.plant.number_of_nodes() == 36
    assert resolution.connector_pairs == []
    assert len(resolution.unresolved) == 2
    assert {entry.reason for entry in resolution.unresolved} == {"no reference label"}
