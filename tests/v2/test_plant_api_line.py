"""The plant API's line view: `line` relations, `kind`, the `Valve` label, line-end marks."""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from corpus_v2 import corpus

from plantgraph.graph import schema
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.plant_api.line_graph import add_line_view
from plantgraph.qa.plant_api.model import ItemEdge, ItemFilter, ItemRecord, PlantApiError
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import item_line
from plantgraph.qa.scoring import normalize_scalar

#: id -> (node class, tag); `None` = a pipe part nobody names.
#: TK -> V1 -> tee -> STR (tagged strainer) -> P1;  tee -> V2 -> blind flange (a dead end).
_NODES: dict[str, tuple[str, str | None]] = {
    "tk": ("Tank", "TK-1"),
    "v1": ("GateValve", "GTV-1"),
    "tee": ("PipeTee", None),
    "str": ("ConicalStrainer", "STR-1"),
    "p1": ("CentrifugalPump", "P-1"),
    "v2": ("BallValve", "BFV-2"),
    "bf": ("BlindFlange", None),
}
_FLOW = [("tk", "v1"), ("v1", "tee"), ("tee", "str"), ("str", "p1"), ("tee", "v2"), ("v2", "bf")]


def _records() -> list[ItemRecord]:
    return [
        ItemRecord(
            item_id=item_id,
            tag=tag,
            node_class=node_class,
            labels=schema.labels_for(node_class),
            unit_id="1",
            sheets=("S1",),
            occurrence_keys=(f"S1:{item_id}",),
        )
        for item_id, (node_class, tag) in _NODES.items()
    ]


def _graph(*, line_view: bool) -> ItemGraph:
    records = _records()
    edges = [ItemEdge(source=a, target=b, relation="send_to") for a, b in _FLOW]
    ids_by_tag = {normalize_scalar(tag): (i,) for i, (_, tag) in _NODES.items() if tag}
    if not line_view:
        return ItemGraph(records, edges, ids_by_tag)
    line_records, line_edges = add_line_view(records, edges)
    return ItemGraph(line_records, edges, ids_by_tag, line_edges)


def _tags(items: Iterable[ItemRecord]) -> list[str]:
    return [item.tag or item.item_id for item in items]


def test_a_line_step_skips_the_fitting_and_names_the_strainer() -> None:
    api = PlantApi(_graph(line_view=True))

    sub = api.neighbours("GTV-1", "downstream", "line")

    assert [m.item.tag for m in sub.members] == ["BFV-2", "P-1"]
    assert "GTV-1 -line_to-> P-1 [via STR-1]" in sub.render()


def test_a_flow_step_still_stops_at_the_fitting() -> None:
    sub = PlantApi(_graph(line_view=True)).neighbours("GTV-1", "downstream", "flow")

    assert [m.item.item_id for m in sub.members] == ["tee"]


def test_kind_filter_and_the_valve_label_select_line_items_only() -> None:
    api = PlantApi(_graph(line_view=True))

    assert _tags(api.find(ItemFilter(label="Valve")).items) == ["BFV-2", "GTV-1"]
    assert _tags(api.find(ItemFilter(kind="valve")).items) == ["BFV-2", "GTV-1"]
    assert _tags(api.find(ItemFilter(kind="equipment")).items) == ["P-1", "TK-1"]
    assert _tags(api.find(ItemFilter(kind="inline")).items) == ["bf", "tee", "STR-1"]


def test_item_lines_show_the_kind_and_where_a_line_starts_or_stops() -> None:
    graph = _graph(line_view=True)

    assert "kind equipment" in item_line(graph.item("tk"))
    assert item_line(graph.item("tk")).endswith("[no inflow]")
    assert item_line(graph.item("p1")).endswith("[no outflow]")
    assert item_line(graph.item("v2")).endswith("[no outflow]")  # the blind flange is no line item
    assert item_line(graph.item("v1")).endswith("sheets S1)")


def test_a_line_path_lists_line_items_only() -> None:
    path = PlantApi(_graph(line_view=True)).path("TK-1", "P-1", "line")

    assert path.found and [i.tag for i in path.items] == ["TK-1", "GTV-1", "P-1"]


def test_a_walk_can_stop_at_the_first_valve_in_the_line_view() -> None:
    api = PlantApi(_graph(line_view=True))

    sub = api.traverse("TK-1", "downstream", "line", stop_at=ItemFilter(kind="valve"))

    assert [(m.item.tag, m.is_stop) for m in sub.members] == [("GTV-1", True)]


def test_without_the_line_view_the_new_vocabulary_is_refused() -> None:
    api = PlantApi(_graph(line_view=False))

    with pytest.raises(PlantApiError, match="no line view.*'line'"):
        api.neighbours("GTV-1", "downstream", "line")
    with pytest.raises(PlantApiError, match="no line view"):
        api.find(ItemFilter(kind="valve"))
    with pytest.raises(PlantApiError, match="known label.*'Valve'"):
        api.find(ItemFilter(label="Valve"))


def test_without_the_line_view_item_lines_are_the_v1_text() -> None:
    graph = _graph(line_view=False)

    assert item_line(graph.item("tk")) == "TK-1 (Tank, unit 1, sheets S1)"
    assert graph.item("tk").kind is None and not graph.has_line_view


def test_the_group_any_never_follows_line_edges() -> None:
    api = PlantApi(_graph(line_view=True))

    sub = api.neighbours("GTV-1", "downstream", "any")

    assert [m.item.item_id for m in sub.members] == ["tee"]


def test_building_with_the_line_view_keeps_the_drawn_graph_and_adds_kinds() -> None:
    built = corpus()
    view = NetworkxGraphView("T", built.localized_sheets, built.resolution)
    plain, lined = build_item_graph(view), build_item_graph(view, line_view=True)

    assert plain.edges == lined.edges and plain.all_ids() == lined.all_ids()
    assert all(lined.item(i).kind is not None for i in lined.all_ids())
    assert lined.line_edges and not plain.line_edges
