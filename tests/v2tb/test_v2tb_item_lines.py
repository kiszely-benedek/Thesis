"""T14d R14a/R14b/R14d/R14e: what a B item line shows, and that edge lines stay the frozen ones."""

from __future__ import annotations

import pytest
from plants_b import real_corpus, real_plant

from plantgraph.qa.agent.strategies import GraphAgentLines
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.item_graph_b import (
    build_item_graph_b,
    shows_b_properties,
    with_line_numbers,
)
from plantgraph.qa.v2tb.plant_api_b import item_line_b
from plantgraph.qa.v2tb.shown_b import item_line_misses
from plantgraph.qa.v2tb.strategies_b import GraphAgentLinesB, _with_b_reading
from plantgraph.qa.v2tb.views_b import NetworkxGraphViewB
from qa_agent_fakes import DONE, PIN, ScriptedModel, call

_VALVE = ItemRecord(
    item_id="s:v",
    tag=None,
    node_class="GateValve",
    labels=(),
    unit_id=None,
    sheets=("s",),
    occurrence_keys=("s:v",),
)


def _edge(source: str, target: str, line: str | None) -> ItemEdge:
    properties = {} if line is None else {"line_number": line}
    return ItemEdge(source=source, target=target, relation="send_to", properties=properties)


def _graph(view: NetworkxGraphViewB) -> ItemGraph:
    return build_item_graph_b(view, line_view=True)


def _numbers_of(items: list[ItemRecord]) -> dict[str, object]:
    return {i.item_id: i.properties.get("line_numbers") for i in items}


# ---- item lines ---------------------------------------------------------------------------------


def test_an_untagged_valve_at_a_spec_break_prints_both_numbers_in_folded_order() -> None:
    edges = [_edge("pump", "s:v", '6"-P-1203-A1A'), _edge("s:v", "tank", "2-P-1204-A1A")]
    pump = _VALVE.model_copy(update={"item_id": "pump", "tag": "P-1", "node_class": "Pump"})

    items = with_line_numbers([pump, _VALVE], edges)

    assert item_line_b(items[1]).endswith('[lines 2-P-1204-A1A, 6"-P-1203-A1A]')
    assert "line_numbers" not in items[0].properties  # a tagged non-valve prints none


def test_an_untagged_valve_on_one_line_prints_line_once_and_a_tagged_valve_prints_none() -> None:
    edges = [_edge("a", "s:v", "L1"), _edge("s:v", "b", "L1"), _edge("a", "t:v", "L1")]
    tagged = _VALVE.model_copy(update={"item_id": "t:v", "tag": "HV-1"})

    items = with_line_numbers([_VALVE, tagged], edges)

    assert item_line_b(items[0]).endswith(" [line L1]")
    assert "[line" not in item_line_b(items[1])


def test_an_untagged_valve_with_no_drawn_line_number_prints_the_frozen_line() -> None:
    items = with_line_numbers([_VALVE], [_edge("a", "s:v", None)])

    assert _numbers_of(items) == {"s:v": None}


def test_a_positioned_valve_prints_the_position_before_the_line_numbers() -> None:
    valve = _VALVE.model_copy(update={"properties": {"operating_position": "NC"}})

    (shown,) = with_line_numbers([valve], [_edge("a", "s:v", "L1")])

    assert item_line_b(shown).endswith(" [operating_position NC] [line L1]")


def test_every_line_of_the_small_real_plant_is_exact() -> None:
    corpus = real_corpus()
    plain = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution)
    valves = [i.local_key for i in plain.items() if "Valve" in i.node_class and i.tag]
    positions = {key: "NC" for key in valves}
    view = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution, positions)
    graph = _graph(view)

    misses = item_line_misses(graph, positions, PlantIndex(real_plant()), corpus.occurrence_map)

    assert misses == []
    assert any("line_numbers" in graph.item(i).properties for i in graph.all_ids())  # not vacuous


# ---- edge lines are the frozen ones -------------------------------------------------------------


def _positioned_view() -> tuple[NetworkxGraphViewB, str]:
    corpus = real_corpus()
    plain = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution)
    valves = [i for i in plain.items() if "Valve" in i.node_class and i.tag is not None]
    positions = {valve.local_key: "NC" for valve in valves}
    return (
        NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution, positions),
        str(valves[0].tag),
    )


def test_the_b_agent_prints_the_frozen_edge_lines() -> None:
    view, tag = _positioned_view()
    script = [call("neighbours", of=tag, direction="both", relations="flow"), DONE]
    graph = _graph(view)
    b_context = GraphAgentLinesB(graph, PIN, ScriptedModel(script)).retrieve("q").context
    a_context = GraphAgentLines(graph, PIN, ScriptedModel(script)).retrieve("q").context

    assert b_context is not None and a_context is not None
    b_edges = [x for x in b_context.splitlines() if "-send_to->" in x]
    assert b_edges and b_edges == [x for x in a_context.splitlines() if "-send_to->" in x]
    assert " [line " not in "".join(b_edges)


# ---- the prompt sentence ------------------------------------------------------------------------


def _frozen_and_b(view: NetworkxGraphViewB) -> tuple[str, str]:
    graph = _graph(view)
    frozen = GraphAgentLines(graph, PIN, ScriptedModel([])).system_prompt
    return frozen, GraphAgentLinesB(graph, PIN, ScriptedModel([])).system_prompt


def test_on_a_b_corpus_the_prompt_is_the_frozen_one_plus_one_sentence() -> None:
    view, _tag = _positioned_view()

    frozen, b_prompt = _frozen_and_b(view)

    assert b_prompt == _with_b_reading(frozen) and b_prompt != frozen
    assert b_prompt.count("[operating_position NC]") == 1


def test_on_an_a_corpus_the_prompt_equals_the_frozen_one_byte_for_byte() -> None:
    corpus = real_corpus()
    plain = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution)

    frozen, b_prompt = _frozen_and_b(plain)

    assert b_prompt == frozen
    assert not shows_b_properties(build_item_graph(plain, line_view=True))


def test_the_added_sentence_is_refused_when_the_frozen_sentence_is_gone() -> None:
    with pytest.raises(ValueError, match="An item line reads"):
        _with_b_reading("a prompt with no item-line sentence")


def test_the_first_message_of_an_a_corpus_is_the_frozen_one() -> None:
    corpus = real_corpus()
    plain = NetworkxGraphViewB("c", corpus.localized_sheets, corpus.resolution)
    b_send, a_send = ScriptedModel([DONE]), ScriptedModel([DONE])
    graph = _graph(plain)

    GraphAgentLinesB(graph, PIN, b_send).retrieve("q")
    GraphAgentLines(graph, PIN, a_send).retrieve("q")

    assert b_send.requests[0].messages == a_send.requests[0].messages
