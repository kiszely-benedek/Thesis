"""Sheet route, flow route and through-line on hand-built toys (design §3.2-§3.3, §9)."""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.qa.anchors import TagAnchor, extract_anchors
from plantgraph.qa.routing import (
    build_flow_graph,
    build_sheet_route_graph,
    flow_route,
    flow_through_line,
    route_pair_by_flow,
    route_pair_by_sheets,
    sheet_route,
    sheet_through_line,
)
from qa_routing_toy import ToyCorpus, key


def _anchor(toy: ToyCorpus, tag: str) -> TagAnchor:
    anchors = extract_anchors(tag, toy.view())
    assert len(anchors.tags) == 1, f"toy has no unique tag {tag!r}"
    return anchors.tags[0]


def _identity_only_toy() -> ToyCorpus:
    """S1 ~ S2 by an off-page connector; S3 touches S2 only through a repeated drawing of P-1."""
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.item("S2", "p", "P-1")
    toy.cut("S1", "a", "S2", "p", "c1")
    toy.item("S3", "p_ref", "P-1")
    toy.item("S3", "t", "TT")
    toy.flow("S3", "p_ref", "t")
    toy.identity("P-1", home=("S2", "p"), references=[("S3", "p_ref")])
    return toy


def _back_and_forth_toy() -> ToyCorpus:
    """Flow A(S1) -> B(S2) -> C(S1) -> D(S2): three crossings, but only two sheets."""
    toy = ToyCorpus()
    for sheet, node in (("S1", "a"), ("S2", "b"), ("S1", "c"), ("S2", "d")):
        toy.item(sheet, node, f"T{node.upper()}")
    toy.cut("S1", "a", "S2", "b", "c1")
    toy.cut("S2", "b", "S1", "c", "c2")
    toy.cut("S1", "c", "S2", "d", "c3")
    return toy


def test_identity_links_join_the_sheet_graph_into_one_component() -> None:
    view = _identity_only_toy().view()

    without = build_sheet_route_graph(view, with_identity_links=False)
    with_links = build_sheet_route_graph(view)

    assert nx.number_connected_components(without.graph) == 2
    assert nx.number_connected_components(with_links.graph) == 1


def test_sheet_route_crosses_an_identity_link_and_is_deterministic() -> None:
    toy = _identity_only_toy()
    sheets = build_sheet_route_graph(toy.view())

    assert sheet_route(sheets, {"S1"}, {"S3"}) == ("S1", "S2", "S3")
    assert sheet_route(sheets, {"S1"}, {"S3"}) == sheet_route(sheets, {"S1"}, {"S3"})
    unlinked = build_sheet_route_graph(toy.view(), with_identity_links=False)
    assert sheet_route(unlinked, {"S1"}, {"S3"}) is None


def test_unknown_sheet_raises_naming_it() -> None:
    sheets = build_sheet_route_graph(_identity_only_toy().view())

    with pytest.raises(ValueError, match="S9"):
        sheet_route(sheets, {"S9"}, {"S1"})


def test_a_flow_path_that_revisits_sheets_is_covered_whole() -> None:
    toy = _back_and_forth_toy()
    flow = build_flow_graph(toy.view())

    route = flow_route(flow, {key("S1", "a")}, {key("S2", "d")})

    assert route is not None
    assert route.distance == 3  # one plant hop per crossing, as the uncut edges counted
    assert route.sheets == ("S1", "S2")
    assert key("S1", "c") in route.path  # the revisit of S1 is on the path
    assert not route.reversed


def test_a_cut_costs_one_hop_like_the_plain_edge() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.item("S1", "b", "TB")
    toy.flow("S1", "a", "b")
    toy.item("S2", "c", "TC")
    toy.cut("S1", "b", "S2", "c", "c1")
    flow = build_flow_graph(toy.view())

    plain = flow_route(flow, {key("S1", "a")}, {key("S1", "b")})
    across = flow_route(flow, {key("S1", "b")}, {key("S2", "c")})

    assert plain is not None and plain.distance == 1
    assert across is not None and across.distance == 1


def test_reverse_direction_is_used_when_forward_has_no_path() -> None:
    flow = build_flow_graph(_back_and_forth_toy().view())

    route = flow_route(flow, {key("S2", "d")}, {key("S1", "a")})

    assert route is not None
    assert route.reversed
    assert route.distance == 3


