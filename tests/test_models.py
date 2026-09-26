"""Invariants of the benchmark data model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plantgraph.benchmark.models import (
    BoundingBox,
    ConnectorObservation,
    ConnectorPair,
    DanglingReference,
    IdentityGroup,
    SheetRef,
    Side,
    SplitManifest,
    UnresolvedConnector,
)


def box(xmin=10.0, ymin=20.0, xmax=110.0, ymax=70.0) -> BoundingBox:
    return BoundingBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)


def observation(sheet="5", node_id="inlet/outlet47") -> ConnectorObservation:
    return ConnectorObservation(sheet_file=sheet, node_id=node_id, bbox=box(), side=Side.LEFT)


def test_degenerate_box_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(xmin=100.0, ymin=0.0, xmax=100.0, ymax=50.0)


def test_expanded_grows_sideways_by_width_multiple() -> None:
    grown = box().expanded(x_factor=3.0, y_margin=25)
    assert grown.xmin == 10.0 - 300.0
    assert grown.xmax == 110.0 + 300.0
    assert grown.ymin == 20.0 - 25
    assert grown.height == box().height + 50


def test_clipping_keeps_the_box_inside_the_image() -> None:
    clipped = box(-50.0, -50.0, 5000.0, 5000.0).clipped_to(3188, 2130)
    assert clipped.as_pixels() == (0, 0, 3188, 2130)


def test_sheet_reference_normalises_spelling() -> None:
    # Both 'PID 120-1' and 'PID-120-01' occur on the drawings for the same sheet.
    assert SheetRef(pid="120", sheet_no=1).canonical() == "PID-120-1"


def test_identity_group_needs_more_than_one_occurrence() -> None:
    with pytest.raises(ValidationError):
        IdentityGroup(tag="RC-P102A", home="5:eq1", references=[])


def test_manifest_accounts_for_every_connector() -> None:
    paired_a, paired_b, lone = (
        observation("5", "inlet/outlet1"),
        observation("6", "inlet/outlet2"),
        observation("0", "inlet/outlet3"),
    )
    manifest = SplitManifest(
        source="test",
        sheet_files=["0", "5", "6"],
        connectors=[paired_a, paired_b, lone],
        connector_pairs=[ConnectorPair(from_key=paired_a.key, to_key=paired_b.key)],
        dangling=[DanglingReference(from_key=lone.key, target=SheetRef(pid="190", sheet_no=1))],
    )
    assert manifest.accounted_for()


def test_manifest_notices_a_dropped_connector() -> None:
    kept, dropped = observation("5", "inlet/outlet1"), observation("6", "inlet/outlet2")
    manifest = SplitManifest(source="test", sheet_files=["5", "6"], connectors=[kept, dropped])
    assert not manifest.accounted_for()


def test_manifest_accepts_an_openly_unresolved_connector() -> None:
    # On real drawings, the named target sheet sometimes exists but has no matching
    # connector on it. Not a bug — it just needs to be reported, not hidden.
    stuck = observation("11", "inlet/outlet22")
    manifest = SplitManifest(
        source="test",
        sheet_files=["11"],
        connectors=[stuck],
        unresolved=[
            UnresolvedConnector(from_key=stuck.key, reason="no P&ID reference on the label")
        ],
    )
    assert manifest.accounted_for()
