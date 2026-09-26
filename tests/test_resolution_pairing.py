"""`pair_connectors` — a két párosító szabály és a rájuk épülő megoldatlan-jelentés.

A hibakereséshez kézzel épített `ConnectorLabel`-eken teszteli az egyes
szabályokat elszigetelten; a design §10 T3 elfogadási feltételét (a predikált
párok egyeznek a megoldókulccsal) a teljes splitter -> localize -> pairing
csővezetéken futtatva.
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
    """Egy 4-egységes szintetikus üzem — n_units alapértéke (`GeneratorConfig`)."""
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
) -> ConnectorLabel:
    """Kényelmi gyár: csak azt a mezőt kell kiírni a hívónak, ami az adott tesztben számít."""
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
    """Két azonos connector_number-ű bejövő (valódi duplicate_tag eset, design §2) nem választható
    szét a legerősebb szabállyal — a line_number viszont igen, a másik pedig megoldatlan marad.
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
    """Jelvezeték-vágásnál (measured_by, control, ...) nincs line_number, a gyengébb szabály fut."""
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
    """A teljes csővezeték T3-ig: split -> localize -> minden lap feliratai egy listában."""
    plant = _generated_plant()
    sheets, manifest = split(plant, config)
    localized, occurrence_map = localize(sheets)
    labels = [label for sheet in localized for label in read_connector_labels(sheet)]
    return labels, manifest.connector_pairs, occurrence_map


def _to_original_pair(pair: ConnectorPair, occurrence_map: OccurrenceMap) -> frozenset[str]:
    """Egy predikált pár helyi kulcsait az eredeti, lap-minősített kulcsokra fordítja.

    Csak a teszt fordítja vissza — a resolver sosem kapja meg az `OccurrenceMap`-et
    (design §4.3, D1 döntés).
    """
    return frozenset(
        {occurrence_map.original_key(pair.from_key), occurrence_map.original_key(pair.to_key)}
    )


def test_predicted_pairs_equal_the_manifest_at_splitter_defaults() -> None:
    """Design §10 T3 elfogadás: alapértelmezett feliratozásnál a predikció a megoldókulcs maga.

    A budget/seed csak azért tér el az alapértéktől, hogy a 4-egységes üzem
    ténylegesen több lapra és lapok közötti vágásra essen szét — minden más
    dial (feliratozás, számozás, egyezés) a `SplitConfig` alapértéke marad.
    """
    config = SplitConfig(sheet_equipment_budget=3, seed=0)
    labels, manifest_pairs, occurrence_map = _connector_labels(config)
    sheet_ids = {label.sheet_id for label in labels}
    predicted, unresolved = pair_connectors(labels, sheet_ids)

    message = f"alapértelmezettnél minden csatlakozónak párt kell találnia: {unresolved}"
    assert unresolved == [], message
    predicted_original = {_to_original_pair(pair, occurrence_map) for pair in predicted}
    expected = {frozenset({pair.from_key, pair.to_key}) for pair in manifest_pairs}
    assert predicted_original == expected


def test_every_connector_is_paired_or_unresolved_at_drawing_only_detail() -> None:
    """Design §10 T3 elfogadás: a gyengébb feliratozásnál sem tűnhet el csendben egy csatlakozó,
    és amit párba tett, annak helyesnek kell lennie (a §5.2 property: pontosság mindig 1.0).
    """
    config = SplitConfig(
        sheet_equipment_budget=3, seed=0, connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY
    )
    labels, manifest_pairs, occurrence_map = _connector_labels(config)
    sheet_ids = {label.sheet_id for label in labels}
    predicted, unresolved = pair_connectors(labels, sheet_ids)

    accounted = {pair.from_key for pair in predicted} | {pair.to_key for pair in predicted}
    accounted |= {entry.from_key for entry in unresolved}
    assert accounted == {label.key for label in labels}, "egy csatlakozó sem tűnhet el csendben"

    expected = {frozenset({pair.from_key, pair.to_key}) for pair in manifest_pairs}
    for pair in predicted:
        original_pair = _to_original_pair(pair, occurrence_map)
        assert original_pair in expected, f"hibás pár: {original_pair}"
