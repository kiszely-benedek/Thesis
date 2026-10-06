"""The six plant API primitives on a hand-built toy with branches, a cycle and a check valve."""

from __future__ import annotations

import pytest

from plantgraph.graph.schema import NodeClass
from plantgraph.qa.plant_api.model import ItemFilter, PlantApiError
from plantgraph.qa.plant_api.primitives import PlantApi
from qa_plant_api_toy import build_graph, member_tags, set_tags, toy_api

_PUMP = NodeClass.CENTRIFUGAL_PUMP.value
_OPERATED = ItemFilter(label="OperatedValve")


# --- find / filter ------------------------------------------------------------


def test_find_by_label_class_unit_sheet_and_tag() -> None:
    api = toy_api()

    assert set_tags(api.find(_OPERATED)) == ["BV1", "GV2"]
    assert set_tags(api.find(ItemFilter(node_class="GlobeValve"))) == ["GV2"]
    assert set_tags(api.find(ItemFilter(unit="2"))) == ["GV2", "V2"]
    assert set_tags(api.find(ItemFilter(not_unit="1"))) == ["GV2", "V2"]
    assert set_tags(api.find(ItemFilter(sheet="S2"))) == ["CHV", "GV2", "P1", "V1"]
    assert set_tags(api.find(ItemFilter(tag=" p1 "))) == ["P1"]


def test_find_ands_its_fields_and_a_check_valve_is_not_operated() -> None:
    api = toy_api()

    assert set_tags(api.find(ItemFilter(label="OperatedValve", unit="1"))) == ["BV1"]
    assert "CHV" not in set_tags(api.find(_OPERATED))
    assert set_tags(api.find(ItemFilter(label="PipingComponent"))) == ["BV1", "CHV", "GV2"]


def test_an_unknown_label_is_an_error_not_an_empty_result() -> None:
    with pytest.raises(PlantApiError, match="known label.*'Valve'"):
        toy_api().find(ItemFilter(label="Valve"))
    with pytest.raises(PlantApiError, match="known sheet"):
        toy_api().find(ItemFilter(sheet="S99"))


def test_filter_restricts_a_handle() -> None:
    api = toy_api()
    equipment = api.find(ItemFilter(label="Equipment"))

    in_unit_2 = api.filter(equipment.handle, ItemFilter(unit="2"))

    assert set_tags(equipment) == ["P1", "T1", "V1", "V2"]
    assert set_tags(in_unit_2) == ["V2"]


# --- neighbours ---------------------------------------------------------------


def test_neighbours_follow_direction_and_relation_group() -> None:
    api = toy_api()

    assert member_tags(api.neighbours("P1", "downstream", "flow")) == ["CHV", "GV2"]
    assert member_tags(api.neighbours("P1", "upstream", "flow")) == ["BV1"]
    assert member_tags(api.neighbours("P1", "both", "flow")) == ["BV1", "CHV", "GV2"]
    assert member_tags(api.neighbours("BV1", "upstream", "signal")) == ["FV"]
    assert member_tags(api.neighbours("BV1", "upstream", "any")) == ["FV", "T1", "V1"]


def test_neighbours_can_be_filtered_and_report_the_edges_used() -> None:
    api = toy_api()

    result = api.neighbours("P1", "both", "flow", _OPERATED)

    assert member_tags(result) == ["BV1", "GV2"]
    assert result.total_edges == 2
    assert result.render().splitlines()[-2:] == [
        "BV1 -send_to-> P1 [crosses S1→S2]",
        "P1 -send_to-> GV2",
    ]


def test_neighbours_of_a_handle_expand_every_member() -> None:
    api = toy_api()
    valves = api.find(_OPERATED)

    downstream = api.neighbours(valves.handle, "downstream", "flow")

    assert member_tags(downstream) == ["P1", "V2"]


