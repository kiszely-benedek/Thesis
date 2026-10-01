"""`pair_connectors` — the two pairing rules, and the unresolved-reporting built on them.

Tests each rule in isolation on hand-built `ConnectorLabel`s; design §10 T3's
acceptance condition (the predicted pairs match the answer key) is exercised
through the full splitter -> localize -> pairing pipeline.
"""

from __future__ import annotations

import networkx as nx

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import ConnectorKind, ConnectorPair, Direction, MatchRule
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.resolution.connector_labels import ConnectorLabel, read_connector_labels
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.pairing import pair_connectors

_ALL_SHEET_IDS = {"0", "1"}


def _generated_plant(seed: int = 8) -> nx.DiGraph[str]:
    """A 4-unit synthetic plant — the default of n_units (`GeneratorConfig`)."""
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


def _label(
    key: str,
    sheet_id: str,
    direction: Direction,
    connector_number: str,
    referenced_drawing_number: str,
    referenced_connector_number: str | None = None,
    line_number: str | None = None,
    fluid_code: str | None = None,
    kind: ConnectorKind = ConnectorKind.PIPE,
    relation: str = "send_to",
    loop_tag: str | None = None,
) -> ConnectorLabel:
    """Convenience factory: caller only needs to spell out the field that matters for this test."""
    return ConnectorLabel(
        key=key,
        sheet_id=sheet_id,
        direction=direction,
        kind=kind,
        relation=relation,
        connector_number=connector_number,
        referenced_drawing_number=referenced_drawing_number,
        referenced_connector_number=referenced_connector_number,
        line_number=line_number,
        fluid_code=fluid_code,
        loop_tag=loop_tag,
    )


def test_unique_connector_number_pairs_via_the_strongest_rule() -> None:
    out_label = _label(
        "0:out", "0", Direction.OUTGOING, "OUT-1", "1", referenced_connector_number="IN-1"
    )
    in_label = _label(
        "1:in", "1", Direction.INCOMING, "IN-1", "0", referenced_connector_number="OUT-1"
    )
    pairs, unresolved = pair_connectors([out_label, in_label], _ALL_SHEET_IDS)

    assert unresolved == []
    (pair,) = pairs
    assert (pair.from_key, pair.to_key) == ("0:out", "1:in")
    assert pair.match_rule is MatchRule.CONNECTOR_NUMBER


def test_absent_target_sheet_is_unresolved_with_a_named_reason() -> None:
    out_label = _label("0:out", "0", Direction.OUTGOING, "OUT-1", "not-in-corpus")
    pairs, unresolved = pair_connectors([out_label], _ALL_SHEET_IDS)

    assert pairs == []
    (entry,) = unresolved
    assert entry.from_key == "0:out"
    assert entry.reason == "referenced drawing not in corpus"


def test_ambiguous_connector_number_falls_back_to_line_number() -> None:
    """Two incoming labels sharing a connector_number (a real duplicate_tag case, design §2) can't
    be told apart by the strongest rule — but line_number can, and the other stays unresolved.
    """
    out_label = _label(
        "0:out",
        "0",
        Direction.OUTGOING,
        "OUT-1",
        "1",
        referenced_connector_number="IN-DUP",
        line_number="PL-1",
        fluid_code="PL",
    )
    matching_in = _label(
        "1:in-a",
        "1",
        Direction.INCOMING,
        "IN-DUP",
        "0",
        referenced_connector_number="OUT-1",
        line_number="PL-1",
        fluid_code="PL",
    )
    other_in = _label(
        "1:in-b",
        "1",
        Direction.INCOMING,
        "IN-DUP",
        "0",
        referenced_connector_number="OUT-1",
        line_number="PL-2",
        fluid_code="PL",
    )
    pairs, unresolved = pair_connectors([out_label, matching_in, other_in], _ALL_SHEET_IDS)

    (pair,) = pairs
    assert (pair.from_key, pair.to_key) == ("0:out", "1:in-a")
    assert pair.match_rule is MatchRule.LINE_NUMBER
    (entry,) = unresolved
    assert entry.from_key == "1:in-b"


def test_shared_label_group_with_more_than_two_labels_is_all_unresolved() -> None:
    out_a = _label(
        "0:out-a", "0", Direction.OUTGOING, "A", "1", line_number="PL-1", fluid_code="PL"
    )
    out_b = _label(
        "0:out-b", "0", Direction.OUTGOING, "B", "1", line_number="PL-1", fluid_code="PL"
    )
    in_a = _label("1:in-a", "1", Direction.INCOMING, "A", "0", line_number="PL-1", fluid_code="PL")
    pairs, unresolved = pair_connectors([out_a, out_b, in_a], _ALL_SHEET_IDS)

    assert pairs == []
    assert {entry.from_key for entry in unresolved} == {"0:out-a", "0:out-b", "1:in-a"}
    assert all("2 outgoing, 1 incoming" in entry.reason for entry in unresolved)


