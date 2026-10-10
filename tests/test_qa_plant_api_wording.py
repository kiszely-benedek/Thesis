"""Golden renderings of the plant API's result texts and tool descriptions (cascade-v2 §5)."""

from __future__ import annotations

import pytest

from plantgraph.graph import schema
from plantgraph.qa.plant_api.model import ItemFilter, PlantApiError
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.tool_registry import TOOLS
from qa_plant_api_toy import EdgeSpecs, ItemSpecs, build_graph, toy_api

TANK = schema.NodeClass.TANK.value
#: A -> B <- C -> D <- E: the undirected path A..E walks B<-C and D<-E against the edge direction.
_ZIGZAG_ITEMS: ItemSpecs = {tag: (TANK, "1", ("S1",)) for tag in "ABCDE"}
_ZIGZAG_EDGES: EdgeSpecs = [
    ("A", "send_to", "B", ()),
    ("C", "send_to", "B", ()),
    ("C", "send_to", "D", ()),
    ("E", "send_to", "D", ()),
]

_NO_TAG = (
    "No item has tag 'FV-33-4' in this plant. Tags are already matched ignoring case and "
    "spaces; patterns and wildcards are not supported, so another spelling will not match."
)


def test_directed_no_path_states_the_direction_semantics() -> None:
    text = toy_api().path("V2", "T1").render()

    assert text == (
        "$r1: no path from V2 to T1 along the edge direction (send_to: source to target). "
        "Flow cannot reach T1 from V2."
    )


def test_directed_no_path_over_signals_does_not_claim_flow() -> None:
    text = toy_api().path("FV", "T1", relations="signal").render()

    assert "send_to" not in text
    assert text.endswith("T1 cannot be reached from FV that way.")


def test_undirected_path_is_labelled_and_marks_reversed_edges() -> None:
    api = PlantApi(build_graph(_ZIGZAG_ITEMS, _ZIGZAG_EDGES))

    text = api.path("A", "E", directed=False).render()

    assert text.splitlines() == [
        "$r1: path A to E IGNORING EDGE DIRECTION, 4 hops, 2 edges walked against their "
        "direction (marked [against direction]); this is not a flow path, sheets S1",
        "A (Tank, unit 1, sheets S1)",
        "B (Tank, unit 1, sheets S1)",
        "C (Tank, unit 1, sheets S1)",
        "D (Tank, unit 1, sheets S1)",
        "E (Tank, unit 1, sheets S1)",
        "A -send_to-> B",
        "C -send_to-> B [against direction]",
        "C -send_to-> D",
        "E -send_to-> D [against direction]",
    ]


def test_directed_path_text_is_unchanged() -> None:
    text = toy_api().path("T1", "V2").render()

    assert text.startswith("$r1: path T1 to V2, 4 hops, sheets S1,S2,S3")
    assert "[against direction]" not in text


def test_upstream_traverse_marks_sources_end_and_hop_limited_items_not() -> None:
    text = toy_api().traverse("GV2", "upstream", "flow", max_hops=3).render()

    lines = text.splitlines()
    assert "T1 (Tank, unit 1, sheets S1) [hop 3] [end]" in lines
    assert "V1 (PressureVessel, unit 1, sheets S2) [hop 3] [hop limit]" in lines
    assert "P1 (CentrifugalPump, unit 1, sheets S2) [hop 1]" in lines  # interior: no mark


def test_unlimited_traverse_has_end_marks_and_no_hop_limit() -> None:
    text = toy_api().traverse("GV2", "upstream", "flow").render()

    assert "[hop limit]" not in text
    assert "T1 (Tank, unit 1, sheets S1) [hop 3] [end]" in text.splitlines()


def test_downstream_end_is_a_sink() -> None:
    text = toy_api().traverse("P1", "downstream", "flow").render()

    assert "V2 (PressureVessel, unit 2, sheets S3) [hop 2] [end]" in text.splitlines()


def test_stop_items_are_marked_stop_not_end() -> None:
    api = toy_api()

    text = api.traverse("GV2", "upstream", "flow", stop_at=ItemFilter(label="OperatedValve"))

    assert "BV1 (BallValve, unit 1, sheets S1) [hop 2] [stop]" in text.render().splitlines()
    assert "[end]" not in text.render()


def test_neighbours_carry_no_boundary_marks() -> None:
    text = toy_api().neighbours("P1", "downstream", "flow").render()

    assert "[end]" not in text and "[hop limit]" not in text


def test_find_with_unknown_tag_explains_matching() -> None:
    text = toy_api().find(ItemFilter(tag="FV-33-4")).render()

    assert text.splitlines() == ["$r1: 0 items", _NO_TAG]


def test_find_with_known_tag_that_other_filters_exclude_has_no_tag_sentence() -> None:
    text = toy_api().find(ItemFilter(tag="T1", unit="2")).render()

    assert text == "$r1: 0 items"


def test_unknown_tag_error_carries_the_same_sentence() -> None:
    with pytest.raises(PlantApiError, match="No item has tag 'FV-33-4' in this plant. Tags are"):
        toy_api().traverse("FV-33-4", "upstream", "flow")


def test_tool_descriptions_state_the_generic_usage() -> None:
    assert "linked at all, never a flow route" in TOOLS["path"].description
    assert "set stop_at to that kind; stop items are marked [stop]" in TOOLS["traverse"].description