def test_a_cut_start_list_lists_no_edge_from_an_unlisted_start() -> None:
    # regression (QAR-P2 pilot): with more start items than max_items, an edge from a start
    # item beyond the cut was listed although its line could not name that item
    api = toy_api(max_items=1)
    valves = api.find(_OPERATED)

    downstream = api.neighbours(valves.handle, "downstream", "flow")

    listed = {item.item_id for item in downstream.start} | {
        member.item.item_id for member in downstream.members
    }
    assert all(e.source in listed and e.target in listed for e in downstream.edges)
    downstream.render()


# --- traverse -----------------------------------------------------------------


def test_traverse_closes_over_a_cycle_without_repeating_items() -> None:
    result = toy_api().traverse("T1", "downstream", "flow")

    assert [(m.item.tag, m.hops) for m in result.members] == [
        ("BV1", 1),
        ("P1", 2),
        ("CHV", 3),
        ("GV2", 3),
        ("V1", 4),
        ("V2", 4),
    ]
    assert result.total_edges == 7  # the recycle V1 -> BV1 is an edge used; BV1 is not repeated


def test_stop_at_includes_the_stop_item_and_goes_no_further() -> None:
    api = toy_api()

    first_valve = api.traverse("T1", "downstream", "flow", stop_at=_OPERATED)
    two_stops = api.traverse("P1", "downstream", "flow", stop_at=_OPERATED)

    assert [(m.item.tag, m.is_stop) for m in first_valve.members] == [("BV1", True)]
    assert [(m.item.tag, m.is_stop) for m in two_stops.members] == [
        ("CHV", False),
        ("GV2", True),
        ("V1", False),
        ("BV1", True),
    ]
    assert "V2" not in member_tags(two_stops)  # beyond the stop GV2


def test_walk_only_never_enters_other_items() -> None:
    api = toy_api()

    result = api.traverse("T1", "downstream", "flow", walk_only=ItemFilter(unit="1"))

    assert member_tags(result) == ["BV1", "P1", "CHV", "V1"]
    assert "GV2" not in result.render()  # not even as an edge target


def test_max_hops_limits_the_walk() -> None:
    result = toy_api().traverse("T1", "downstream", "flow", max_hops=2)

    assert member_tags(result) == ["BV1", "P1"]


def test_upstream_traverse_stops_at_a_tank() -> None:
    api = toy_api()

    result = api.traverse("V2", "upstream", "flow", stop_at=ItemFilter(label="Tank"))

    assert [(m.item.tag, m.hops, m.is_stop) for m in result.members] == [
        ("GV2", 1, False),
        ("P1", 2, False),
        ("BV1", 3, False),
        ("T1", 4, True),
        ("V1", 4, False),
        ("CHV", 5, False),
    ]


def test_max_hops_below_one_is_an_error() -> None:
    with pytest.raises(PlantApiError, match="max_hops"):
        toy_api().traverse("T1", "downstream", "flow", max_hops=0)


# --- path ---------------------------------------------------------------------


def test_path_lists_items_hops_and_sheets_in_order() -> None:
    result = toy_api().path("T1", "V2")

    assert [item.tag for item in result.items] == ["T1", "BV1", "P1", "GV2", "V2"]
    assert result.hops == 4
    assert result.sheets == ("S1", "S2", "S3")
    assert "path T1 to V2, 4 hops, sheets S1,S2,S3" in result.render()


def test_path_is_directed_by_default_and_undirected_on_request() -> None:
    api = toy_api()

    backwards = api.path("V2", "T1")
    undirected = api.path("V2", "T1", directed=False)

    assert not backwards.found and backwards.hops is None
    assert backwards.render() == f"{backwards.handle}: no path from V2 to T1"
    assert [item.tag for item in undirected.items] == ["V2", "GV2", "P1", "BV1", "T1"]


def test_path_over_signals_and_among_equal_paths_the_smaller_tag_sequence_wins() -> None:
    signal = toy_api().path("T1", "BV1", relations="signal")
    diamond = build_graph(
        {tag: (_PUMP, None, ("S1",)) for tag in ("A", "B", "X", "Z")},
        [
            ("A", "send_to", "X", ()),
            ("A", "send_to", "B", ()),
            ("X", "send_to", "Z", ()),
            ("B", "send_to", "Z", ()),
        ],
    )

    assert [item.tag for item in signal.items] == ["T1", "FT", "FIC", "FV", "BV1"]
    assert [item.tag for item in PlantApi(diamond).path("A", "Z").items] == ["A", "B", "Z"]


