"""`qa.questions.evidence` — the connector cut, `k`, `evidence_sheets`, `evidence_tags` (QA-T6)."""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.benchmark.models import IdentityGroup, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.questions.evidence import (
    Crossings,
    Evidence,
    SheetIndex,
    connector_cut,
    crossings,
    evidence_sheets,
    evidence_tags,
)
from plantgraph.qa.questions.families_flow import flow_path_candidates
from qa_toy_plant import (
    CUT_EDGES,
    N_ACTUATOR,
    N_CONTROLLER,
    N_PUMP,
    N_SENSOR,
    N_TANK,
    N_TANK_U2,
    N_VALVE,
    N_VESSEL,
    SHEET_1,
    SHEET_2,
    TAG_LOOP,
    TAG_PUMP,
    TAG_TANK,
    TAG_VALVE,
    build_toy_manifest,
    build_toy_plant,
    build_toy_sheets,
)


def test_connector_cut_reconstructs_the_hand_chosen_cut() -> None:
    manifest = build_toy_manifest()

    assert connector_cut(manifest) == CUT_EDGES


def test_connector_cut_ignores_pairs_with_no_original_edge() -> None:
    """An OPEN100-sourced pair has no `original_edge`; it must not silently count as a cut."""
    manifest = build_toy_manifest()
    manifest.connector_pairs[0] = manifest.connector_pairs[0].model_copy(
        update={"original_edge": None}
    )

    assert manifest.connector_pairs[0].original_edge is None
    assert len(connector_cut(manifest)) == len(CUT_EDGES) - 1


def _duplicated_valve_toy() -> tuple[nx.DiGraph[str], list[SheetGraph], SplitManifest]:
    """The toy plant with VALVE also drawn on S1 (home S2), so TANK->VALVE needs no connector.

    The duplication replaces that one cut edge: S1 now holds a reference
    occurrence of VALVE beside TANK, and the manifest records the identity
    group instead of a connector pair for the edge.
    """
    plant = build_toy_plant()
    sheets = build_toy_sheets(plant)
    sheet_1 = next(sheet for sheet in sheets if sheet.sheet_id == SHEET_1)
    sheet_1.graph.add_node(N_VALVE, **plant.nodes[N_VALVE])
    manifest = build_toy_manifest()
    manifest.connector_pairs = [
        pair for pair in manifest.connector_pairs if pair.original_edge != (N_TANK, N_VALVE)
    ]
    manifest.identity_groups = [
        IdentityGroup(
            tag=TAG_VALVE, home=f"{SHEET_2}:{N_VALVE}", references=[f"{SHEET_1}:{N_VALVE}"]
        )
    ]
    return plant, sheets, manifest


def test_crossings_on_a_plant_with_one_duplicated_item_match_the_hand_count() -> None:
    plant, sheets, manifest = _duplicated_valve_toy()
    index = SheetIndex.from_sheets(sheets, manifest)
    # TANK->VALVE: homes S1/S2, resolved by the duplicate (identity). SENSOR->CONTROLLER:
    # homes S1/S2, cut (connector). VESSEL->TANK_U2: one sheet, but unit 1 -> unit 2.
    evidence = Evidence(
        nodes=frozenset({N_TANK, N_VALVE, N_SENSOR, N_CONTROLLER, N_VESSEL, N_TANK_U2}),
        edges=frozenset({(N_TANK, N_VALVE), (N_SENSOR, N_CONTROLLER), (N_VESSEL, N_TANK_U2)}),
    )

    assert crossings(evidence, index, plant) == Crossings(k=2, k_connector=1, k_identity=1, u=1)


