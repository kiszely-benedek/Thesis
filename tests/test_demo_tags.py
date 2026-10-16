"""Tag lookup of the demo: the sorted tag index, the lookup over an item graph, the HTTP route."""

from __future__ import annotations

import pytest

from plantgraph.demo.app.server import STATIC_DIR
from plantgraph.demo.app.tag_lookup import MAX_SUGGESTIONS, TagIndex, lookup
from plantgraph.qa.plant_api.item_graph import ItemGraph
from qa_harness_toy import CORPUS_ID
from qa_plant_api_toy import build_graph, toy_graph

# the toy server fixtures of the app tests (a pytest fixture is found by name in this module)
from test_demo_app import Client, env, make_client, toy  # noqa: F401

#: The toy plant's sheets: S1 holds T1/BV1, S2 holds P1/GV2, S3 holds V2.
PAGES = {"S1": 11, "S2": 12, "S3": 13}


def _numbered_graph(count: int) -> ItemGraph:
    """`count` tanks tagged TK-1 ... TK-<count>, all on S1."""
    return build_graph({f"TK-{n}": ("Tank", "1", ("S1",)) for n in range(1, count + 1)}, [])


def test_a_prefix_suggests_the_tags_that_start_with_it_in_sorted_order() -> None:
    index = TagIndex.build(toy_graph())

    assert index.suggest("G") == ("GV2",)
    assert index.suggest("f") == ("FIC", "FT", "FV")  # case is folded, the order is sorted


def test_suggestions_are_capped() -> None:
    index = TagIndex.build(_numbered_graph(25))

    assert len(index.suggest("TK-")) == MAX_SUGGESTIONS
    assert len(index.suggest("TK-", limit=3)) == 3


def test_a_prefix_that_matches_nothing_suggests_nothing() -> None:
    index = TagIndex.build(toy_graph())

    assert index.suggest("ZZ") == ()
    assert index.suggest("W") == ()  # sorts after the last tag: the slice is empty


def test_an_exact_tag_gives_the_item_with_class_unit_and_sheets_in_page_order() -> None:
    graph = build_graph({"A1": ("Tank", "7", ("S3", "S1"))}, [])

    found = lookup(" a1 ", graph, TagIndex.build(graph), PAGES)

    (hit,) = found.hits
    assert (hit.tag, hit.node_class, hit.unit_id) == ("A1", "Tank", "7")
    assert [(s.sheet_id, s.page) for s in hit.sheets] == [("S1", 11), ("S3", 13)]
    assert found.query == " a1 "


def test_a_prefix_has_no_hit_but_suggestions() -> None:
    graph = toy_graph()

    found = lookup("G", graph, TagIndex.build(graph), PAGES)

    assert found.hits == () and found.suggestions == ("GV2",)


def test_a_sheet_missing_from_the_drawing_index_is_refused() -> None:
    graph = toy_graph()

    with pytest.raises(ValueError, match="missing"):
        lookup("P1", graph, TagIndex.build(graph), {"S1": 1})


def test_the_route_looks_a_tag_up_by_its_corpus(make_client: Client) -> None:  # noqa: F811
    body = make_client().get(f"/api/corpora/{CORPUS_ID}/tags", params={"q": "p-2-1"}).json()

    (hit,) = body["hits"]
    assert hit["tag"] == "P-2-1" and hit["node_class"] == "CentrifugalPump"
    assert hit["unit_id"] == "2" and [s["sheet_id"] for s in hit["sheets"]] == ["3"]


def test_the_route_suggests_for_a_prefix(make_client: Client) -> None:  # noqa: F811
    body = make_client().get(f"/api/corpora/{CORPUS_ID}/tags", params={"q": "BV-2"}).json()

    assert body["hits"] == []
    assert body["suggestions"] == ["BV-2-1", "BV-2-2", "BV-2-3", "BV-2-4"]


def test_the_route_refuses_a_blank_or_overlong_query_and_an_unknown_corpus(
    make_client: Client,  # noqa: F811
) -> None:
    client = make_client()

    assert client.get(f"/api/corpora/{CORPUS_ID}/tags", params={"q": ""}).status_code == 422
    assert client.get(f"/api/corpora/{CORPUS_ID}/tags", params={"q": "x" * 65}).status_code == 422
    assert client.get("/api/corpora/nope/tags", params={"q": "P"}).status_code == 404


def test_a_corpus_still_loading_cannot_be_searched(make_client: Client) -> None:  # noqa: F811
    client = make_client(load=False)

    response = client.get(f"/api/corpora/{CORPUS_ID}/tags", params={"q": "P"})

    assert response.status_code == 409


def test_the_search_box_is_an_aria_combobox_over_a_listbox() -> None:
    page = (STATIC_DIR / "index.html").read_text("utf-8")

    for attribute in ('role="combobox"', 'aria-autocomplete="list"', 'aria-controls="find-list"'):
        assert attribute in page, f"expected {attribute} on the search box, found none"
    assert 'id="find-list"' in page and 'role="listbox"' in page


def test_the_page_starts_the_lookup_and_clears_it_when_the_plant_changes() -> None:
    app = (STATIC_DIR / "app.js").read_text("utf-8")

    assert "initLookup();" in app and "resetLookup();" in app
