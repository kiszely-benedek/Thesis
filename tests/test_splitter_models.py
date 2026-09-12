"""A splitter új adatmodelljeinek invariánsai: OffPageConnector, SplitConfig, SplitManifest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plantgraph.benchmark.models import (
    ConnectorPair,
    Direction,
    NumberingScheme,
    OffPageConnector,
    SplitConfig,
    SplitManifest,
)


def connector(sheet_id="0", attached_node_id="opc:0:0", partner_sheet_id="1") -> OffPageConnector:
    return OffPageConnector(
        tag="SHEET-0-OPC-00",
        sheet_id=sheet_id,
        direction=Direction.OUTGOING,
        partner_sheet_id=partner_sheet_id,
        partner_tag="SHEET-1-OPC-00",
        attached_node_id=attached_node_id,
    )


def test_off_page_connector_key_matches_connector_observation_shape() -> None:
    # A key alakja (lap:node_id) szándékosan egyezik a ConnectorObservation.key-ével
    # (models.py) — ez teszi lehetővé, hogy a ConnectorPair mindkét forrásra ugyanúgy működjön.
    assert connector(sheet_id="3", attached_node_id="opc:3:7").key == "3:opc:3:7"


def test_split_config_defaults_cover_the_design_note_equipment_list() -> None:
    config = SplitConfig()
    assert config.strategy == "flow_greedy"
    assert config.equipment_classes == {"vessel", "pump", "exchanger", "column", "tank"}
    assert config.numbering_scheme is NumberingScheme.SEQUENTIAL


def test_split_config_rejects_a_zero_sheet_budget() -> None:
    with pytest.raises(ValidationError):
        SplitConfig(sheet_equipment_budget=0)


def test_split_config_rejects_an_out_of_range_duplication_rate() -> None:
    with pytest.raises(ValidationError):
        SplitConfig(duplication_rate=1.5)


def test_manifest_accounts_for_off_page_connectors_too() -> None:
    out, inp = (
        connector(sheet_id="0", attached_node_id="opc:0:0"),
        connector(sheet_id="1", attached_node_id="opc:1:0", partner_sheet_id="0"),
    )
    manifest = SplitManifest(
        source="synthetic",
        sheet_files=["0", "1"],
        off_page_connectors=[out, inp],
        connector_pairs=[ConnectorPair(from_key=out.key, to_key=inp.key, original_edge=("a", "b"))],
    )
    assert manifest.accounted_for()


def test_manifest_notices_a_dropped_off_page_connector() -> None:
    out, inp = (
        connector(sheet_id="0", attached_node_id="opc:0:0"),
        connector(sheet_id="1", attached_node_id="opc:1:0", partner_sheet_id="0"),
    )
    manifest = SplitManifest(
        source="synthetic", sheet_files=["0", "1"], off_page_connectors=[out, inp]
    )
    assert not manifest.accounted_for()
