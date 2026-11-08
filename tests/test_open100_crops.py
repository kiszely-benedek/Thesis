"""Montage row identifiers must be unique, or a label read off a montage cannot be traced back."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from plantgraph.benchmark.models import BoundingBox, ConnectorObservation, Side
from plantgraph.benchmark.open100 import crops

_BOX = BoundingBox(xmin=0.0, ymin=0.0, xmax=10.0, ymax=10.0)


def _observation(sheet: str, node_id: str) -> ConnectorObservation:
    return ConnectorObservation(sheet_file=sheet, node_id=node_id, bbox=_BOX, side=Side.LEFT)


def test_the_real_node_id_shape_gives_the_short_tag() -> None:
    assert crops.montage_tag(_observation("5", "inlet/outlet47")) == "5/47"


def test_node_ids_that_share_their_digits_get_different_tags() -> None:
    first = crops.montage_tag(_observation("5", "inlet/outlet47"))
    second = crops.montage_tag(_observation("5", "outlet47"))
    assert first != second


def test_two_connectors_with_one_tag_are_refused(tmp_path: Path) -> None:
    twins = [_observation("5", "inlet/outlet47"), _observation("5", "inlet/outlet47")]
    images = {"5": Image.new("RGB", (200, 100), "white")}
    with pytest.raises(ValueError, match="duplicate montage tag"):
        crops.write_montages(twins, images, tmp_path)
