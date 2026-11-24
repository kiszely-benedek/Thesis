"""Descriptor resolution (design 5): a descriptor picks out exactly the node it names."""

from __future__ import annotations

import networkx as nx
import pytest
from plants_b import (
    BRANCH,
    LINE,
    bypass_plant,
    real_plant,
    root_valve_plant,
    series_plant,
    spec_break_plant,
    toy_plant,
)

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


def test_the_walk_follows_every_send_to_edge_whatever_its_line_number() -> None:
    index = PlantIndex(toy_plant())
    # g1 reaches FV-1 through the tee `t`, and also T-2 along the tee's branch line
    assert index.nearest_tagged("g1", forward=True) == {"fv", "tank2"}
    assert index.nearest_tagged("g1", forward=False) == {"p"}
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


def test_a_spec_break_block_is_named_by_the_pump_upstream_of_it() -> None:
    index = PlantIndex(spec_break_plant())
    assert index.line_numbers("block") == sorted([fold_line_number(LINE), fold_line_number(BRANCH)])
    # either of the block's two line numbers is accepted (R10c)
    for line in (LINE, BRANCH):
        assert resolve_descriptor(
            index, _descriptor("GateValve", line, "P-1", Side.DOWNSTREAM)
        ) == {"block"}


def test_an_instrument_root_valve_is_named_by_its_gauge() -> None:
    index = PlantIndex(root_valve_plant())
    root = _descriptor("NeedleValve", BRANCH, "PI-1", Side.UPSTREAM)
    assert resolve_descriptor(index, root) == {"root"}
    assert canonical_descriptor(index, "root") is not None


def test_a_control_valve_bypass_globe_valve_gets_a_unique_descriptor() -> None:
    index = PlantIndex(bypass_plant())
    descriptor = canonical_descriptor(index, "bypass")
    assert descriptor is not None
    assert resolve_descriptor(index, descriptor) == {"bypass"}
    assert canonical_descriptor(index, "gate_in") is not None


def test_two_printed_line_numbers_that_fold_together_are_refused() -> None:
    plant = toy_plant()
    plant.add_edge("g3", "tank2", relation="send_to", line_number="6-P-1203-A1A")  # LINE without ")
    with pytest.raises(ValueError, match="both fold to"):
        PlantIndex(plant)


def test_an_edge_without_a_line_number_still_carries_the_walk() -> None:
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class="Tank", tag="T-1")
    plant.add_node("v", node_class="GateValve")
    plant.add_node("b", node_class="Tank", tag="T-2")
    plant.add_edge("a", "v", relation="send_to", line_number=LINE)
    plant.add_edge("v", "b", relation="send_to")
    index = PlantIndex(plant)
    assert index.nearest_tagged("v", forward=True) == {"b"}
