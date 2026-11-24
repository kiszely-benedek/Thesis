"""R5: the two B views extend the frozen ones and change one thing each."""

from __future__ import annotations

import pytest
from plants_b import real_corpus

from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.neo4j_view import Neo4jGraphView
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.qa.v2tb.schema_text_b import build_schema_text_b
from plantgraph.qa.v2tb.store_b import with_positions
from plantgraph.qa.v2tb.views_b import Neo4jGraphViewB, NetworkxGraphViewB
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from plantgraph.store.neo4j_plan import build_load_plan
from plantgraph.store.neo4j_settings import Neo4jSettings


def _frozen_and_b(
    positions: dict[str, str] | None,
) -> tuple[NetworkxGraphView, NetworkxGraphViewB]:
    corpus = real_corpus()
    frozen = NetworkxGraphView("c", corpus.localized_sheets, corpus.resolution)
    view_b = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution, positions)
    return frozen, view_b


def _some_valve_keys(n: int) -> list[str]:
    frozen = NetworkxGraphView("c", real_corpus().localized_sheets, real_corpus().resolution)
    return [i.local_key for i in frozen.items() if "Valve" in i.node_class][:n]


def test_with_an_empty_map_the_b_view_equals_the_frozen_view() -> None:
    frozen, view_b = _frozen_and_b(None)
    sheets = frozen.sheets()[:3]

    assert view_b.items() == frozen.items()
    assert view_b.edges() == frozen.edges()
    assert view_b.sheets() == frozen.sheets()
    assert sorted(view_b.subgraph(sheets).nodes(data=True)) == sorted(
        frozen.subgraph(sheets).nodes(data=True)
    )


def test_with_the_map_exactly_the_positioned_valves_gain_the_property() -> None:
    keys = _some_valve_keys(4)
    frozen, view_b = _frozen_and_b(dict.fromkeys(keys, "NC"))

    gained = {i.local_key for i in view_b.items() if OPERATING_POSITION in i.properties}
    assert gained == set(keys)
    without = [i for i in view_b.items() if i.local_key not in keys]
    assert without == [i for i in frozen.items() if i.local_key not in keys]
    # one graph behind every method: a subgraph shows the same property
    sheet = next(i for i in view_b.items() if i.local_key == keys[0]).sheet_id
    assert view_b.subgraph([sheet]).nodes[keys[0]][OPERATING_POSITION] == "NC"


def test_a_position_for_a_valve_the_view_does_not_have_is_refused() -> None:
    with pytest.raises(ValueError, match="positioned valve 'S9:nope'"):
        _frozen_and_b({"S9:nope": "NO"})


def test_the_neo4j_view_b_serves_the_b_schema_text_without_a_database() -> None:
    corpus = real_corpus()
    plan = build_load_plan("c", corpus.localized_sheets, corpus.resolution, profile="plant_lines")
    patched = with_positions(plan, dict.fromkeys(_some_valve_keys(3), "NO"))
    settings = Neo4jSettings(uri="bolt://unused:7687", username="u", password="p")  # type: ignore[arg-type]

    view_b = Neo4jGraphViewB(settings, patched)
    frozen = Neo4jGraphView(settings, patched)

    assert view_b.schema_text() == build_schema_text_b(patched)
    assert OPERATING_POSITION in view_b.schema_text()
    assert OPERATING_POSITION not in frozen.schema_text()
    assert frozen.schema_text() == build_schema_text(patched)
    # an unpatched plan gives the frozen text exactly
    assert Neo4jGraphViewB(settings, plan).schema_text() == build_schema_text(plan)