def test_k_equals_k_connector_when_nothing_is_duplicated() -> None:
    plant = build_toy_plant()
    index = SheetIndex.from_sheets(build_toy_sheets(plant), build_toy_manifest())
    # TANK->VALVE and SENSOR->CONTROLLER are both cut; VESSEL->TANK_U2 only changes unit.
    evidence = Evidence(
        nodes=frozenset({N_TANK, N_VALVE, N_SENSOR, N_CONTROLLER, N_VESSEL, N_TANK_U2}),
        edges=frozenset({(N_TANK, N_VALVE), (N_SENSOR, N_CONTROLLER), (N_VESSEL, N_TANK_U2)}),
    )

    assert crossings(evidence, index, plant) == Crossings(k=2, k_connector=2, k_identity=0, u=1)


def test_duplicate_does_not_move_k_only_its_split_between_connector_and_identity() -> None:
    plant, sheets, manifest = _duplicated_valve_toy()
    duplicated = SheetIndex.from_sheets(sheets, manifest)
    plain = SheetIndex.from_sheets(build_toy_sheets(plant), build_toy_manifest())
    evidence = Evidence(
        nodes=frozenset({N_TANK, N_VALVE, N_PUMP}),
        edges=frozenset({(N_TANK, N_VALVE), (N_VALVE, N_PUMP)}),
    )

    with_duplicate = crossings(evidence, duplicated, plant)
    without = crossings(evidence, plain, plant)

    assert with_duplicate.k == without.k == 2
    assert (without.k_connector, without.k_identity) == (2, 0)
    assert (with_duplicate.k_connector, with_duplicate.k_identity) == (1, 1)


def test_sheet_index_raises_when_a_multi_sheet_node_has_no_home_in_the_manifest() -> None:
    plant, sheets, manifest = _duplicated_valve_toy()
    manifest.identity_groups = []

    with pytest.raises(ValueError, match="exactly one home sheet"):
        SheetIndex.from_sheets(sheets, manifest)


def test_crossings_raises_when_a_cut_edge_does_not_cross_home_sheets() -> None:
    plant = build_toy_plant()
    index = SheetIndex.from_sheets(build_toy_sheets(plant), build_toy_manifest())
    # Forge a cut edge between two nodes that share sheet S2.
    forged = SheetIndex(index.sheets_of, index.home, index.cut | {(N_CONTROLLER, N_ACTUATOR)})
    evidence = Evidence(
        nodes=frozenset({N_CONTROLLER, N_ACTUATOR}),
        edges=frozenset({(N_CONTROLLER, N_ACTUATOR)}),
    )

    with pytest.raises(ValueError, match="k >= k_connector"):
        crossings(evidence, forged, plant)


def test_evidence_sheets_lists_every_sheet_that_draws_an_evidence_node() -> None:
    plant = build_toy_plant()
    sheets = build_toy_sheets(plant)
    # TANK is drawn on S1, VALVE on S2 — the evidence spans both.
    evidence = Evidence(nodes=frozenset({N_TANK, N_VALVE}), edges=frozenset())

    assert evidence_sheets(evidence, SheetIndex.from_sheets(sheets, build_toy_manifest())) == [
        SHEET_1,
        SHEET_2,
    ]


def test_evidence_tags_reads_the_printed_tag_not_the_internal_id() -> None:
    plant = build_toy_plant()
    evidence = Evidence(nodes=frozenset({N_TANK, N_CONTROLLER}), edges=frozenset())

    tags = evidence_tags(evidence, plant)

    assert tags == sorted([TAG_TANK, TAG_LOOP])
    assert N_TANK not in tags
    assert N_CONTROLLER not in tags


def test_flow_path_through_a_duplicated_item_counts_the_identity_crossing() -> None:
    plant, sheets, manifest = _duplicated_valve_toy()

    questions = flow_path_candidates(plant, manifest, sheets, corpus_id="toy", seed=0)
    by_anchors = {tuple(q.anchors): q for q in questions}

    tank_to_pump = by_anchors[(TAG_TANK, TAG_PUMP)]
    assert (tank_to_pump.k, tank_to_pump.k_connector, tank_to_pump.k_identity) == (2, 1, 1)
