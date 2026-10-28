"""The `plant_lines` store profile: rows, invariants, schema text, and equality with the plant API.

No database: the load plan's rows are inspected directly. The Cypher invariants and the real
load are run against a temporary database by hand (see the QT-3 report).
"""

from __future__ import annotations

from functools import cache

import pytest
from corpus_v2 import corpus

from plantgraph.graph.line_view import LINE_ITEM_CLASSES
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.store.neo4j_plan import CypherStatement, LoadPlan, build_load_plan
from plantgraph.store.plant_invariants import invariant_statements
from plantgraph.store.plant_rows import item_uid

_CORPUS_ID = "pytest-lines"


@cache
def _plan(profile: str) -> LoadPlan:
    built = corpus()
    return build_load_plan(
        _CORPUS_ID,
        built.localized_sheets,
        built.resolution,
        profile=profile,  # type: ignore[arg-type]
    )


@cache
def _item_graph() -> ItemGraph:
    built = corpus()
    view = NetworkxGraphView(_CORPUS_ID, built.localized_sheets, built.resolution)
    return build_item_graph(view, line_view=True)


def _node_props() -> dict[str, dict[str, object]]:
    """uid -> properties of every plant item node in the `plant_lines` plan."""
    rows = [
        row["props"]
        for statement in _plan("plant_lines").node_statements
        if ":PlantItem" in statement.query
        for row in _rows(statement)
    ]
    return {str(props["uid"]): props for props in rows}


def _rows(statement: CypherStatement) -> list[dict[str, object]]:
    rows = statement.parameters["rows"]
    assert isinstance(rows, list)
    return rows


def _line_to_rows() -> list[dict[str, object]]:
    return [
        row
        for statement in _plan("plant_lines").relationship_statements
        if "[r:line_to]" in statement.query
        for row in _rows(statement)
    ]


def test_the_line_to_edges_equal_the_plant_apis_line_view() -> None:
    graph = _item_graph()
    api_edges = {
        (item_uid(_CORPUS_ID, e.source), item_uid(_CORPUS_ID, e.target)): (
            tuple(e.via_tags),
            e.n_fittings,
        )
        for e in graph.line_edges
    }
    stored = {
        (str(r["source_uid"]), str(r["target_uid"])): (
            tuple(r["props"]["via_tags"]),  # type: ignore[index]
            r["props"]["n_fittings"],  # type: ignore[index]
        )
        for r in _line_to_rows()
    }

    assert api_edges, "the v2 corpus has no line edges, so the comparison proves nothing"
    assert stored == api_edges


def test_kind_valve_label_and_line_end_marks_equal_the_plant_apis() -> None:
    graph = _item_graph()
    props = _node_props()

    for item_id in graph.all_ids():
        item, stored = graph.item(item_id), props[item_uid(_CORPUS_ID, item_id)]
        assert stored["kind"] == item.kind
        if item.node_class in LINE_ITEM_CLASSES:
            assert stored["no_inflow"] == ("[no inflow]" in item.line_marks)
            assert stored["no_outflow"] == ("[no outflow]" in item.line_marks)
        else:
            assert "no_inflow" not in stored and "no_outflow" not in stored


def test_a_valve_has_the_valve_label_and_nothing_else_does() -> None:
    n_valves = sum(1 for p in _node_props().values() if p["kind"] == "valve")

    assert n_valves > 0
    assert _plan("plant_lines").expected_node_labels["Valve"] == n_valves


def test_the_profile_only_adds_to_the_plant_profile() -> None:
    plain, lines = _plan("plant"), _plan("plant_lines")

    assert {k: v for k, v in lines.expected_node_labels.items() if k != "Valve"} == (
        plain.expected_node_labels
    )
    assert {k: v for k, v in lines.expected_relationship_types.items() if k != "line_to"} == (
        plain.expected_relationship_types
    )
    assert lines.expected_relationship_types["line_to"] == len(_line_to_rows())
    assert "line_to" not in plain.expected_relationship_types


def test_the_plant_profile_plan_is_unchanged_by_the_new_profile() -> None:
    assert "kind" not in str(_plan("plant").node_statements)
    assert "Valve" not in _plan("plant").expected_node_labels


def test_the_invariants_of_plant_lines_are_the_plant_ones_and_three_new() -> None:
    ids = [s.invariant_id for s in invariant_statements("acme", "plant_lines")]

    assert ids == ["INV-6", "INV-7", "INV-8", "INV-9", "INV-10"]
    assert [s.invariant_id for s in invariant_statements("acme", "plant")] == ["INV-6", "INV-7"]
    assert len(_plan("plant_lines").invariant_statements) == 5


def test_the_schema_text_describes_the_line_view_and_the_v2_vocabulary() -> None:
    text = build_schema_text(_plan("plant_lines"))

    assert "line_to" in text.splitlines()[1]  # in the relationship-type list
    assert "kind" in text.splitlines()[2]
    assert "via_tags" in text.splitlines()[3]
    for fact in ("no_inflow", "ProcessInstrumentationFunction", "unit_id is a string", ":Valve"):
        assert fact in text


def test_the_plant_schema_text_does_not_mention_the_line_view() -> None:
    text = build_schema_text(_plan("plant"))

    assert "line_to" not in text and "no_inflow" not in text


def test_an_unknown_profile_in_a_plan_is_refused_by_the_schema_text() -> None:
    with pytest.raises(ValueError, match="profile"):
        build_schema_text(_plan("both"))


def test_the_ingest_cli_accepts_the_profile() -> None:
    from plantgraph.ingest import __main__ as ingest_main

    args = ingest_main._parse_args(
        ["synthetic", "--n-units", "4", "--store-profile", "plant_lines"]
    )

    assert args.store_profile == "plant_lines"