def test_no_directed_path_falls_back_to_the_sheet_route_and_says_so() -> None:
    """Two branches that meet only upstream: A and B are both fed by X."""
    toy = ToyCorpus()
    toy.item("S1", "x", "TX")
    toy.item("S2", "a", "TA")
    toy.item("S3", "b", "TB")
    toy.cut("S1", "x", "S2", "a", "c1")
    toy.cut("S1", "x", "S3", "b", "c2")
    flow, sheets = build_flow_graph(toy.view()), build_sheet_route_graph(toy.view())

    route = route_pair_by_flow(flow, sheets, _anchor(toy, "TA"), _anchor(toy, "TB"))

    assert route.found and route.fell_back_to_sheet_graph
    assert route.sheets == ("S2", "S1", "S3")
    assert route.path == ()


def test_pair_routes_report_mode_and_no_route() -> None:
    toy = _back_and_forth_toy()
    toy.item("S9", "z", "TZ")  # an island sheet
    flow, sheets = build_flow_graph(toy.view()), build_sheet_route_graph(toy.view())
    source, target = _anchor(toy, "TA"), _anchor(toy, "TD")

    by_flow = route_pair_by_flow(flow, sheets, source, target)
    by_sheets = route_pair_by_sheets(sheets, source, target)
    island = route_pair_by_sheets(sheets, source, _anchor(toy, "TZ"))

    assert by_flow.found and not by_flow.fell_back_to_sheet_graph and by_flow.path
    assert by_sheets.sheets == ("S1", "S2") and by_sheets.path == ()
    assert not island.found


def _identity_flow_toy() -> ToyCorpus:
    """A(S1) -> R(S2, a repeat of P) ~ P(S3, home) -> T(S3); X(S2) is an unrelated neighbour."""
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.item("S2", "r", "P-1")
    toy.item("S2", "x", "TX")
    toy.flow("S2", "x", "r")
    toy.cut("S1", "a", "S2", "r", "c1")
    toy.item("S3", "h", "P-1")
    toy.item("S3", "t", "TT")
    toy.flow("S3", "h", "t")
    toy.identity("P-1", home=("S3", "h"), references=[("S2", "r")])
    return toy


def test_flow_route_moves_between_reference_and_home_for_free() -> None:
    toy = _identity_flow_toy()
    flow = build_flow_graph(toy.view())

    route = flow_route(flow, {key("S1", "a")}, {key("S3", "t")})

    assert route is not None
    assert route.distance == 2  # A -> P -> T, the plant's two hops
    assert route.sheets == ("S1", "S2", "S3")


def test_flow_through_line_keeps_stubs_and_path_items_only() -> None:
    toy = _identity_flow_toy()
    flow = build_flow_graph(toy.view())
    route = flow_route(flow, {key("S1", "a")}, {key("S3", "t")})
    assert route is not None

    kept = flow_through_line(flow, route.path, core_sheets={"S1", "S3"})

    assert kept == {"S2": (key("S2", "in_c1"), key("S2", "r"))}
    assert kept == flow_through_line(flow, route.path, core_sheets={"S1", "S3"})


def _chain_toy(connected_inside: bool) -> ToyCorpus:
    """A(S1) -> m(S2) -> T(S3); S2 also holds junk J; `connected_inside=False` splits S2 in two."""
    toy = ToyCorpus()
    toy.item("S1", "a", "TA")
    toy.item("S2", "m", "TM")
    toy.item("S2", "j", "TJ")
    toy.item("S3", "t", "TT")
    toy.cut("S1", "a", "S2", "m", "c1")
    if connected_inside:
        toy.cut("S2", "m", "S3", "t", "c2")
        toy.flow("S2", "j", "m")
    else:
        toy.cut("S2", "j", "S3", "t", "c2")  # leaves S2 through J, not through m
    return toy


def test_sheet_through_line_follows_the_path_inside_the_sheet() -> None:
    toy = _chain_toy(connected_inside=True)
    view = toy.view()
    flow, sheets = build_flow_graph(view), build_sheet_route_graph(view)

    kept = sheet_through_line(flow, sheets, ("S1", "S2", "S3"), core_sheets={"S1", "S3"})

    assert kept == {"S2": (key("S2", "in_c1"), key("S2", "m"), key("S2", "out_c2"))}


def test_sheet_through_line_keeps_the_whole_sheet_when_no_inside_path_exists() -> None:
    toy = _chain_toy(connected_inside=False)
    view = toy.view()
    flow, sheets = build_flow_graph(view), build_sheet_route_graph(view)

    kept = sheet_through_line(flow, sheets, ("S1", "S2", "S3"), core_sheets={"S1", "S3"})

    assert set(kept["S2"]) == set(flow.keys_by_sheet["S2"])
