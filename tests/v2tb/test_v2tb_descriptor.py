"""Descriptor resolution (design 5): a descriptor picks out exactly the node it names."""

from __future__ import annotations

import pytest
from plants_b import BRANCH, LINE, real_plant, series_plant, toy_plant

from plantgraph.qa.v2tb.descriptor import (
    Descriptor,
    PlantIndex,
    Side,
    canonical_descriptor,
    decode_item,
    descriptor_from_object,
    encode_descriptor,
    fold_class,
    fold_line_number,
    resolve_descriptor,
)


def _descriptor(class_name: str, line: str, next_to: str, side: Side) -> Descriptor:
    return Descriptor(class_name=class_name, line_number=line, next_to=next_to, side=side)


def test_a_descriptor_resolves_to_the_valve_it_names() -> None:
    index = PlantIndex(toy_plant())
    assert resolve_descriptor(index, _descriptor("GateValve", LINE, "FV-1", Side.UPSTREAM)) == {
        "g1"
    }
    assert resolve_descriptor(index, _descriptor("BallValve", LINE, "FV-1", Side.UPSTREAM)) == {
        "g2"
    }
    assert resolve_descriptor(index, _descriptor("GateValve", LINE, "T-1", Side.UPSTREAM)) == {"g3"}


def test_the_walk_passes_through_a_tee_but_stays_on_its_own_line() -> None:
    index = PlantIndex(toy_plant())
    # g1 reaches FV-1 through the tee `t`, and never reaches T-2 along the branch line
    assert index.nearest_tagged("g1", fold_line_number(LINE), forward=True) == {"fv"}
    assert resolve_descriptor(index, _descriptor("GateValve", BRANCH, "T-2", Side.UPSTREAM)) == {
        "b"
    }


def test_the_side_decides_which_neighbour_counts() -> None:
    index = PlantIndex(toy_plant())
    after = _descriptor("GateValve", LINE, "FV-1", Side.DOWNSTREAM)  # g3 lies downstream of FV-1
    assert resolve_descriptor(index, after) == {"g3"}


@pytest.mark.parametrize(
    "wrong",
    [
        _descriptor("GateValve", LINE, "FV-1", Side.DOWNSTREAM),  # wrong side
        _descriptor("GateValve", BRANCH, "FV-1", Side.UPSTREAM),  # wrong line
        _descriptor("BallValve", LINE, "T-1", Side.UPSTREAM),  # wrong class
        _descriptor("GateValve", LINE, "NO-SUCH", Side.UPSTREAM),  # no such neighbour
    ],
)
def test_a_wrong_side_line_class_or_neighbour_names_no_valve_g1(wrong: Descriptor) -> None:
    index = PlantIndex(toy_plant())
    assert "g1" not in resolve_descriptor(index, wrong)


def test_spelling_of_class_and_line_number_does_not_matter() -> None:
    index = PlantIndex(toy_plant())
    loose = _descriptor("gate valve", "6-p-1203-a1a", "fv-1", Side.UPSTREAM)
    assert resolve_descriptor(index, loose) == {"g1"}
    assert fold_class("Gate-Valve") == fold_class("GateValve")


def test_a_tagged_valve_is_not_named_by_a_descriptor() -> None:
    index = PlantIndex(toy_plant())
    assert resolve_descriptor(index, _descriptor("GlobeValve", LINE, "T-1", Side.UPSTREAM)) == set()


def test_canonical_descriptors_resolve_to_their_own_node() -> None:
    index = PlantIndex(toy_plant())
    for node in ("g1", "g2", "g3", "b"):
        descriptor = canonical_descriptor(index, node)
        assert descriptor is not None
        assert resolve_descriptor(index, descriptor) == {node}


def test_two_identical_valves_in_series_cannot_be_named() -> None:
    index = PlantIndex(series_plant())
    assert canonical_descriptor(index, "v1") is None
    assert canonical_descriptor(index, "v2") is None


def test_a_descriptor_round_trips_through_its_string() -> None:
    original = _descriptor("GateValve", LINE, "FV-1", Side.UPSTREAM)
    assert decode_item(encode_descriptor(original)) == original
    assert decode_item("GTV-1203") == "GTV-1203"


def test_a_malformed_descriptor_is_refused() -> None:
    with pytest.raises(ValueError, match="expected a descriptor"):
        decode_item('{"class": "GateValve"}')
    with pytest.raises(ValueError, match="expected a descriptor"):
        descriptor_from_object(
            {"class": "GateValve", "line_number": "1", "next_to": "A", "side": "left"}
        )


def test_every_untagged_valve_of_a_real_plant_that_has_a_descriptor_resolves_to_itself() -> None:
    plant = real_plant()
    index = PlantIndex(plant)
    untagged = [
        n for n, d in plant.nodes(data=True) if not d.get("tag") and "Valve" in d["node_class"]
    ]
    named = 0
    for node in untagged:
        descriptor = canonical_descriptor(index, node)
        if descriptor is not None:
            named += 1
            assert resolve_descriptor(index, descriptor) == {node}
    assert untagged and named > 0