def test_service_direction_used_when_no_line_number_is_printed() -> None:
    """A signal-line cut (measured_by, control, ...) has no line_number, so the weaker rule runs."""
    out_label = _label(
        "0:out", "0", Direction.OUTGOING, "A", "1", kind=ConnectorKind.SIGNAL, relation="control"
    )
    in_label = _label(
        "1:in", "1", Direction.INCOMING, "B", "0", kind=ConnectorKind.SIGNAL, relation="control"
    )
    pairs, _ = pair_connectors([out_label, in_label], _ALL_SHEET_IDS)

    (pair,) = pairs
    assert pair.match_rule is MatchRule.SERVICE_DIRECTION


def _connector_labels(
    config: SplitConfig,
) -> tuple[list[ConnectorLabel], list[ConnectorPair], OccurrenceMap]:
    """The full pipeline up to T3: split -> localize -> every sheet's labels in one list."""
    plant = _generated_plant()
    sheets, manifest = split(plant, config)
    localized, occurrence_map = localize(sheets)
    labels = [
        label
        for sheet in localized
        for label in read_connector_labels(sheet)[0]  # the splitter always gives a drawing number
    ]
    return labels, manifest.connector_pairs, occurrence_map


def _to_original_pair(pair: ConnectorPair, occurrence_map: OccurrenceMap) -> frozenset[str]:
    """Translate a predicted pair's local keys to the original, sheet-qualified keys.

    Only the test translates back — the resolver never receives the
    `OccurrenceMap` (design §4.3, decision D1).
    """
    return frozenset(
        {occurrence_map.original_key(pair.from_key), occurrence_map.original_key(pair.to_key)}
    )


def test_predicted_pairs_equal_the_manifest_at_splitter_defaults() -> None:
    """Design §10 T3 acceptance: under default labelling, the prediction is the answer key itself.

    budget/seed only differ from the default so that the 4-unit plant actually
    splits across several sheets with cross-sheet cuts — every other dial
    (labelling, numbering, matching) stays at `SplitConfig`'s default.
    """
    config = SplitConfig(sheet_equipment_budget=3, seed=0)
    labels, manifest_pairs, occurrence_map = _connector_labels(config)
    sheet_ids = {label.sheet_id for label in labels}
    predicted, unresolved = pair_connectors(labels, sheet_ids)

    message = f"at the defaults, every connector must find a pair: {unresolved}"
    assert unresolved == [], message
    predicted_original = {_to_original_pair(pair, occurrence_map) for pair in predicted}
    expected = {frozenset({pair.from_key, pair.to_key}) for pair in manifest_pairs}
    assert predicted_original == expected


def test_every_connector_is_paired_or_unresolved_at_drawing_only_detail() -> None:
    """Design §10 T3 acceptance: even under weaker labelling, no connector may silently disappear,
    and whatever gets paired must be correct (the §5.2 property: precision is always 1.0).
    """
    config = SplitConfig(
        sheet_equipment_budget=3, seed=0, connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY
    )
    labels, manifest_pairs, occurrence_map = _connector_labels(config)
    sheet_ids = {label.sheet_id for label in labels}
    predicted, unresolved = pair_connectors(labels, sheet_ids)

    accounted = {pair.from_key for pair in predicted} | {pair.to_key for pair in predicted}
    accounted |= {entry.from_key for entry in unresolved}
    assert accounted == {label.key for label in labels}, "no connector may silently disappear"

    expected = {frozenset({pair.from_key, pair.to_key}) for pair in manifest_pairs}
    for pair in predicted:
        original_pair = _to_original_pair(pair, occurrence_map)
        assert original_pair in expected, f"wrong pair: {original_pair}"


def test_two_signal_loops_between_the_same_sheets_pair_by_loop_tag() -> None:
    """Without loop_tag these four labels would form one ambiguous group (ADR-0027)."""

    def signal(key: str, sheet: str, direction: Direction, other: str, loop: str) -> ConnectorLabel:
        return _label(
            key,
            sheet,
            direction,
            f"C-{key}",
            other,
            kind=ConnectorKind.SIGNAL,
            relation="measured_by",
            loop_tag=loop,
        )

    labels = [
        signal("0:o1", "0", Direction.OUTGOING, "1", "FIC-1"),
        signal("0:o2", "0", Direction.OUTGOING, "1", "TIC-2"),
        signal("1:i1", "1", Direction.INCOMING, "0", "FIC-1"),
        signal("1:i2", "1", Direction.INCOMING, "0", "TIC-2"),
    ]
    pairs, unresolved = pair_connectors(labels, _ALL_SHEET_IDS)

    assert unresolved == []
    assert {(pair.from_key, pair.to_key) for pair in pairs} == {
        ("0:o1", "1:i1"),
        ("0:o2", "1:i2"),
    }


def test_four_unit_plant_at_drawing_only_pairs_with_precision_one() -> None:
    config = SplitConfig(
        sheet_equipment_budget=3, seed=0, connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY
    )
    labels, manifest_pairs, occurrence_map = _connector_labels(config)
    predicted, unresolved = pair_connectors(labels, {label.sheet_id for label in labels})

    expected = {frozenset({pair.from_key, pair.to_key}) for pair in manifest_pairs}
    predicted_original = {_to_original_pair(pair, occurrence_map) for pair in predicted}
    assert predicted_original <= expected, "pair precision must stay 1.0"
    assert unresolved == []
    assert predicted_original == expected