# --- aggregate and composition ------------------------------------------------


def test_handles_compose_traverse_then_filter_then_aggregate() -> None:
    api = toy_api()
    reached = api.traverse("T1", "downstream", "flow")  # $r1: BV1 P1 CHV GV2 V1 V2

    valves = api.filter(reached.handle, _OPERATED)
    by_sheet = api.aggregate(reached.handle, "sheet")

    assert (reached.handle, valves.handle, by_sheet.handle) == ("$r1", "$r2", "$r3")
    assert set_tags(valves) == ["BV1", "GV2"]
    assert [(row.group, row.count) for row in by_sheet.rows] == [("S2", 4), ("S1", 1), ("S3", 1)]


def test_aggregate_by_unit_and_class_orders_by_count_then_name() -> None:
    api = toy_api()
    everything = api.find(ItemFilter())

    by_unit = api.aggregate(everything.handle, "unit")
    by_class = api.aggregate(everything.handle, "node_class")

    assert [(row.group, row.count) for row in by_unit.rows] == [("1", 8), ("2", 2)]
    assert by_unit.rows[0].tags == ("BV1", "CHV", "FIC", "FT", "FV")  # first five, tag order
    assert [(row.group, row.count) for row in by_class.rows[:2]] == [
        ("PressureVessel", 2),
        ("ActuatingFunction", 1),
    ]
    assert by_class.total_groups == 9


def test_bad_handles_and_tags_raise_with_what_was_found() -> None:
    api = toy_api()
    api.find(ItemFilter(unit="2"))

    with pytest.raises(PlantApiError, match=r"handles \['\$r1'\].*'\$r7'"):
        api.filter("$r7", ItemFilter())
    with pytest.raises(PlantApiError, match="tag in the plant.*or a handle.*'NOPE'"):
        api.neighbours("NOPE", "both", "any")


def test_an_empty_handle_cannot_be_continued_from() -> None:
    api = toy_api()
    nothing = api.find(ItemFilter(unit="2", sheet="S1"))

    with pytest.raises(PlantApiError, match="holds no items"):
        api.aggregate(nothing.handle, "sheet")


# --- bounds, rendering, determinism -------------------------------------------


def test_truncation_reports_the_total_and_the_handle_keeps_every_item() -> None:
    api = toy_api(max_items=3)

    found = api.find(ItemFilter())
    by_unit = api.aggregate(found.handle, "unit")

    assert len(found.items) == 3 and found.total == 10
    assert found.render().splitlines()[0] == (
        "$r1: 10 items (7 more not shown; narrow with filter or aggregate)"
    )
    assert by_unit.total_items == 10


def test_every_result_renders_within_max_chars_and_never_prints_an_item_id() -> None:
    api = toy_api()
    results = [
        api.find(ItemFilter()),
        api.traverse("T1", "both", "any"),
        api.path("T1", "V2"),
        api.aggregate("$r1", "sheet"),
    ]

    for result in results:
        assert len(result.render(max_chars=150)) <= 150
        assert "id-" not in result.render()


def test_item_line_format_and_touched_keys() -> None:
    api = toy_api()
    found = api.find(ItemFilter(tag="BV1"))
    upstream = api.neighbours("P1", "upstream", "flow")

    assert found.render().splitlines()[1] == "BV1 (BallValve, unit 1, sheets S1)"
    assert found.touched_keys == ("S1:bv1",)
    assert upstream.touched_keys == ("S1:bv1", "S1:out1", "S2:in1", "S2:p1")


def test_same_calls_give_equal_results_and_text() -> None:
    def run() -> list[str]:
        api = toy_api()
        results = [
            api.traverse("T1", "both", "any"),
            api.path("T1", "V2"),
            api.aggregate("$r1", "node_class"),
        ]
        return [r.model_dump_json() + r.render() for r in results]

    assert run() == run()
