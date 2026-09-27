"""`qa.questions.evidence` — the connector cut, `k`, `evidence_sheets`, `evidence_tags` (QA-T6)."""

from __future__ import annotations

from plantgraph.qa.questions.evidence import (
    Evidence,
    connector_cut,
    evidence_k,
    evidence_sheets,
    evidence_tags,
)
from qa_toy_plant import (
    CUT_EDGES,
    N_ACTUATOR,
    N_CONTROLLER,
    N_SENSOR,
    N_TANK,
    N_VALVE,
    SHEET_1,
    SHEET_2,
    TAG_LOOP,
    TAG_TANK,
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


def test_evidence_k_counts_only_edges_that_are_actually_cut() -> None:
    cut = CUT_EDGES
    # TANK->VALVE is cut (S1 -> S2); SENSOR->CONTROLLER is cut too (S1 -> S2).
    crossing = Evidence(nodes=frozenset({N_TANK, N_VALVE}), edges=frozenset({(N_TANK, N_VALVE)}))
    not_crossing = Evidence(
        nodes=frozenset({N_CONTROLLER, N_ACTUATOR}), edges=frozenset({(N_CONTROLLER, N_ACTUATOR)})
    )
    both = Evidence(
        nodes=frozenset({N_TANK, N_SENSOR, N_CONTROLLER}),
        edges=frozenset({(N_TANK, N_VALVE), (N_SENSOR, N_CONTROLLER)}),
    )

    assert evidence_k(crossing, cut) == 1
    assert evidence_k(not_crossing, cut) == 0
    assert evidence_k(both, cut) == 2


def test_evidence_sheets_lists_every_sheet_that_draws_an_evidence_node() -> None:
    plant = build_toy_plant()
    sheets = build_toy_sheets(plant)
    # TANK is drawn on S1, VALVE on S2 — the evidence spans both.
    evidence = Evidence(nodes=frozenset({N_TANK, N_VALVE}), edges=frozenset())

    assert evidence_sheets(evidence, sheets) == [SHEET_1, SHEET_2]


def test_evidence_tags_reads_the_printed_tag_not_the_internal_id() -> None:
    plant = build_toy_plant()
    evidence = Evidence(nodes=frozenset({N_TANK, N_CONTROLLER}), edges=frozenset())

    tags = evidence_tags(evidence, plant)

    assert tags == sorted([TAG_TANK, TAG_LOOP])
    assert N_TANK not in tags
    assert N_CONTROLLER not in tags
