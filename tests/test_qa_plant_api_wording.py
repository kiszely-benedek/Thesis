"""Golden renderings of the plant API's result texts and tool descriptions (cascade-v2 §5)."""

from __future__ import annotations

import pytest

from plantgraph.graph import schema
from plantgraph.qa.plant_api.model import ItemFilter, PlantApiError, UnknownTagError
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import no_such_tag_text
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
    "spaces; patterns and wildcards are not supported, so another spelling will not match. "
    "Do not try other tags in its place: that the plant has no such item is itself an answer."
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


def test_undirected_path_is_a_summary_without_an_item_listing() -> None:
    api = PlantApi(build_graph(_ZIGZAG_ITEMS, _ZIGZAG_EDGES))

    result = api.path("A", "E", directed=False)

    assert result.render() == (
        "$r1: path A to E IGNORING EDGE DIRECTION: linked, 4 hops, 2 edges walked against "
        "their direction, sheets S1. This is not a flow path and the route is not listed; "
        "it does not answer a question about flow."
    )
    assert result.touched_keys == ()  # nothing was shown, so nothing counts as evidence read


def test_undirected_path_between_unlinked_items_says_so() -> None:
    api = PlantApi(build_graph(_ZIGZAG_ITEMS | {"Z": (TANK, "1", ("S1",))}, _ZIGZAG_EDGES))

    text = api.path("A", "Z", directed=False).render()

    assert (
        text
        == "$r1: path A to Z IGNORING EDGE DIRECTION: not linked, even ignoring edge direction."
    )


def test_unknown_node_class_is_refused_with_the_valid_values() -> None:
    api = toy_api()

    with pytest.raises(PlantApiError) as refused:
        api.traverse("GV2", "upstream", "flow", stop_at=ItemFilter(node_class="Valve"))

    assert str(refused.value) == (
        "expected a known node_class, found 'Valve'; valid node_class values: "
        "ActuatingFunction, BallValve, CentrifugalPump, CheckValve, GlobeValve, "
        "PressureVessel, ProcessInstrumentationFunction, ProcessSignalGeneratingFunction, Tank"
    )


def test_a_label_given_as_node_class_is_refused_with_a_pointer_to_the_other_field() -> None:
    with pytest.raises(PlantApiError, match=r"'OperatedValve' is a valid label; use that field"):
        toy_api().find(ItemFilter(node_class="OperatedValve"))


def test_unknown_label_is_refused_with_the_valid_values() -> None:
    with pytest.raises(PlantApiError, match=r"valid label values: .*OperatedValve"):
        toy_api().find(ItemFilter(label="Valve"))


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


def test_no_such_tag_text_says_not_to_try_other_tags() -> None:
    assert "Do not try other tags in its place" in no_such_tag_text("FV-33-4")


def test_resolving_an_unknown_tag_raises_the_subclass_carrying_the_tag() -> None:
    with pytest.raises(UnknownTagError) as raised:
        toy_api().traverse("FV-33-4", "upstream", "flow")

    assert raised.value.tag == "FV-33-4"
    assert isinstance(raised.value, PlantApiError)
